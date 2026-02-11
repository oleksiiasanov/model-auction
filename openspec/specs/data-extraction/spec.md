# data-extraction Specification

## Purpose
TBD - created by archiving change add-auction-simulator. Update Purpose after archive.
## Requirements
### Requirement: Historical Total Impression Data Extraction with Runtime Filters

The system SHALL extract ALL impression events from ClickHouse for a specified time range and filters, **including multiple feed sources and all ad types** for comprehensive coverage.

#### Scenario: Include multiple feeds (6500 and 6002)

- **WHEN** extracting impressions from `enriched_distributed`
- **THEN** filter using `feed_id IN ('6500', '6002')`
- **RATIONALE**:
  - Feed 6500 = Category feed (primary)
  - Feed 6002 = Additional ad feed (supplementary)
  - Both feeds contain ads relevant for simulation
- **PREVIOUS**: `feed_id = '6500'` only
- **IMPACT**: Expands data to include feed 6002 ads

#### Scenario: Include all ad types (no ad_type restriction)

- **WHEN** extracting impressions, spending, or calculating min_bid
- **THEN** do NOT filter by `ad_type`
- **RATIONALE**:
  - All ad types participate in auction ecosystem
  - Type-specific filtering excludes valid ads
  - Simulation should reflect complete ad landscape
- **PREVIOUS**: `ad_type = '1'` filter excluded other types
- **IMPACT**: Includes all ad_type values

### Requirement: Ad and Seller Metadata Extraction

The system SHALL extract ad and seller metadata from impression data **across multiple feed sources and all ad types**.

#### Scenario: Expanded feed sources for metadata

- **WHEN** deriving ad_id, seller_id, category_id from impressions
- **THEN** include data from `feed_id IN ('6500', '6002')`
- **CONSISTENCY**: Matches impression extraction filters

#### Scenario: All ad types included in metadata

- **WHEN** building ad list for simulation
- **THEN** do NOT filter by ad_type
- **RESULT**: Complete ad catalog regardless of type

---

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

The system SHALL calculate min_bid as `spending / reach`, **not spending / impressions**.

#### Scenario: Min bid formula uses reach denominator

- **WHEN** calculating min_bid per category
- **THEN** `min_bid = total_spending / paid_reach`
- **WHERE**: `paid_reach = COUNT(DISTINCT user_id)` from impressions query
- **PREVIOUS**: `min_bid = total_spending / total_impressions` (inflated denominator)
- **IMPACT**: min_bid increases by 1.5-2.5x (smaller denominator = higher per-reach cost)

#### Scenario: Impressions query uses reach

- **WHEN** counting impressions for min_bid calculation
- **THEN** query: `SELECT COUNT(DISTINCT user_id) as paid_reach FROM ...`
- **CONSISTENCY**: Matches ad extraction reach logic

---

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

The system SHALL use ClickHouse tables with correct event filtering and NULL handling for accurate impression metrics.

#### Scenario: Extract only impression view events from enriched_distributed

- **WHEN** extracting impression data
- **THEN** query SHALL filter for impression view events specifically:
```sql
SELECT
    category_id,
    ad_id,
    lister_user_id as seller_id,
    data_chunk_date as date,
    toHour(timestamp) as hour,
    COUNT(*) as total_impressions,
    SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
FROM enriched_distributed
WHERE
    data_chunk_date >= :time_from
    AND data_chunk_date <= :time_to
    AND country_id = :country
    AND category_id IN (:categories)
    AND component = 'listing'       -- ✅ Event from listing page
    AND screen != 'my_profile'      -- ✅ Exclude profile views
    AND element = 'ad'              -- ✅ Element is an ad
    AND action = 'view'             -- ✅ Action is view (impression)
    AND ad_type = '1'               -- Standard ad type
    AND feed_id = '6500'            -- Category feed
    AND client != 'backend'         -- Exclude backend events
    AND ad_id IS NOT NULL
GROUP BY category_id, ad_id, lister_user_id, date, hour
```
- **RATIONALE**: enriched_distributed contains ALL platform events (clicks, scrolls, profile views, etc.), not just impressions. Without event-specific filters, query extracts non-impression events.
- **IMPACT**:
  - Without filters: 332,952 events extracted
  - With filters: 313,977 events extracted (6% reduction)
  - Ensures accurate impression counts for simulation

#### Scenario: Handle NULL campaign_show_ad as organic impressions

- **WHEN** calculating organic impressions
- **THEN** NULL campaign_show_ad SHALL be treated as organic (same as 'False'):
```sql
-- WRONG (excludes NULL in ClickHouse):
SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as organic_impressions

-- CORRECT (includes NULL):
SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
```
- **CLICKHOUSE NULL SEMANTICS**:
  - The `!= 'True'` operator does NOT match NULL values in ClickHouse
  - NULL == NULL returns NULL (not true), so `!= 'True'` excludes NULL rows
  - Must use `= 'True' THEN 0 ELSE 1` pattern to include NULL in the "else" branch
- **BUSINESS SEMANTICS**: NULL campaign_show_ad means free (organic) impression, not paid
- **IMPACT**:
  - campaign_show_ad distribution: False (255,914), NULL (48,628), True (9,435)
  - Wrong calculation: organic = 255,914 (excludes NULL) → paid = 58,063
  - Correct calculation: organic = 304,542 (includes NULL) → paid = 9,435
  - Wrong calculation inflates paid impressions by **6.2x**!

#### Scenario: Calculate min_bid with consistent impression filters

- **WHEN** calculating category min_bid
- **THEN** paid impressions query SHALL use same filters as impression extraction:
```sql
WITH category_impressions AS (
    SELECT COUNT(*) as paid_impressions
    FROM enriched_distributed
    WHERE data_chunk_date >= toDate('{time_from}')
      AND category_id = {category_id}
      AND campaign_show_ad = 'True'
      AND component = 'listing'      -- ✅ Consistent with extraction
      AND screen != 'my_profile'     -- ✅ Consistent with extraction
      AND element = 'ad'             -- ✅ Consistent with extraction
      AND action = 'view'            -- ✅ Consistent with extraction
      AND feed_id = '6500'
      AND ad_type = '1'
      AND client != 'backend'
)
SELECT total_spending / paid_impressions as min_bid
FROM category_spending, category_impressions
```
- **CONSISTENCY**: Both impression extraction and min_bid calculation must use identical filters
- **VALIDATION**: Paid impression count in min_bid calculation should match impression extraction

#### Scenario: Validate paid/organic ratio correctness

- **WHEN** extracting impressions with correct filters and NULL handling
- **THEN** the following metrics SHALL be realistic:
  - Organic impressions: ~97% of total (most impressions are free)
  - Paid impressions: ~3% of total (only campaign_show_ad = 'True')
  - Actual CPI from spending data: ~5-6 kopecks (realistic for platform)
  - Min_bid ≈ Actual CPI (both calculated from same paid impressions)
- **ANTI-PATTERN**:
  - If organic < 90%, likely missing NULL in calculation
  - If paid > 20%, likely including NULL as paid (wrong!)
  - If actual CPI << min_bid (e.g., 0.88 vs 5.6), paid impressions inflated

### Requirement: Field Semantics Documentation

The system SHALL clearly distinguish between viewer and seller identifiers in enriched_distributed table.

#### Scenario: Understand available user identifier fields

- **WHEN** querying enriched_distributed table
- **THEN** the following fields are available with distinct meanings:
  - `lister_user_id`: The user who owns/listed the ad (seller)
    - **Properties**: Non-NULL, constant per ad_id, identifies seller
    - **Usage**: Use for seller_id in auction simulation
  - `user_id`: The user who viewed the impression (viewer)
    - **Properties**: Can be NULL, changes per impression, identifies viewer
    - **Usage**: Use for audience analytics, NOT for seller tracking
- **INCORRECT USAGE**: Using `user_id` for seller_id violates business semantics (ads cannot transfer between sellers)

#### Scenario: Validate field choice in extraction queries

- **WHEN** writing extraction queries that need seller identification
- **THEN** always use `lister_user_id as seller_id`, never `user_id as seller_id`
- **VERIFICATION**: Run validation query to confirm lister_user_id is constant per ad:
  ```sql
  -- Should return 0 rows
  SELECT ad_id, COUNT(DISTINCT lister_user_id) as seller_count
  FROM enriched_distributed
  WHERE [filters]
  GROUP BY ad_id
  HAVING seller_count > 1
  ```

### Requirement: Impression Event Filtering

The system SHALL filter enriched_distributed events to include only impression views, excluding other platform events.

#### Scenario: Filter events by component, screen, element, and action

- **WHEN** querying enriched_distributed for any impression-related metric
- **THEN** apply ALL of these event filters:
  - `component = 'listing'`: Event occurred on listing/search page
  - `screen != 'my_profile'`: Exclude views on user's own profile
  - `element = 'ad'`: Event target is an advertisement
  - `action = 'view'`: Event type is a view (impression), not click/scroll/etc.
- **RATIONALE**: enriched_distributed is an event stream containing ALL user interactions:
  - Clicks on ads
  - Scrolls on listing page
  - Profile views
  - Ad impressions
  - Search queries
  - Without filters, query returns mixture of event types, not just impressions

#### Scenario: Combine event filters with category filters

- **WHEN** extracting category-specific impressions
- **THEN** apply both event filters AND category filters:
```sql
WHERE
    -- Time and geography
    data_chunk_date BETWEEN :time_from AND :time_to
    AND country_id = :country
    AND category_id IN (:categories)
    -- Impression event filters (required)
    AND component = 'listing'
    AND screen != 'my_profile'
    AND element = 'ad'
    AND action = 'view'
    -- Feed and ad type filters
    AND ad_type = '1'
    AND feed_id = '6500'
    AND client != 'backend'
```
- **ORDER MATTERS**: Category filters alone are insufficient; event filters are mandatory for accuracy

### Requirement: ClickHouse NULL Handling

The system SHALL account for ClickHouse's NULL semantics when using comparison operators.

#### Scenario: Understand != operator behavior with NULL

- **WHEN** using `field != 'value'` in ClickHouse
- **THEN** understand that NULL values are NOT included in the result:
  - `NULL != 'True'` evaluates to NULL (not true)
  - Rows with NULL are excluded from the result set
  - This differs from some other SQL databases where `NULL != 'value'` might include NULL
- **CORRECT PATTERN**: To include NULL in "not equal" logic:
```sql
-- To count non-True values (including NULL):
CASE WHEN field = 'True' THEN 0 ELSE 1 END

-- To count only True values (excluding NULL):
CASE WHEN field = 'True' THEN 1 ELSE 0 END
```

#### Scenario: Validate NULL handling in test queries

- **WHEN** testing organic/paid calculation logic
- **THEN** verify NULL handling with test query:
```sql
SELECT
    campaign_show_ad,
    COUNT(*) as row_count,
    SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as not_true_old,
    SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as not_true_new
FROM enriched_distributed
WHERE [filters]
GROUP BY campaign_show_ad
```
- **EXPECTED RESULTS**:
  - not_true_old (old method): excludes NULL rows, counts only 'False'
  - not_true_new (new method): includes NULL rows, counts 'False' + NULL
  - Difference reveals number of NULL rows mishandled by old method

### Requirement: Strict Category-Safe Budget Extraction
The system SHALL extract budget records only for the requested categories and exclude null/invalid category rows to prevent out-of-scope paid ads from entering simulation.

#### Scenario: Exclude out-of-scope categories
- **WHEN** simulation runs with `categories=[1361]`
- **AND** `spendings_distributed` contains budget rows for categories outside 1361
- **THEN** those rows are excluded from extracted budgets
- **AND** excluded rows are not counted in simulation budget totals

#### Scenario: Exclude null or zero category artifacts
- **WHEN** source data contains budget rows with `category_id IS NULL` or `category_id=0`
- **THEN** these rows are excluded from extracted budgets for category-scoped simulation
- **AND** they do not create paid ads with missing category in reports

### Requirement: Budget Records Carry Category Context
The system SHALL preserve category context for each extracted budget record so budget-only ads can be initialized in the correct category.

#### Scenario: Budget-only ad gets category assignment
- **WHEN** an ad has budget for selected category and no impressions in period
- **THEN** extracted budgets include `(ad_id, seller_id, category_id, date, daily_budget, actual_spend)`
- **AND** simulation can initialize that ad in the selected category

### Requirement: Budget Eligibility Is Not Gated by Impression Presence
The system SHALL include in-scope budget rows even when the same ad has zero impression rows in the selected period.

#### Scenario: In-scope budget row without impressions is kept
- **WHEN** an ad has `daily_budget > 0` for selected category/date
- **AND** the ad has no matching rows in `enriched_distributed` during that period
- **THEN** the budget row is still extracted
- **AND** the ad can be initialized as budget-only (cold-start) for paid auction participation

