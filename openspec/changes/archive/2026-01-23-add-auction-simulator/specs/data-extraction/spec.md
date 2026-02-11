## ADDED Requirements

### Requirement: Historical Total Impression Data Extraction with Runtime Filters
The system SHALL extract ALL impression events (both paid and organic) from ClickHouse for a specified time range and filters.

#### Scenario: Extract with runtime parameters
- **WHEN** extraction is run with country=13, categories=[1234, 5678], time_from="2024-01-15 00:00", time_to="2024-01-15 23:59"
- **THEN** all impressions matching these filters are returned, including both paid (is_paid=true) and organic (is_paid=false)

#### Scenario: Extract multiple days
- **WHEN** time_from="2024-01-15 00:00" and time_to="2024-01-17 23:59"
- **THEN** impressions for 3 full days (15th, 16th, 17th) are returned

#### Scenario: Filter category feed only
- **WHEN** extracting impressions
- **THEN** only impressions from category feed (not search, not filtered views) are included

#### Scenario: Group by category, day, and hour
- **WHEN** impressions are extracted
- **THEN** results are grouped by category_id, date (YYYY-MM-DD), and hour (0-23) with total counts per group

#### Scenario: Extract includes both paid and organic
- **WHEN** extracting impressions for category 1234, day 2024-01-15, hour 10
- **THEN** result includes total_impressions count (e.g., 5000) combining both paid and organic impressions from that hour

#### Scenario: Aggregate total impressions for simulation
- **WHEN** preparing data for simulation
- **THEN** for each (category_id, date, hour) tuple, calculate total_impressions = COUNT(*) from all impression events (both paid and organic)
- **AND** this total_impressions count becomes the fixed volume that simulation must redistribute in that hour
- **EXAMPLE**: If category 1234 had 500 paid + 200 organic = 700 total impressions at hour 10, simulation runs auction for exactly 700 slots

#### Scenario: Extract per-ad historical organic impression counts
- **WHEN** extracting impression data for fallback distribution
- **THEN** for each ad_id, calculate organic_impressions_historical = COUNT(*) WHERE is_paid=false (campaign_show_ad != 'True')
- **PURPOSE**: Used for proportional distribution when all paid budgets exhausted but slots remain in simulation
- **NOTE**: Historical organic (is_paid=false yesterday) is separate concept from simulated organic (budget=0 today). An ad with budget=0 today may have had paid impressions historically. We use historical organic counts purely as proxy for quality/relevance in fallback distribution.
- **EXAMPLE**: Ad A had 100 historical organic impressions (is_paid=false), Ad B had 50 → if 300 slots remain in simulation, distribute 200 to A, 100 to B (proportional to 100:50 ratio)

### Requirement: Ad and Seller Metadata Extraction
The system SHALL extract ad and seller metadata from ClickHouse impression data. No separate metadata tables are required in MVP.

#### Scenario: Derive ads from impressions
- **WHEN** extracting impressions for simulation period
- **THEN** unique ad_id, seller_id, category_id tuples are derived directly from impression events

#### Scenario: All ads from period eligible
- **WHEN** building ad list for auction
- **THEN** all ads that had impressions in the selected period (time_from to time_to) and categories are included, no Reach Profile filtering applied
- **SCOPE**: "All ads" means ads present in enriched_distributed for specified filters, NOT all ads in system
- **EXAMPLE**: If country=13, categories=[1234], time_from=2024-01-15, only ads with impressions matching these filters are included

### Requirement: Daily Budget Extraction from Campaign MS
The system SHALL extract daily campaign budgets for each ad for each day in the simulation time range.

#### Scenario: Extract daily budget for single day
- **WHEN** querying campaigns for ad_id=12345, date=2024-01-15
- **THEN** return daily_budget from the campaign record created for that ad on that date

#### Scenario: Extract daily budgets for multi-day range
- **WHEN** querying campaigns for ad_id=12345, time_from=2024-01-15, time_to=2024-01-17
- **THEN** return separate daily_budget values for each date (15th, 16th, 17th)

#### Scenario: Ad has no campaign for a day
- **WHEN** querying campaigns for ad_id=12345, date=2024-01-15 and no campaign exists
- **THEN** return daily_budget=0 for that ad on that date

#### Scenario: Campaign budgets reset daily
- **WHEN** ad has daily_budget=10 on 2024-01-15
- **THEN** on 2024-01-16, a new campaign record exists with fresh daily_budget (e.g., 10 again)

### Requirement: Category min_bid Calculation
The system SHALL calculate min_bid per category from actual spending data within the same simulation time range (time_from to time_to).

#### Scenario: Calculate min_bid for category from same period
- **WHEN** simulating period 2024-01-15 to 2024-01-17, category 1234
- **THEN** min_bid for category 1234 = total_spending_cat / total_paid_impressions_cat from same period
- **DATA SOURCE**: Use spendings_distributed as single source of truth:
  - Numerator: SUM(spending) WHERE spending > 0 for category
  - Denominator: COUNT of paid impressions from spendings_distributed (exact field name depends on schema - see implementation note)
- **IMPLEMENTATION NOTE**: Schema verification required before implementation:
  - Check if spendings_distributed has direct impressions count field (e.g., `impressions_count`, `paid_impressions`, or similar)
  - If not available, may need to join with enriched_distributed on (ad_id, operationdate) to get paid impression counts, but this creates cross-table dependency
  - **PREFERRED**: Use single table (spendings_distributed) if impression counts available
  - **FALLBACK**: Document cross-table dependency if join required
- **QUERY LOGIC (schema-dependent)**:
  ```sql
  -- Option A: if spendings_distributed has impressions_count field
  SELECT
    SUM(spending) as total_spending,
    SUM(impressions_count) as total_paid_impressions
  FROM spendings_distributed
  WHERE operationdate >= :time_from AND operationdate <= :time_to
    AND country_id = :country
    AND category_id = :category
    AND spending > 0

  -- Option B: if join required (less preferred)
  SELECT
    SUM(s.spending) as total_spending,
    COUNT(DISTINCT i.impression_id) as total_paid_impressions
  FROM spendings_distributed s
  JOIN enriched_distributed i ON i.ad_id = s.ad_id AND i.data_chunk_date = s.operationdate
  WHERE s.operationdate >= :time_from AND s.operationdate <= :time_to
    AND s.country_id = :country
    AND i.category_id = :category
    AND s.spending > 0
    AND i.campaign_show_ad = 'True'
  ```
- **EXAMPLE**: If category 1234 had SUM(spending)=5000 kopecks and 10000 paid impressions → min_bid = 0.5 kopecks per impression

#### Scenario: Category with no spending
- **WHEN** category has 0 total spending (SUM(spending)=0) in the simulation period
- **THEN** min_bid defaults to global average across all categories with spending, or configurable fallback value (e.g., 100 kopecks = 1.0 currency)

#### Scenario: Currency handling
- **WHEN** calculating min_bid
- **THEN** all values are kept in kopecks (integer) for precision, converted to currency units only for reporting
- **CURRENCY DEFINITIONS**:
  - **Storage unit**: kopeck (smallest denomination, 1/100 of currency unit)
  - **Example**: 100 kopecks = 1.00 AZN (for Azerbaijan), 100 kopecks = 1.00 UAH (for Ukraine)
  - **All monetary fields** use kopecks internally:
    - `daily_budget` (from price_per_day): integer kopecks
    - `spending` (from spendings_distributed): integer kopecks
    - `remaining_budget`: integer kopecks (runtime)
    - `actual_spend`: integer kopecks (runtime)
    - `min_bid`: float kopecks (can be fractional, e.g., 0.5 kopecks)
    - `bid_step`: float kopecks (default 0.1)
    - `effective_bid`: float kopecks
  - **Conversion for reporting**: divide by 100 and format with 2 decimal places (e.g., 5000 kopecks → "50.00 AZN")
  - **Precision**: Use floating point for bid calculations, round to integer kopecks when deducting from budgets

### Requirement: Data Validation
The system SHALL validate extracted data for completeness and correctness before passing to simulation.

#### Scenario: Detect missing required fields
- **WHEN** an impression record has null ad_id or category_id
- **THEN** log a validation error and exclude that record from simulation

#### Scenario: Detect budget inconsistencies
- **WHEN** a seller has actual_spending > plan_budget in historical data
- **THEN** log a warning but allow simulation to proceed (use actual data as-is)

### Requirement: Local Caching
The system SHALL cache extracted data locally to avoid repeated database queries during development and testing.

#### Scenario: Save extracted data to local cache
- **WHEN** data is successfully extracted from databases
- **THEN** save impressions, ads, budgets, and Reach configs as local files (parquet or pickle format)

#### Scenario: Load from cache if available
- **WHEN** simulation is run with same date and cache exists
- **THEN** load data from local cache instead of querying databases

#### Scenario: Cache invalidation
- **WHEN** user specifies --no-cache flag or cache is older than 24 hours
- **THEN** ignore cache and re-extract data from databases

### Requirement: SQL Implementation Details
The system SHALL use ClickHouse tables with specific field mappings and optimizations for efficient data extraction.

#### Scenario: Timezone handling
- **WHEN** extracting timestamps from ClickHouse
- **THEN** all timestamps are in UTC timezone (no conversion needed)

#### Scenario: Use data_chunk_date for joins
- **WHEN** joining impressions with campaign budgets
- **THEN** use `data_chunk_date` field directly (pre-normalized date partition key) instead of `toDate(timestamp)` for better performance

#### Scenario: Extract impressions from enriched_distributed
- **WHEN** extracting impression events
- **THEN** query structure:
```sql
SELECT
    category_id,
    ad_id,
    user_id as seller_id,
    country_id,
    CASE WHEN campaign_show_ad = 'True' THEN true ELSE false END as is_paid,
    toStartOfHour(timestamp) as hour,
    data_chunk_date as date
FROM enriched_distributed
WHERE
    data_chunk_date >= :time_from
    AND data_chunk_date <= :time_to
    AND country_id = :country
    AND feed_id = '6500'  -- category feed only
    AND ad_type = '1'
    AND client != 'backend'
    AND ad_id IS NOT NULL
    AND category_id IN (:categories)
```

#### Scenario: Extract campaign budgets from spendings_distributed
- **WHEN** extracting daily budgets and spending
- **THEN** query structure:
```sql
SELECT
    ad_id,
    user_id as seller_id,
    operationdate as date,
    price_per_day as daily_budget,  -- in kopecks
    spending as actual_spend,       -- in kopecks
    campaign_id,
    country_id
FROM analytics_reports.spendings_distributed
WHERE
    operationdate >= :time_from
    AND operationdate <= :time_to
    AND country_id = :country
```

#### Scenario: Join impressions with budgets using data_chunk_date
- **WHEN** building combined dataset for simulation
- **THEN** join on `i.ad_id = s.ad_id AND i.data_chunk_date = s.operationdate` for optimal performance
- **JOIN TYPE**: LEFT JOIN from impressions to spendings (impression is primary, budget may be missing → defaults to 0)
- **DEDUPLICATION**: If multiple campaign records exist for same (ad_id, operationdate), use latest by campaign_id or timestamp
- **AGGREGATION ORDER**:
  1. Extract impressions: GROUP BY (category_id, ad_id, data_chunk_date, hour) → total_impressions, organic_impressions
  2. Extract budgets: GROUP BY (ad_id, operationdate) → daily_budget (handle duplicates)
  3. Join: impressions LEFT JOIN budgets ON (ad_id, date)
- **EXAMPLE QUERY**:
  ```sql
  WITH impressions_agg AS (
    SELECT
      category_id,
      ad_id,
      data_chunk_date,
      toStartOfHour(timestamp) as hour,
      COUNT(*) as total_impressions,
      SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as organic_impressions
    FROM enriched_distributed
    WHERE [filters]
    GROUP BY category_id, ad_id, data_chunk_date, hour
  ),
  budgets_dedup AS (
    SELECT
      ad_id,
      operationdate,
      price_per_day as daily_budget,
      spending as actual_spend,
      ROW_NUMBER() OVER (PARTITION BY ad_id, operationdate ORDER BY campaign_id DESC) as rn
    FROM spendings_distributed
    WHERE [filters]
  )
  SELECT i.*, COALESCE(b.daily_budget, 0) as daily_budget, COALESCE(b.actual_spend, 0) as actual_spend
  FROM impressions_agg i
  LEFT JOIN budgets_dedup b ON i.ad_id = b.ad_id AND i.data_chunk_date = b.operationdate AND b.rn = 1
  ```
