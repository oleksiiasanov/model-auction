# data-extraction Specification Changes

## MODIFIED Requirements

### Requirement: Category min_bid Calculation

The system SHALL fetch min_bid per category from PostgreSQL `campaign_ad_price` table instead of calculating from ClickHouse spending/impression data.

#### Scenario: Fetch min_bid from PostgreSQL by category and country

- **WHEN** extracting data for simulation
- **THEN** system SHALL query PostgreSQL for min_bid values:
  ```sql
  SELECT
      cac.category_id,
      cap.price_per_day,      -- kopecks (integer)
      cap.fact_impression,    -- impressions count
      cap.price_per_day::float / cap.fact_impression AS min_bid_kopecks
  FROM public.campaign_ad_price cap
  JOIN campaign_ad_category cac ON cap.campaign_ad_category_id = cac.id
  WHERE cac.category_id IN (:categories)
    AND cac.country_id = :country
    AND cap."default" = TRUE
  ORDER BY cac.category_id;
  ```
- **RATIONALE**: PostgreSQL stores authoritative min_bid values used by production ad system
- **BENEFIT**: Accurate min_bid (0.07 kopecks) vs inflated ClickHouse calculation (1.34 kopecks = 19x inflation)

#### Scenario: Calculate min_bid from PostgreSQL fields

- **WHEN** PostgreSQL query returns price_per_day and fact_impression
- **THEN** calculate min_bid: `price_per_day / fact_impression` (in kopecks)
- **EXAMPLE**:
  - price_per_day = 60 kopecks
  - fact_impression = 852
  - min_bid = 60 / 852 = 0.0704 kopecks per impression ✅
- **DATA TYPES**:
  - price_per_day: integer (kopecks) from PostgreSQL
  - fact_impression: integer (count) from PostgreSQL
  - min_bid: float (kopecks per impression) calculated in Python
- **CONSISTENCY**: Result is float kopecks, matching all other monetary calculations

#### Scenario: Handle missing categories with fallback

- **WHEN** category not found in PostgreSQL campaign_ad_price table
- **THEN** use fallback min_bid from config: `simulation.min_bid_fallback` (default: 100 kopecks)
- **AND** log warning: `"Category {id} not found in PostgreSQL, using fallback={value}"`
- **RATIONALE**: Graceful degradation, simulation can continue with reasonable default
- **EXAMPLE**: New category added to ClickHouse but not yet in PostgreSQL pricing

#### Scenario: Validate PostgreSQL min_bid vs ClickHouse calculation

- **WHEN** running simulation with PostgreSQL min_bid
- **THEN** simulated spending should be realistic:
  - **Before (ClickHouse)**: min_bid = 1.34 kopecks → spending = 4,863 AZN (9x actual)
  - **After (PostgreSQL)**: min_bid = 0.07 kopecks → spending ~540-800 AZN (1-1.5x actual) ✅
- **VALIDATION**: Simulated spending within 50-200% of actual spending
- **ANTI-PATTERN**: If simulated spending > 3x actual, min_bid likely wrong

#### Scenario: PostgreSQL connection configuration

- **WHEN** DataExtractor initializes
- **THEN** read PostgreSQL connection from `config.postgres_database`:
  - host: PostgreSQL server hostname
  - port: 5432 (default PostgreSQL port)
  - database: database name (default: "postgres")
  - user: read-only username
  - password: read-only password
  - connect_timeout: connection timeout in seconds
- **ERROR HANDLING**: If connection fails, log error and raise exception (fail fast)
- **CLEANUP**: Disconnect PostgreSQL client when DataExtractor destroyed

#### Scenario: Log min_bid source for transparency

- **WHEN** fetching min_bid from PostgreSQL
- **THEN** log at INFO level:
  - `"Fetching min_bid from PostgreSQL: {host}:{port}/{database}"`
  - `"Category {id}: min_bid={value:.4f} kopecks (price_per_day={p}/fact_impression={f})"`
- **WHEN** using fallback min_bid
- **THEN** log warning:
  - `"Category {id}: not found in PostgreSQL, using fallback={value} kopecks"`
- **PURPOSE**: Make min_bid source obvious in logs for debugging

## REMOVED Requirements

### Requirement: Calculate min_bid from ClickHouse spending data (DEPRECATED)

**Previous behavior:** Calculate min_bid from ClickHouse as `total_spending / paid_impressions`.

**Why removed:**
- ClickHouse calculation produced inflated min_bid (1.34 kopecks vs actual 0.07)
- Historical spending/impression ratio doesn't reflect current platform policy
- PostgreSQL stores authoritative min_bid values used by production system

**Migration:** All min_bid lookups now use PostgreSQL. ClickHouse only used for impression extraction and budget data.

**Code cleanup:** `_calculate_min_bids()` method can be removed after PostgreSQL integration validated.

## ADDED Requirements

### Requirement: PostgreSQL Database Connection

The system SHALL support PostgreSQL connection for min_bid lookup in addition to existing ClickHouse connection.

#### Scenario: Dual database architecture

- **WHEN** running simulation
- **THEN** system SHALL use:
  - **ClickHouse**: Impression data, budget data (analytics_reports.*)
  - **PostgreSQL**: Min_bid pricing data (campaign_ad_price, campaign_ad_category)
- **RATIONALE**: Each database serves its purpose:
  - ClickHouse: Fast analytical queries on large event data
  - PostgreSQL: Transactional data with authoritative pricing
- **BENEFIT**: Use strengths of each database, avoid complex ClickHouse calculation

#### Scenario: PostgreSQL query performance

- **WHEN** querying PostgreSQL for min_bid
- **THEN** query should complete in < 100ms (one query per simulation run)
- **CACHING**: Min_bid values cached in parquet files with other extracted data
- **FREQUENCY**: One PostgreSQL query per simulation run, not per hour/batch
- **IMPACT**: Minimal latency impact (< 1% of total extraction time)

#### Scenario: PostgreSQL read-only access

- **WHEN** connecting to PostgreSQL
- **THEN** use read-only user credentials
- **AND** only SELECT queries allowed (no INSERT, UPDATE, DELETE)
- **RATIONALE**: Simulation reads pricing data, never modifies it
- **SECURITY**: Read-only access prevents accidental data modification
