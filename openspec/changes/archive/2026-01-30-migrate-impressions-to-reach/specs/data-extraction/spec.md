# Spec Delta: Migrate Impressions to Reach (Data Extraction)

**Capability**: data-extraction
**Change**: migrate-impressions-to-reach

---

## MODIFIED Requirements

### Requirement: Historical Total Reach Data Extraction with Runtime Filters

The system SHALL extract REACH (unique users per day per ad) from ClickHouse, **not raw impressions**, for accurate auction simulation.

**TERMINOLOGY CHANGE:**
- **OLD**: Impression = any ad view event
- **NEW**: Reach = unique user_id viewing ad_id per day

**RATIONALE**: Real-world auction charges per unique user reach, not per repeat impression. Counting all impressions inflates traffic volume 1.5-2.5x.

#### Scenario: Calculate reach as unique users per ad per day

- **WHEN** extracting ad view data for simulation
- **THEN** calculate reach = `COUNT(DISTINCT user_id)` grouped by `(date, ad_id, seller_id, hour)`
- **RATIONALE**:
  - Same user viewing same ad multiple times = 1 reach
  - Deduplication occurs within day boundary
  - Each ad gets separate reach count
- **EXAMPLE**:
  - User 33 views ad_id=1 at 09:00 and 14:00 on 2026-05-15
  - Raw impressions: 2
  - Reach: 1 (unique user 33 on ad 1 that day)

#### Scenario: Track reach timestamp as first view

- **WHEN** calculating reach for ad+user combination
- **THEN** record `reach_timestamp = MIN(timestamp)` as the time of first view in that day
- **PURPOSE**: Determines which hour the reach occurred for slot allocation
- **EXAMPLE**:
  - User 33 views ad_id=1 at 09:00, 14:00, 22:00 on same day
  - reach_timestamp = 09:00 (first view)
  - This reach counts in hour 9 batch

#### Scenario: Filter NULL user_id values

- **WHEN** calculating reach
- **THEN** exclude events where `user_id IS NULL`
- **RATIONALE**: Cannot deduplicate without user_id
- **VALIDATION**: Check NULL rate < 5% before simulation

#### Scenario: Preserve raw impressions for comparison

- **WHEN** extracting reach data
- **THEN** also calculate `raw_impressions = COUNT(*)` for validation
- **PURPOSE**:
  - Compare reach vs impression counts
  - Validate reasonable ratio (reach/impressions = 40-80% typical)
  - Debug data quality issues

#### Scenario: Calculate organic reach (not organic impressions)

- **WHEN** extracting historical organic data for fallback
- **THEN** calculate `organic_reach = COUNT(DISTINCT user_id WHERE is_paid=false)`
- **GROUP BY**: `(date, ad_id)`
- **PURPOSE**: Proportional fallback uses organic reach, not impressions
- **PREVIOUS**: Used `organic_impressions = COUNT(*)`

#### Scenario: Group by ad and hour for deduplication

- **WHEN** running extraction query
- **THEN** `GROUP BY date, hour, seller_id, ad_id, category_id`
- **EFFECT**: Deduplicates user_id within each ad+hour combination
- **EXAMPLE**:
  ```sql
  SELECT
      data_chunk_date as date,
      toHour(timestamp) as hour,
      ad_id,
      lister_user_id as seller_id,
      COUNT(DISTINCT user_id) as reach,
      MIN(timestamp) as reach_timestamp,
      COUNT(*) as raw_impressions
  FROM enriched_distributed
  WHERE user_id IS NOT NULL
  GROUP BY date, hour, ad_id, lister_user_id
  ```

#### Scenario: Validate reach < impressions invariant

- **WHEN** extraction completes
- **THEN** verify `reach <= raw_impressions` for all ads
- **AND** warn if ratio < 0.3 or > 0.9 (unusual patterns)
- **TYPICAL RATIO**: 40-80% (reach is 40-80% of impressions)

---

## MODIFIED Requirements

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

## Implementation Notes

### SQL Changes

**File**: `src/auction_simulator/data_extraction.py`

**Line ~240-264** (`fetch_ads_from_clickhouse`):
```sql
-- BEFORE:
SELECT
    ...
    COUNT(*) as total_impressions,
    SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
FROM enriched_distributed
GROUP BY category_id, ad_id, lister_user_id, date, hour

-- AFTER:
SELECT
    ...
    COUNT(DISTINCT user_id) as reach,
    MIN(timestamp) as reach_timestamp,
    COUNT(*) as raw_impressions,
    COUNT(DISTINCT CASE WHEN campaign_show_ad != 'True' THEN user_id END) as organic_reach
FROM enriched_distributed
WHERE user_id IS NOT NULL  -- NEW
GROUP BY category_id, ad_id, lister_user_id, date, hour
```

### Data Structure

**Return format:**
```python
{
    'ad_id': 123,
    'seller_id': 456,
    'category_id': 1361,
    'reach': 450,  # was: total_impressions
    'reach_timestamp': datetime(...),  # NEW
    'raw_impressions': 680,  # was: total_impressions (renamed)
    'organic_reach': 120,  # was: organic_impressions
}
```

### Validation Query

```sql
-- Check reach/impression ratio
SELECT
    ad_id,
    COUNT(*) as impressions,
    COUNT(DISTINCT user_id) as reach,
    (reach * 100.0 / impressions) as reach_pct
FROM enriched_distributed
WHERE data_chunk_date = '2026-01-22'
  AND country_id = 13
GROUP BY ad_id
HAVING reach_pct < 30 OR reach_pct > 90;  -- Flag anomalies
```

---

## Cross-References

- **Related change**: `auction-engine` spec also updated with reach terminology
- **Data dependency**: Requires `user_id` field in `enriched_distributed` table

---

## Revision History

- **2026-01-30**: Initial spec delta (migrate-impressions-to-reach)
