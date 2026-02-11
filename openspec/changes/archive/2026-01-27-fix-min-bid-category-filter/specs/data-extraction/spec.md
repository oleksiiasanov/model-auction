# data-extraction Specification Delta

## MODIFIED Requirements

### Requirement: Category min_bid Calculation

The system SHALL calculate min_bid per category from actual spending data within the same simulation time range (time_from to time_to), filtering BOTH spending and impressions by the specific category.

#### Scenario: Calculate min_bid for category from same period
- **WHEN** simulating period 2024-01-15 to 2024-01-17, category 1234
- **THEN** min_bid for category 1234 = total_spending_cat / total_paid_impressions_cat from same period
- **AND** total_spending_cat includes ONLY spending from ads belonging to category 1234
- **AND** total_paid_impressions_cat includes ONLY paid impressions from ads in category 1234
- **DATA SOURCE**: Use cross-table query with category filter on both sides:
  - **Numerator (spending)**: SUM(spending) from spendings_distributed WHERE ad_id IN (ads from category)
  - **Denominator (impressions)**: COUNT of paid impressions from enriched_distributed WHERE category_id = target_category
- **QUERY STRUCTURE**:
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
              AND feed_id = '6500'
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
        AND feed_id = '6500'
        AND ad_type = '1'
        AND client != 'backend'
  )
  SELECT s.total_spending, i.paid_impressions
  FROM category_spending s, category_impressions i
  ```
- **DISTRIBUTED TABLES**: Use GLOBAL IN keyword when filtering spending by category-specific ad_ids (prevents "DISTRIBUTED_IN_JOIN_SUBQUERY_DENIED" error)
- **EXAMPLE**:
  - Category 1361 has SUM(spending)=7,450 kopecks (from category ads only) and 9,735 paid impressions → min_bid = 0.77 kopecks per impression ✅
  - **INCORRECT**: Taking all country spending (452,153 kopecks) / category impressions (1,363) → min_bid = 331.73 kopecks ❌

#### Scenario: Validate category filter correctness
- **WHEN** calculating min_bid for category 1234
- **THEN** system SHALL verify spending includes only ads where ad_id appears in enriched_distributed with category_id=1234
- **AND** log total_spending, paid_impressions, and calculated min_bid for debugging
- **VERIFICATION**: Simulated spending should be within 50-200% of actual spending (not 900%)

#### Scenario: Category with no spending
- **WHEN** category has 0 total spending (SUM(spending)=0) in the simulation period
- **THEN** min_bid defaults to global average across all categories with spending, or configurable fallback value (e.g., 100 kopecks = 1.0 currency)
- **AND** system logs warning about using fallback min_bid

#### Scenario: Category with no paid impressions
- **WHEN** category has paid_impressions=0 but spending>0 (edge case: spending without impressions)
- **THEN** min_bid defaults to configurable fallback value
- **AND** system logs warning about data inconsistency

#### Scenario: Currency handling
- **WHEN** calculating min_bid
- **THEN** all values are kept in kopecks (integer spending, float min_bid) for precision, converted to currency units only for reporting
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

## REMOVED Requirements

None. This change modifies the implementation approach for existing min_bid calculation requirement without removing functionality.
