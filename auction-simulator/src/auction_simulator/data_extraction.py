"""
Data extraction from ClickHouse for auction simulation.

Extracts historical impressions and campaign budgets with local caching support.
"""

import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts and caches data from ClickHouse for simulation."""

    def __init__(self, config):
        """
        Initialize data extractor.

        Args:
            config: Configuration object with database and cache settings
        """
        self.config = config
        self.client = None
        self.protocol = None  # 'native' or 'http'
        self.pg_client = None  # PostgreSQL connection
        self.cache_dir = Path(config.cache.directory)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_feed_filter_clause(self) -> str:
        """
        Get the feed_id filter clause based on configuration.

        Similar to category_id filtering:
        - If feed_id is specified (list): filters to those feed_id values
        - If feed_id is None/empty: no filter (all feeds)

        Returns:
            SQL WHERE clause for feed_id filtering, or empty string if no filter
        """
        # Get feed_id from config
        feed_ids = None
        if hasattr(self.config, 'data_extraction'):
            feed_ids = getattr(self.config.data_extraction, 'feed_id', ['6500', '6002'])

        # If feed_ids is None or empty, return no filter
        if not feed_ids:
            return ""

        # Build IN clause with feed_id values
        feed_ids_str = ', '.join(f"'{fid}'" for fid in feed_ids)
        return f"AND feed_id IN ({feed_ids_str})"

    def connect(self):
        """Establish connection to ClickHouse (auto-detect protocol)."""
        if self.client is None:
            port = self.config.database.port
            host = self.config.database.host

            # Auto-detect protocol based on port
            if port == 8123 or port == 8443:
                self.protocol = 'http'
                logger.info(f"Connecting to ClickHouse via HTTP: {host}:{port}")

                try:
                    import clickhouse_connect

                    self.client = clickhouse_connect.get_client(
                        host=host,
                        port=port,
                        database=self.config.database.database,
                        username=self.config.database.user,
                        password=self.config.database.password,
                        secure=self.config.database.get('secure', False),
                        connect_timeout=self.config.database.connect_timeout,
                        send_receive_timeout=self.config.database.send_receive_timeout
                    )
                    logger.info("Connected to ClickHouse successfully (HTTP protocol)")

                except ImportError:
                    raise ImportError(
                        "clickhouse-connect is required for HTTP protocol. "
                        "Install it with: pip install clickhouse-connect"
                    )
            else:
                self.protocol = 'native'
                logger.info(f"Connecting to ClickHouse via native protocol: {host}:{port}")

                try:
                    from clickhouse_driver import Client

                    self.client = Client(
                        host=host,
                        port=port,
                        database=self.config.database.database,
                        user=self.config.database.user,
                        password=self.config.database.password,
                        connect_timeout=self.config.database.connect_timeout,
                        send_receive_timeout=self.config.database.send_receive_timeout
                    )
                    logger.info("Connected to ClickHouse successfully (native protocol)")

                except ImportError:
                    raise ImportError(
                        "clickhouse-driver is required for native protocol. "
                        "Install it with: pip install clickhouse-driver"
                    )

    def disconnect(self):
        """Close ClickHouse and PostgreSQL connections."""
        if self.client:
            if self.protocol == 'http':
                self.client.close()
            else:
                self.client.disconnect()
            self.client = None
            logger.info("Disconnected from ClickHouse")

        self._disconnect_postgres()

    def _connect_postgres(self):
        """Establish connection to PostgreSQL for min_bid lookup."""
        if self.pg_client is None:
            pg_config = self.config.postgres_database
            host = pg_config.host
            port = pg_config.port
            database = pg_config.database

            logger.info(f"Connecting to PostgreSQL: {host}:{port}/{database}")

            try:
                self.pg_client = psycopg2.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=pg_config.user,
                    password=pg_config.password,
                    connect_timeout=pg_config.connect_timeout
                )
                logger.info("Connected to PostgreSQL successfully")
            except psycopg2.Error as e:
                logger.error(f"Failed to connect to PostgreSQL {host}:{port}/{database}: {e}")
                raise

    def _disconnect_postgres(self):
        """Close PostgreSQL connection."""
        if self.pg_client:
            self.pg_client.close()
            self.pg_client = None
            logger.info("Disconnected from PostgreSQL")

    def _execute_query(self, query: str) -> List[Tuple]:
        """Execute query with protocol-specific method."""
        if self.protocol == 'http':
            # clickhouse-connect returns pandas DataFrame or QueryResult
            result = self.client.query(query)
            return result.result_rows  # Get rows as list of tuples
        else:
            # clickhouse-driver returns list of tuples
            return self.client.execute(query)

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.parquet"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is valid (within TTL)."""
        if not cache_path.exists():
            return False

        cache_ttl_hours = self.config.cache.ttl_hours
        if cache_ttl_hours <= 0:
            return True

        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return file_age < timedelta(hours=cache_ttl_hours)

    def extract_data(
        self,
        country: int,
        categories: Optional[List[int]],
        time_from: date,
        time_to: date,
        use_cache: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[int, float], List[int]]:
        """
        Extract all required data for simulation.

        Args:
            country: Country ID
            categories: List of category IDs, or None to extract all categories for the country
            time_from: Start date (inclusive)
            time_to: End date (inclusive)
            use_cache: Whether to use local cache

        Returns:
            Tuple of (impressions_df, budgets_df, min_bid_by_category, categories)
        """
        # If categories is None, fetch all categories for the country
        if categories is None:
            self.connect()
            categories = self._get_all_categories_for_country(country, time_from, time_to)
            logger.info(f"Auto-detected {len(categories)} categories for country {country}")

        cache_key = f"{country}_{'_'.join(map(str, categories))}_{time_from}_{time_to}"

        # Try loading from cache
        if use_cache:
            impressions = self._load_from_cache(f"{cache_key}_impressions")
            budgets = self._load_from_cache(f"{cache_key}_budgets")
            min_bids = self._load_from_cache(f"{cache_key}_min_bids")

            if impressions is not None and budgets is not None and min_bids is not None:
                logger.info("Loaded data from cache")
                min_bid_dict = min_bids.set_index('category_id')['min_bid'].to_dict()
                return impressions, budgets, min_bid_dict, categories

        # Extract from database
        logger.info(f"Extracting data from ClickHouse for country={country}, categories={categories}, "
                    f"time_from={time_from}, time_to={time_to}")

        self.connect()

        impressions = self._extract_impressions(country, categories, time_from, time_to)
        budgets = self._extract_budgets(country, categories, time_from, time_to)
        # Fetch min_bid from PostgreSQL (authoritative source)
        min_bid_dict = self._fetch_min_bids_from_postgres(country, categories)
        # OLD: min_bid_dict = self._calculate_min_bids(country, categories, time_from, time_to)

        # Save to cache
        if use_cache:
            self._save_to_cache(impressions, f"{cache_key}_impressions")
            self._save_to_cache(budgets, f"{cache_key}_budgets")
            min_bids_df = pd.DataFrame(list(min_bid_dict.items()), columns=['category_id', 'min_bid'])
            self._save_to_cache(min_bids_df, f"{cache_key}_min_bids")

        logger.info(f"Extracted {len(impressions)} reach records, {len(budgets)} budget records")

        return impressions, budgets, min_bid_dict, categories

    def _get_all_categories_for_country(
        self,
        country: int,
        time_from: date,
        time_to: date
    ) -> List[int]:
        """
        Get all distinct category IDs for a country in the specified date range.

        Args:
            country: Country ID
            time_from: Start date
            time_to: End date

        Returns:
            List of category IDs
        """
        feed_filter_clause = self._get_feed_filter_clause()
        query = f"""
            SELECT DISTINCT category_id
            FROM enriched_distributed
            WHERE data_chunk_date >= toDate('{time_from}')
              AND data_chunk_date <= toDate('{time_to}')
              AND toDate(timestamp) >= toDate('{time_from}')
              AND toDate(timestamp) <= toDate('{time_to}')
              AND country_id = {country}
              AND category_id > 0
              AND component = 'listing'
              AND screen != 'my_profile'
              AND element = 'ad'
              AND action = 'view'
              {feed_filter_clause}
              AND client != 'backend'
              AND ad_id IS NOT NULL
            ORDER BY category_id
        """

        rows = self._execute_query(query)
        categories = [row[0] for row in rows]
        return categories

    def _extract_impressions(
        self,
        country: int,
        categories: List[int],
        time_from: date,
        time_to: date
    ) -> pd.DataFrame:
        """
        Extract reach data from enriched_distributed.

        Filters for impression view events only (component='listing', action='view')
        and calculates REACH (unique user_id per day per ad), not impressions.

        Reach is counted ONCE per day per user per ad, regardless of how many
        hours the user viewed the ad during that day.

        Returns DataFrame with columns:
        - category_id
        - ad_id
        - seller_id
        - date
        - total_reach (COUNT DISTINCT user_id per day)
        - organic_reach (COUNT DISTINCT user_id WHERE campaign_show_ad != 'True')
        - raw_impressions (COUNT * - for comparison)
        - reach_timestamp (MIN timestamp - when first view occurred)
        - hour (extracted from reach_timestamp - for hourly distribution)
        """
        categories_str = ','.join(map(str, categories))
        feed_filter_clause = self._get_feed_filter_clause()

        query = f"""
        SELECT
            category_id,
            ad_id,
            lister_user_id as seller_id,
            toDate(timestamp) as date,
            COUNT(DISTINCT user_id) as total_reach,
            COUNT(DISTINCT CASE WHEN campaign_show_ad != 'True' THEN user_id END) as organic_reach,
            COUNT(*) as raw_impressions,
            MIN(timestamp) as reach_timestamp
        FROM enriched_distributed
        WHERE
            data_chunk_date >= toDate('{time_from}')
            AND data_chunk_date <= toDate('{time_to}')
            AND toDate(timestamp) >= toDate('{time_from}')
            AND toDate(timestamp) <= toDate('{time_to}')
            AND country_id = {country}
            AND category_id IN ({categories_str})
            AND component = 'listing'
            AND screen != 'my_profile'
            AND element = 'ad'
            AND action = 'view'
            -- Filter expansions for comprehensive data (change: expand-data-extraction-filters):
            --   feed_id IN ('6500', '6002'): Include both category feed and additional feed
            --   No ad_type filter: Include all ad types for complete simulation
            {feed_filter_clause}
            AND client != 'backend'
            AND ad_id IS NOT NULL
            AND user_id IS NOT NULL  -- Required for reach calculation (change: migrate-impressions-to-reach)
        GROUP BY category_id, ad_id, lister_user_id, toDate(timestamp)
        ORDER BY category_id, ad_id, date
        """

        logger.info("Executing reach query...")
        result = self._execute_query(query)

        df = pd.DataFrame(
            result,
            columns=['category_id', 'ad_id', 'seller_id', 'date',
                     'total_reach', 'organic_reach', 'raw_impressions', 'reach_timestamp']
        )

        # Extract hour from reach_timestamp for hourly distribution
        # Reach is counted once per day, but assigned to the hour of first view
        df['hour'] = pd.to_datetime(df['reach_timestamp']).dt.hour

        logger.info(f"Extracted {len(df)} reach records")

        # Validate data
        self._validate_impressions(df)

        return df

    def _extract_budgets(
        self,
        country: int,
        categories: List[int],
        time_from: date,
        time_to: date
    ) -> pd.DataFrame:
        """
        Extract campaign budget data from spendings_distributed.

        Filters budgets to only include ads from selected categories using a subquery,
        reducing data transfer by ~50x (from ~50,000 to ~1,000 records).

        Returns DataFrame with columns:
        - ad_id
        - seller_id
        - date
        - daily_budget (kopecks)
        - actual_spend (kopecks)
        - campaign_id
        """
        categories_str = ','.join(map(str, categories))

        query = f"""
        SELECT
            ad_id,
            user_id as seller_id,
            category_id,
            operationdate as date,
            price_per_day as daily_budget,
            spending as actual_spend,
            campaign_id
        FROM analytics_reports.spendings_distributed
        WHERE
            operationdate >= toDate('{time_from}')
            AND operationdate <= toDate('{time_to}')
            AND country_id = {country}
            AND category_id IN ({categories_str})
            AND category_id IS NOT NULL
            AND ad_id IS NOT NULL
        ORDER BY ad_id, date, campaign_id DESC
        """

        logger.info("Executing budgets query with category filter...")
        logger.debug(f"Budget query structure: filtering by {len(categories)} categories: {categories}")
        result = self._execute_query(query)

        df = pd.DataFrame(
            result,
            columns=['ad_id', 'seller_id', 'category_id', 'date', 'daily_budget', 'actual_spend', 'campaign_id']
        )

        # Convert Decimal to float for numeric columns to avoid type errors
        df['daily_budget'] = df['daily_budget'].astype(float)
        df['actual_spend'] = df['actual_spend'].astype(float)

        logger.info(f"Extracted {len(df)} budget records (before deduplication)")

        # Deduplicate: keep latest campaign_id per (ad_id, date)
        df = df.sort_values(['ad_id', 'date', 'campaign_id'], ascending=[True, True, False])
        df = df.drop_duplicates(subset=['ad_id', 'date'], keep='first')

        logger.info(f"After deduplication: {len(df)} budget records")

        # Validate data
        self._validate_budgets(df)

        return df

    def _fetch_min_bids_from_postgres(
        self,
        country: int,
        categories: List[int]
    ) -> Dict[int, float]:
        """
        Fetch min_bid per category from PostgreSQL campaign_ad_price table.

        Queries PostgreSQL for authoritative min_bid values used by production.
        Calculation: min_bid = price_per_day / fact_impression (kopecks).

        Args:
            country: Country ID
            categories: List of category IDs

        Returns:
            Dict mapping category_id to min_bid (kopecks, float)
        """
        logger.info(f"Fetching min_bid from PostgreSQL: {self.config.postgres_database.host}:{self.config.postgres_database.port}/{self.config.postgres_database.database}")

        # Connect to PostgreSQL if not already connected
        self._connect_postgres()

        min_bids = {}

        try:
            with self.pg_client.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Build SQL query with parameterized values
                query = """
                    SELECT
                        cac.category_id,
                        cap.price_per_day,
                        cap.fact_impression,
                        cap.price_per_day::float / cap.fact_impression AS min_bid_kopecks
                    FROM public.campaign_ad_price cap
                    JOIN campaign_ad_category cac ON cap.campaign_ad_category_id = cac.id
                    WHERE cac.category_id = ANY(%s)
                      AND cac.country_id = %s
                      AND cap."default" = TRUE
                    ORDER BY cac.category_id;
                """

                logger.debug(f"Executing PostgreSQL query for categories={categories}, country={country}")
                cursor.execute(query, (categories, country))

                rows = cursor.fetchall()

                # Process results
                for row in rows:
                    category_id = row['category_id']
                    price_per_day = row['price_per_day']
                    fact_impression = row['fact_impression']
                    min_bid = row['min_bid_kopecks']

                    min_bids[category_id] = min_bid
                    logger.info(f"Category {category_id}: min_bid={min_bid:.4f} kopecks "
                                f"(from PostgreSQL: price_per_day={price_per_day}/fact_impression={fact_impression})")

                # Handle missing categories with fallback
                found_categories = set(min_bids.keys())
                missing_categories = set(categories) - found_categories

                if missing_categories:
                    fallback = self.config.simulation.min_bid_fallback
                    for category_id in missing_categories:
                        min_bids[category_id] = fallback
                        logger.warning(f"Category {category_id}: not found in PostgreSQL, using fallback={fallback} kopecks")

        except psycopg2.Error as e:
            logger.error(f"PostgreSQL query failed: {e}")
            # Use fallback for all categories on error
            fallback = self.config.simulation.min_bid_fallback
            for category_id in categories:
                min_bids[category_id] = fallback
            logger.warning(f"Using fallback min_bid={fallback} kopecks for all categories due to PostgreSQL error")

        return min_bids

    def _calculate_min_bids(
        self,
        country: int,
        categories: List[int],
        time_from: date,
        time_to: date
    ) -> Dict[int, float]:
        """
        Calculate min_bid per category from spending data.

        Uses dual query approach:
        1. Spending: Filtered to ads from feed_id='6500' in category
        2. Impressions: ALL feeds (no feed_id filter) to reflect actual cost

        Rationale: Ad spending covers impressions across all feeds, not just
        category feed. Using feed_id='6500' filter on impressions inflates
        min_bid by 5-10x, causing simulation overspending.

        Returns dict mapping category_id to min_bid (kopecks, float).
        """
        logger.info("Calculating min_bid per category...")

        min_bids = {}
        feed_filter_clause = self._get_feed_filter_clause()

        for category_id in categories:
            query = f"""
            WITH category_spending AS (
                SELECT
                    SUM(spending) as total_spending
                FROM analytics_reports.spendings_distributed
                WHERE
                    operationdate >= toDate('{time_from}')
                    AND operationdate <= toDate('{time_to}')
                    AND country_id = {country}
                    AND spending > 0
                    AND ad_id GLOBAL IN (
                        SELECT DISTINCT ad_id
                        FROM enriched_distributed
                        WHERE
                            data_chunk_date >= toDate('{time_from}')
                            AND data_chunk_date <= toDate('{time_to}')
                            AND country_id = {country}
                            AND category_id = {category_id}
                            AND component = 'listing'
                            AND screen != 'my_profile'
                            AND element = 'ad'
                            AND action = 'view'
                            {feed_filter_clause}
                            AND client != 'backend'
                            AND ad_id IS NOT NULL
                    )
            ),
            category_impressions AS (
                SELECT
                    COUNT(*) as paid_impressions
                FROM enriched_distributed i
                WHERE
                    data_chunk_date >= toDate('{time_from}')
                    AND data_chunk_date <= toDate('{time_to}')
                    AND country_id = {country}
                    AND category_id = {category_id}
                    AND campaign_show_ad = 'True'
                    AND component = 'listing'
                    AND screen != 'my_profile'
                    AND element = 'ad'
                    AND action = 'view'
                    AND client != 'backend'
            )
            SELECT
                s.total_spending,
                i.paid_impressions
            FROM category_spending s, category_impressions i
            """

            logger.debug(f"Calculating min_bid for category {category_id} using all-feeds reach")
            result = self._execute_query(query)

            if result and len(result) > 0:
                total_spending, paid_impressions = result[0]
                spending_azn = float(total_spending) / 100.0
                logger.debug(f"Category {category_id}: spending={total_spending} kopecks ({spending_azn:.2f} AZN), "
                            f"paid_impressions_all_feeds={paid_impressions}")

                if paid_impressions > 0 and total_spending > 0:
                    min_bid = float(total_spending) / float(paid_impressions)
                    min_bids[category_id] = min_bid
                    logger.info(f"Category {category_id}: min_bid={min_bid:.4f} kopecks "
                                f"(spending={spending_azn:.2f} AZN, impressions_all_feeds={paid_impressions})")
                    logger.debug(f"Category {category_id}: min_bid breakdown: "
                                f"{total_spending} / {paid_impressions} = {min_bid:.4f} kopecks")
                else:
                    # Use fallback
                    fallback = self.config.simulation.min_bid_fallback
                    min_bids[category_id] = fallback
                    logger.warning(f"Category {category_id}: no spending data, using fallback={fallback}")
            else:
                fallback = self.config.simulation.min_bid_fallback
                min_bids[category_id] = fallback
                logger.warning(f"Category {category_id}: query returned no results, using fallback={fallback}")

        return min_bids

    def _validate_impressions(self, df: pd.DataFrame):
        """Validate reach data quality."""
        # Check for required fields
        required_cols = ['category_id', 'ad_id', 'seller_id', 'date', 'hour',
                         'total_reach', 'organic_reach', 'raw_impressions', 'reach_timestamp']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Check for nulls
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            logger.warning(f"Found null values:\n{null_counts[null_counts > 0]}")

        # Check for negative values
        if (df['total_reach'] < 0).any():
            raise ValueError("Found negative total_reach")

        if (df['organic_reach'] < 0).any():
            raise ValueError("Found negative organic_reach")

        if (df['raw_impressions'] < 0).any():
            raise ValueError("Found negative raw_impressions")

        # Check organic_reach <= total_reach
        invalid = df[df['organic_reach'] > df['total_reach']]
        if len(invalid) > 0:
            logger.warning(f"Found {len(invalid)} records where organic_reach > total_reach")

        # Check reach <= raw_impressions (fundamental validation)
        invalid_reach = df[df['total_reach'] > df['raw_impressions']]
        if len(invalid_reach) > 0:
            raise ValueError(f"Found {len(invalid_reach)} records where reach > impressions (impossible)")

        # Check reach ratio is reasonable (30-95%)
        df['reach_ratio'] = df['total_reach'] / df['raw_impressions']
        unusual = df[(df['reach_ratio'] < 0.3) | (df['reach_ratio'] > 0.95)]
        if len(unusual) > 0:
            logger.warning(f"Found {len(unusual)} records with unusual reach ratio (<30% or >95%)")
            logger.debug(f"Sample unusual ratios:\n{unusual[['ad_id', 'total_reach', 'raw_impressions', 'reach_ratio']].head(10)}")

    def _validate_budgets(self, df: pd.DataFrame):
        """Validate budget data quality."""
        # Check for required fields
        required_cols = ['ad_id', 'seller_id', 'date', 'daily_budget', 'actual_spend']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Check for nulls
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            logger.warning(f"Found null values in budgets:\n{null_counts[null_counts > 0]}")

        # Check for negative budgets
        if (df['daily_budget'] < 0).any():
            logger.warning("Found negative daily_budget values")

        # Check for overspending
        overspend = df[df['actual_spend'] > df['daily_budget']]
        if len(overspend) > 0:
            logger.warning(f"Found {len(overspend)} records where actual_spend > daily_budget")

    def _save_to_cache(self, df: pd.DataFrame, cache_key: str):
        """Save DataFrame to cache as parquet."""
        cache_path = self._get_cache_path(cache_key)
        df.to_parquet(cache_path, index=False)
        logger.info(f"Saved to cache: {cache_path}")

    def _load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Load DataFrame from cache if valid."""
        cache_path = self._get_cache_path(cache_key)

        if self._is_cache_valid(cache_path):
            logger.info(f"Loading from cache: {cache_path}")
            return pd.read_parquet(cache_path)

        return None
