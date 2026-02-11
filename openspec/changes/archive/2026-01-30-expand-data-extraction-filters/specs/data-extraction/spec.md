# Spec Delta: Expand Data Extraction Filters

**Capability**: data-extraction
**Change**: expand-data-extraction-filters

---

## MODIFIED Requirements

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

## Implementation Notes

### Code Location

**File**: `src/auction_simulator/data_extraction.py`

**Changes applied:**

1. **Lines ~259-260** (`fetch_ads_from_clickhouse`):
   ```python
   AND feed_id IN ('6500', '6002')  # was: '6500'
   # ad_type = '1' filter removed
   ```

2. **Lines ~326-327** (`fetch_actual_spending_from_clickhouse`):
   ```python
   AND feed_id IN ('6500', '6002')  # was: '6500'
   # ad_type = '1' filter removed
   ```

3. **Lines ~484-485** (`calculate_min_bid_per_category` spending):
   ```python
   AND feed_id IN ('6500', '6002')  # was: '6500'
   # ad_type = '1' filter removed
   ```

4. **Line ~503** (`calculate_min_bid_per_category` impressions):
   ```python
   # ad_type = '1' filter removed
   # (no feed_id filter here by design - counts ALL impressions)
   ```

### Documentation

Documentation comment added at line ~259:
```python
-- Filter expansions for comprehensive data (change: expand-data-extraction-filters):
--   feed_id IN ('6500', '6002'): Include both category feed and additional feed
--   No ad_type filter: Include all ad types for complete simulation
```

---

## Cross-References

- **Related requirements**: All extraction requirements benefit from expanded filters
- **Data sources**: ClickHouse `enriched_distributed`, `impression_reach_events_distributed`

---

## Revision History

- **2026-01-30**: Initial spec delta (expand-data-extraction-filters)
