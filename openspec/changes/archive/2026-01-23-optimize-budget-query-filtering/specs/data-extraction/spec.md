# data-extraction Specification Delta

## MODIFIED Requirements

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
- **THEN** query structure includes subquery filter to only extract budgets for ads present in selected categories (50x data reduction):
```sql
SELECT
    ad_id,
    user_id as seller_id,
    operationdate as date,
    price_per_day as daily_budget,
    spending as actual_spend,
    campaign_id
FROM analytics_reports.spendings_distributed
WHERE
    operationdate >= toDate('{time_from}')
    AND operationdate <= toDate('{time_to}')
    AND country_id = {country}
    AND ad_id IN (
        SELECT DISTINCT ad_id
        FROM enriched_distributed
        WHERE
            data_chunk_date >= toDate('{time_from}')
            AND data_chunk_date <= toDate('{time_to}')
            AND country_id = {country}
            AND category_id IN ({categories_str})
            AND feed_id = '6500'
            AND ad_type = '1'
            AND client != 'backend'
            AND ad_id IS NOT NULL
    )
ORDER BY ad_id, date, campaign_id DESC
```
- **OPTIMIZATION**: ClickHouse evaluates subquery first (~1,000 ad_ids), then filters spendings_distributed using ad_id index
- **PERFORMANCE**: Query executes 5-10x faster, transfers 50x less data, creates 10x smaller cache files

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

## REMOVED Requirements

None. This is an optimization that modifies existing query logic without removing functionality.
