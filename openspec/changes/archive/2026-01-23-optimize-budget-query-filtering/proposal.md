# Change: Optimize Budget Query Filtering

## Why

**Problem: Inefficient budget data extraction**

Current implementation extracts ALL campaign budgets for entire country, then filters in Python:
- Query returns ~50,000 budget records for country
- Simulation uses only ~1,000 ads (filtered by categories in impressions)
- Python discards 49,000 unused records with `if ad_id in self.ads` check

**Impact:**
- Wasted database query time (~500ms extra)
- Unnecessary network transfer (~2-3 MB extra data)
- Wasted memory in Python DataFrames
- Slower cache reads/writes (larger parquet files)
- Scales poorly with country size

**Root cause:**
`_extract_budgets()` has WHERE clause for country but NOT for ad_id list from selected categories.

## What Changes

Optimize budget extraction using SQL subquery to filter by ad_id:

**Current query:**
```sql
SELECT ... FROM spendings_distributed
WHERE country_id = {country}  -- Gets ALL ads in country ❌
```

**Optimized query:**
```sql
SELECT ... FROM spendings_distributed
WHERE country_id = {country}
  AND ad_id IN (
    SELECT DISTINCT ad_id FROM enriched_distributed
    WHERE category_id IN ({categories})
      AND country_id = {country}
      AND data_chunk_date >= ... AND data_chunk_date <= ...
  )  -- Gets ONLY ads in selected categories ✅
```

**Benefits:**
- 50x fewer records returned (1,000 vs 50,000)
- ClickHouse optimizes subquery first (uses indices)
- Single round-trip (no Python → DB → Python → DB)
- Smaller cache files
- Scales better with country size

## Impact

- **Affected files**:
  - `src/auction_simulator/data_extraction.py` (modify `_extract_budgets` method)

- **Affected systems**: None (internal optimization)

- **Data requirements**: None (uses existing tables)

- **Performance improvement**:
  - Query time: ~500ms → ~50ms (10x faster)
  - Network transfer: ~3MB → ~60KB (50x smaller)
  - Memory usage: ~50MB → ~1MB (50x smaller)

- **Risk**: Low (backward compatible, same output)

- **Testing**:
  - Validate same results as before (compare outputs)
  - Test with different category/country combinations
  - Benchmark query performance

## Success Criteria

1. ✅ Budget query includes WHERE ad_id IN (subquery)
2. ✅ Subquery returns DISTINCT ad_ids from impressions query
3. ✅ Query returns same data as before (validated with tests)
4. ✅ Performance improvement measured (>5x faster)
5. ✅ Cache files smaller (>10x size reduction)
