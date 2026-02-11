# data-extraction Specification Changes

## MODIFIED Requirements

### Requirement: Category min_bid Calculation

The system SHALL calculate min_bid per category from actual spending data within the same simulation time range (time_from to time_to), filtering BOTH spending and impressions by the specific category, BUT using ALL feed_ids for impression count to reflect actual cost per impression.

#### Scenario: Calculate min_bid using all-feeds impressions

- **WHEN** calculating min_bid for category X
- **THEN** paid impressions SHALL include ALL feed_ids, not just feed_id='6500':
  - **Rationale**: Ad spending covers impressions from all feeds, not just category feed (6500)
  - **Without all-feeds**: Dividing spending by feed_id='6500' impressions only inflates min_bid by 5-10x
  - **With all-feeds**: Dividing by total paid impressions reflects actual cost per impression
- **EXAMPLE**:
  - Ad has 1000 paid impressions across all feeds
  - Only 100 impressions from feed_id='6500'
  - Total spending: 100 kopecks
  - **Wrong**: min_bid = 100 / 100 = 1.0 kopeck (inflated 10x) ❌
  - **Correct**: min_bid = 100 / 1000 = 0.1 kopeck ✅
- **IMPACT**: Prevents 9x simulated spending overshoot (4,888 AZN → closer to actual 539 AZN)

#### Scenario: Dual query approach for min_bid vs simulation

- **WHEN** extracting data for simulation
- **THEN** system SHALL use TWO different impression queries:
  1. **Min_bid calculation**: Query impressions WITHOUT feed_id filter
     - Purpose: Reflect actual cost per impression across all feeds
     - Query: `COUNT(*) WHERE campaign_show_ad = 'True' AND [impression filters]`
     - NO `feed_id = '6500'` filter
  2. **Simulation extraction**: Query impressions WITH feed_id='6500' filter
     - Purpose: Limit simulation scope to category feed only
     - Query: `COUNT(*) WHERE feed_id = '6500' AND [impression filters]`
     - Already implemented in `_extract_impressions()`
- **RATIONALE**: Min_bid must reflect real-world costs, but simulation scope is intentionally limited to specific feed
- **CONSISTENCY**: Both queries use same impression event filters (component, screen, element, action)

#### Scenario: Calculate min_bid for category from same period (UPDATED QUERY)

- **WHEN** simulating period 2024-01-15 to 2024-01-17, category 1234
- **THEN** min_bid for category 1234 = total_spending_cat / total_paid_impressions_all_feeds
- **QUERY STRUCTURE** (UPDATED):
  ```sql
  WITH category_spending AS (
      SELECT SUM(spending) as total_spending
      FROM analytics_reports.spendings_distributed
      WHERE operationdate >= toDate('{time_from}')
        AND operationdate <= toDate('{time_to}')
        AND country_id = {country}
        AND spending > 0
        AND ad_id GLOBAL IN (
            SELECT DISTINCT ad_id
            FROM enriched_distributed
            WHERE data_chunk_date >= toDate('{time_from}')
              AND data_chunk_date <= toDate('{time_to}')
              AND country_id = {country}
              AND category_id = {category_id}
              AND component = 'listing'
              AND screen != 'my_profile'
              AND element = 'ad'
              AND action = 'view'
              AND feed_id = '6500'         -- ✅ Keep for ad selection
              AND ad_type = '1'
              AND client != 'backend'
              AND ad_id IS NOT NULL
        )
  ),
  category_impressions AS (
      SELECT COUNT(*) as paid_impressions
      FROM enriched_distributed
      WHERE data_chunk_date >= toDate('{time_from}')
        AND data_chunk_date <= toDate('{time_to}')
        AND country_id = {country}
        AND category_id = {category_id}
        AND campaign_show_ad = 'True'
        AND component = 'listing'
        AND screen != 'my_profile'
        AND element = 'ad'
        AND action = 'view'
        -- ❌ NO feed_id = '6500' here! REMOVED to include all feeds
        AND ad_type = '1'
        AND client != 'backend'
  )
  SELECT s.total_spending, i.paid_impressions
  FROM category_spending s, category_impressions i
  ```
- **KEY CHANGE**: Removed `AND feed_id = '6500'` from `category_impressions` CTE
- **PRESERVED**: feed_id='6500' filter still in `category_spending` GLOBAL IN subquery for ad selection

#### Scenario: Validate min_bid reflects all-feeds cost

- **WHEN** calculating min_bid for category 1361, period 2026-01-22 to 2026-01-26
- **THEN** system SHALL log both impression counts for validation:
  - `paid_impressions_all_feeds`: COUNT without feed_id filter (used for min_bid)
  - `paid_impressions_feed_6500`: COUNT with feed_id='6500' (for comparison)
- **VALIDATION**: If inflation_ratio = impressions_feed_6500 / impressions_all_feeds < 0.2, then min_bid was inflated 5x or more
- **EXAMPLE**:
  - Category 1361: 9,435 impressions feed_id='6500', 58,063 impressions all feeds
  - Inflation ratio: 9,435 / 58,063 = 0.16 (6.2x inflation if using feed_id filter)
  - Min_bid with filter: 5.56 kopecks → without filter: 0.93 kopecks ✅

## ADDED Requirements

### Requirement: Feed-Specific Impression Filtering Context

The system SHALL document why different feed filters are used for min_bid calculation vs simulation extraction.

#### Scenario: Understand feed_id filtering strategy

- **WHEN** reviewing data extraction logic
- **THEN** understand that feed_id='6500' filter serves two different purposes:
  1. **Ad selection** (keep filter):
     - Identifies ads that belong to category feed
     - Used in spending query GLOBAL IN subquery
     - Purpose: Only include ads from category feed in analysis
  2. **Impression counting** (filter context-dependent):
     - **For simulation**: Include filter to limit simulation scope
     - **For min_bid**: Exclude filter to reflect actual impression costs
     - Purpose: Min_bid must match real-world costs across all feeds
- **BUSINESS CONTEXT**: Ads selected from feed_id='6500' receive impressions from multiple feeds (search, recommendations, category browse), and spending applies to ALL those impressions, not just category feed

#### Scenario: Prevent min_bid inflation from feed filtering

- **WHEN** filtering paid impressions by feed_id for min_bid calculation
- **THEN** system SHALL warn that this causes artificial min_bid inflation:
  - Ad spending covers impressions across ALL feeds
  - Filtering impressions by single feed creates denominator too small
  - Result: min_bid inflated by 5-10x, causing simulation overspending
- **ANTI-PATTERN**: Using feed_id filter in min_bid calculation
- **CORRECT PATTERN**: Use feed_id filter ONLY in ad selection subquery, NOT in impression count
