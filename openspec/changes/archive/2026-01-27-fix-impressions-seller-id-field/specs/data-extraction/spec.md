# data-extraction Spec Delta

## MODIFIED Requirements

### Requirement: SQL Implementation Details

The system SHALL use ClickHouse tables with specific field mappings and optimizations for efficient data extraction, using correct seller identification fields.

#### Scenario: Extract impressions from enriched_distributed

- **WHEN** extracting impression events
- **THEN** query structure uses `lister_user_id` as the seller identifier (NOT `user_id`):
```sql
SELECT
    category_id,
    ad_id,
    lister_user_id as seller_id,  -- ✅ Correct field: ad owner/seller
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
GROUP BY category_id, ad_id, lister_user_id, date, hour  -- ✅ Group by actual seller
```
- **FIELD SEMANTICS**:
  - `lister_user_id`: The owner/seller of the ad (constant per ad_id, never NULL)
  - `user_id`: The viewer who saw the impression (changes per impression, can be NULL)
- **RATIONALE**: Using `user_id` creates duplicate records (one ad appears with multiple seller_ids), inflating "Ads with Impressions" metrics by 13x. `lister_user_id` correctly identifies the ad owner and remains constant.

#### Scenario: Validate seller_id field correctness

- **WHEN** extracting impressions with lister_user_id as seller_id
- **THEN** the following validations SHALL pass:
  1. **No NULL seller_id**: All records have non-NULL lister_user_id
  2. **Constant per ad**: Each ad_id has exactly one lister_user_id value across all time periods
  3. **No duplication**: COUNT(DISTINCT (ad_id, seller_id)) ≈ COUNT(DISTINCT ad_id) within ~1-5% tolerance
- **ANTI-PATTERN**: Using `user_id as seller_id` causes:
  - 10.6% NULL seller_id values (when user_id is NULL)
  - 13x duplication: 108,060 unique (ad_id, seller_id) pairs vs 8,393 unique ads
  - Up to 125 different "seller_id" values for a single ad
  - Metrics showing 102,881 ads instead of realistic ~8,393

#### Scenario: Extract campaign budgets with seller field

- **WHEN** extracting daily budgets and spending from spendings_distributed
- **THEN** query SHALL use `user_id as seller_id`:
- **NOTE**: spendings_distributed does NOT have `lister_user_id` column - only `user_id` is available
- **SEMANTICS**: In spendings_distributed, `user_id` represents the advertiser/campaign owner (seller), not the viewer
```sql
SELECT
    ad_id,
    user_id as seller_id,  -- ✅ In this table, user_id = seller/advertiser
    operationdate as date,
    price_per_day as daily_budget,
    spending as actual_spend,
    campaign_id
FROM analytics_reports.spendings_distributed
WHERE
    operationdate >= toDate('{time_from}')
    AND operationdate <= toDate('{time_to}')
    AND country_id = {country}
    AND ad_id GLOBAL IN (...)
ORDER BY ad_id, date, campaign_id DESC
```
- **TABLE DIFFERENCES**:
  - enriched_distributed: has both `user_id` (viewer) and `lister_user_id` (seller) → use `lister_user_id`
  - spendings_distributed: has only `user_id` which represents the seller/advertiser → use `user_id`
- **JOIN COMPATIBILITY**: Both tables provide seller_id, enabling joins on (ad_id, seller_id) or ad_id alone

## ADDED Requirements

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
