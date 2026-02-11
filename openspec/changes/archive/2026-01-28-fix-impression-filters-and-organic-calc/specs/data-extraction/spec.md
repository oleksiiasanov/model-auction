# data-extraction Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
