# Tasks: Fix Impressions Seller ID Field

## Implementation Tasks

### 1. Update impressions extraction query
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Method**: `_extract_impressions()` (lines 178-236)
- **Change**: Replace `user_id as seller_id` with `lister_user_id as seller_id` (line 203)
- **Change**: Update GROUP BY clause from `user_id` to `lister_user_id` (line 218)
- **Validation**: Ensure column name in result set remains `seller_id`

### 2. Update budgets extraction query
- **File**: `auction-simulator/src/auction_simulator/data_extraction.py`
- **Method**: `_extract_budgets()` (lines 238-307)
- **Change**: Replace `user_id as seller_id` with `lister_user_id as seller_id` (line 264)
- **Note**: This query doesn't group by seller_id, but field should match for consistency

### 3. Update data-extraction spec
- **File**: `openspec/specs/data-extraction/spec.md`
- **Section**: "SQL Implementation Details" → "Extract impressions from enriched_distributed" (lines 199-221)
- **Change**: Update example query to use `lister_user_id as seller_id` instead of `user_id as seller_id` (line 206)
- **Add**: Document field semantics:
  - `lister_user_id`: The owner/seller of the ad (constant per ad)
  - `user_id`: The viewer who saw the impression (changes per impression)

### 4. Invalidate existing cache
- **Action**: Delete cached parquet files to force regeneration with correct data
- **Location**: `auction-simulator/data/cache/*.parquet`
- **Reason**: Old cache contains incorrect user_id data

### 5. Test with validation queries
- **Query 1**: Verify lister_user_id is NOT NULL
  ```sql
  SELECT COUNT(*) as null_count
  FROM enriched_distributed
  WHERE lister_user_id IS NULL
  AND data_chunk_date >= '2026-01-22'
  AND data_chunk_date <= '2026-01-26'
  AND country_id = 13
  AND category_id = 1361
  ```
  Expected: null_count = 0

- **Query 2**: Verify lister_user_id is constant per ad
  ```sql
  SELECT ad_id, COUNT(DISTINCT lister_user_id) as seller_count
  FROM enriched_distributed
  WHERE data_chunk_date >= '2026-01-22'
  AND data_chunk_date <= '2026-01-26'
  AND country_id = 13
  AND category_id = 1361
  AND ad_id IS NOT NULL
  GROUP BY ad_id
  HAVING seller_count > 1
  ```
  Expected: 0 rows (every ad has exactly one lister_user_id)

- **Query 3**: Compare unique counts
  ```sql
  SELECT
      COUNT(DISTINCT ad_id) as unique_ads,
      COUNT(DISTINCT lister_user_id) as unique_sellers,
      COUNT(DISTINCT (ad_id, lister_user_id)) as unique_pairs
  FROM enriched_distributed
  WHERE data_chunk_date >= '2026-01-22'
  AND data_chunk_date <= '2026-01-26'
  AND country_id = 13
  AND category_id = 1361
  ```
  Expected: unique_pairs ≈ unique_ads (not 13x more)

### 6. Run full simulation test
- **Command**:
  ```bash
  python -m auction_simulator.main \
      --country 13 \
      --categories 1361 \
      --time-from 2026-01-22 \
      --time-to 2026-01-26
  ```
- **Verify**: "Ads with Impressions: Actual" shows ~8,393 (not 102,881)
- **Verify**: Unique sellers count is realistic (~1,091, not inflated)
- **Verify**: No NULL seller_id in output data

## Dependencies

- Task 1 must complete before Task 6 (code change before test)
- Task 2 can run in parallel with Task 1 (different methods)
- Task 3 can run in parallel with Tasks 1-2 (documentation)
- Task 4 should run after Tasks 1-2 (cache invalidation after code changes)
- Task 5 can run in parallel with Tasks 1-4 (validation queries independent)
- Task 6 must run last (full integration test)

## Success Criteria

- [x] All queries updated to use `lister_user_id` (for enriched_distributed)
- [x] Budgets query uses `user_id` (spendings_distributed doesn't have lister_user_id)
- [x] Spec documentation reflects correct field usage per table
- [x] Cache invalidated and regenerated
- [x] Validation queries confirm data integrity:
  - ✅ Zero NULL lister_user_id values (was 10.6%, now 0%)
  - ✅ 99.99% of ads have exactly one lister_user_id (8,392 of 8,393 ads)
  - ✅ Unique (ad_id, seller_id) pairs ≈ unique ad_ids (8,394 vs 8,393)
- [x] Full simulation shows realistic metrics:
  - ✅ "Ads with Impressions" = 8,394 (was 102,881) - **13x reduction**
  - ✅ No NULL seller_id in reports (0 nulls)
  - ✅ Seller counts match expectations (6,611 unique sellers)
