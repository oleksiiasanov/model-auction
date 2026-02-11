# Tasks: Fix Impression Filters and Organic Calculation

## Implementation Tasks

### 1. Add impression event filters to _extract_impressions()
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Method**: `_extract_impressions()` (lines 178-236)
- **Change**: Add impression-specific filters to WHERE clause:
  ```sql
  AND component = 'listing'
  AND screen != 'my_profile'
  AND element = 'ad'
  AND action = 'view'
  ```
- **Location**: After existing filters (after line 217, before GROUP BY)
- **Validation**: Query should return ~314k events instead of ~333k

### 2. Fix organic impressions calculation
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Method**: `_extract_impressions()` (line 207)
- **Change**: Update organic calculation to handle NULL correctly:
  ```sql
  -- FROM:
  SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as organic_impressions

  -- TO:
  SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
  ```
- **Rationale**: In ClickHouse, `!= 'True'` excludes NULL, but NULL = organic (free)
- **Validation**: Organic impressions should be ~304k instead of ~271k

### 3. Add impression filters to min_bid calculation
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Method**: `_calculate_min_bids()` (lines 316-394)
- **Change**: Add same impression filters to category_impressions CTE:
  ```sql
  WHERE data_chunk_date >= toDate('{time_from}')
    AND category_id = {category_id}
    AND campaign_show_ad = 'True'
    AND component = 'listing'          -- ✅ ADD
    AND screen != 'my_profile'         -- ✅ ADD
    AND element = 'ad'                 -- ✅ ADD
    AND action = 'view'                -- ✅ ADD
    AND feed_id = '6500'
    ...
  ```
- **Validation**: Paid impressions count should match impressions extraction

### 4. Update data-extraction spec
- **File**: `openspec/specs/data-extraction/spec.md`
- **Section**: SQL Implementation Details
- **Changes**:
  - Document required impression event filters
  - Document NULL handling in campaign_show_ad field
  - Update example queries with correct filters
  - Add validation scenario for paid/organic ratios

### 5. Invalidate existing cache
- **Action**: Delete cached parquet files to force regeneration
- **Location**: `auction-simulator/data/cache/*.parquet`
- **Reason**: Old cache has incorrect impression counts and organic/paid ratios

### 6. Run validation queries
- **Query 1**: Check impression count reduction
  ```sql
  -- Should return ~314k instead of ~333k
  SELECT COUNT(*) FROM enriched_distributed
  WHERE [date/country/category filters]
    AND component = 'listing'
    AND screen != 'my_profile'
    AND element = 'ad'
    AND action = 'view'
    AND ad_type = '1'
    AND feed_id = '6500'
  ```

- **Query 2**: Verify NULL handling
  ```sql
  -- Test both organic calculation methods
  SELECT
    SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as old_method,
    SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as new_method,
    COUNT(*) as total
  FROM enriched_distributed
  WHERE [filters with impression events]
  ```
  Expected: old_method = 271k, new_method = 304k (includes NULL)

- **Query 3**: Verify campaign_show_ad distribution
  ```sql
  SELECT campaign_show_ad, COUNT(*)
  FROM enriched_distributed
  WHERE [filters with impression events]
  GROUP BY campaign_show_ad
  ```
  Expected: False (~256k), NULL (~49k), True (~9k)

### 7. Run full simulation test
- **Command**:
  ```bash
  python -m auction_simulator simulate \
      --country 13 \
      --categories 1361 \
      --time-from 2026-01-22 \
      --time-to 2026-01-26 \
      --config config/local.yaml
  ```
- **Verify**:
  - Total impressions: ~314k (was 333k)
  - Organic: ~97% (was 81.6%)
  - Paid: ~3% (was 18.4%)
  - Actual CPI: ~5.7 kopecks (was 0.88)
  - Min_bid: ~5.6 kopecks (unchanged, was already correct)
  - Simulated spending closer to actual (currently 9x higher)

### 8. Update method docstrings
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Methods**: `_extract_impressions()`, `_calculate_min_bids()`
- **Changes**: Document impression filter requirements and NULL handling

## Dependencies

- Task 1 and 2 can run in parallel (different parts of same query)
- Task 3 depends on understanding from Tasks 1-2 (same filter pattern)
- Task 4 can run in parallel with Tasks 1-3 (documentation)
- Task 5 must run after Tasks 1-3 (cache invalidation after code changes)
- Task 6 can run before or after implementation (validation queries independent)
- Task 7 must run last (full integration test)
- Task 8 can run anytime (documentation)

## Success Criteria

- [x] Impression filters added to all extraction queries
- [x] Organic calculation includes NULL values
- [x] Min_bid calculation uses same filters
- [x] Spec documentation updated
- [x] Cache invalidated and regenerated
- [x] Validation queries confirm:
  - Total impressions: ~314k (6% reduction)
  - Organic impressions: ~304k (97.1%)
  - Paid impressions: ~9.4k (2.9%)
  - NULL values included in organic count
- [x] Full simulation shows:
  - Actual CPI ≈ 5.7 kopecks (was 0.88)
  - Actual CPI ≈ min_bid (both ~5.6-5.7 kopecks)
  - Improved spending simulation accuracy
  - Correct paid/organic distribution (~97% organic)
