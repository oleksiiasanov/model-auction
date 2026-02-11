# Design: Optimize Budget Query Filtering

## Problem Analysis

### Current Implementation Flow

```
1. Extract impressions with category filter
   ↓
   SELECT ... FROM enriched_distributed
   WHERE category_id IN (1234, 5678)  -- Returns ~1,000 ads
   ↓
   Result: 1,000 unique ad_ids

2. Extract budgets WITHOUT category filter
   ↓
   SELECT ... FROM spendings_distributed
   WHERE country_id = 13  -- Returns ~50,000 budget records ❌
   ↓
   Result: 50,000 budget records

3. Filter in Python
   ↓
   for record in budgets:
       if record.ad_id in ads:  -- Keep only 1,000
           use_record()
   ↓
   Result: 1,000 budget records used, 49,000 discarded
```

**Inefficiency:** 49,000 unnecessary records transferred from database → Python → discarded.

### Root Cause

`_extract_budgets()` method signature:
```python
def _extract_budgets(self, country, time_from, time_to):
```

Missing parameter: `categories` → Cannot filter by category in SQL.

## Solution Design

### Approach 1: SQL Subquery (CHOSEN)

**Rationale:** Single query, database-optimized, no round trips.

```sql
SELECT ...
FROM spendings_distributed
WHERE country_id = {country}
  AND ad_id IN (
    SELECT DISTINCT ad_id
    FROM enriched_distributed
    WHERE category_id IN ({categories})
      AND country_id = {country}
      AND data_chunk_date >= ... AND data_chunk_date <= ...
      AND feed_id = '6500'
      AND ad_type = '1'
      AND client != 'backend'
      AND ad_id IS NOT NULL
  )
```

**Execution plan (ClickHouse):**
1. Evaluate subquery first → returns ~1,000 ad_ids (uses indices)
2. Filter spendings_distributed using ad_id IN (1,000 values)
3. Return only matching budget records

**Advantages:**
- ✅ Single database round-trip
- ✅ ClickHouse query optimizer handles efficiently
- ✅ Uses indices on both tables
- ✅ Minimal Python code changes

**Disadvantages:**
- ⚠️ Subquery repeats some filters from impressions query (category_id, country_id, dates)
- ⚠️ Slightly more complex SQL

### Approach 2: Two-Step Python (REJECTED)

**Alternative:** Extract impressions → get ad_ids → pass to budget query.

```python
# Step 1
impressions = self._extract_impressions(...)
ad_ids = impressions['ad_id'].unique().tolist()  # ~1,000 ids

# Step 2
budgets = self._extract_budgets(country, ad_ids, time_from, time_to)
# WHERE ad_id IN (123, 456, 789, ..., 50000)  # Explicit list
```

**Execution plan:**
1. Python → ClickHouse: extract impressions
2. Python: compute unique ad_ids
3. Python → ClickHouse: extract budgets with ad_id IN (explicit list)

**Advantages:**
- ✅ Explicit ad_id list (easier to debug)
- ✅ Reuses impressions result

**Disadvantages:**
- ❌ Two database round-trips (network latency)
- ❌ ad_ids list can be large (1,000+ values in IN clause)
- ❌ More Python code complexity
- ❌ Cannot benefit from ClickHouse query optimizer combining both queries

**Why rejected:** Extra round-trip adds latency, more complex data flow.

### Approach 3: JOIN (CONSIDERED BUT NOT PREFERRED)

**Alternative:** JOIN spendings with impressions subquery.

```sql
SELECT s.*
FROM spendings_distributed s
INNER JOIN (
  SELECT DISTINCT ad_id
  FROM enriched_distributed
  WHERE ...
) i ON s.ad_id = i.ad_id
WHERE s.country_id = {country}
  AND s.operationdate >= ... AND s.operationdate <= ...
```

**Advantages:**
- ✅ Single query
- ✅ JOIN might use merge join

**Disadvantages:**
- ⚠️ JOIN syntax more complex than IN subquery
- ⚠️ INNER JOIN vs WHERE IN performance is similar in ClickHouse

**Why not chosen:** WHERE IN is more readable and performance is equivalent.

## Implementation Details

### Method Signature Change

**Before:**
```python
def _extract_budgets(
    self,
    country: int,
    time_from: date,
    time_to: date
) -> pd.DataFrame:
```

**After:**
```python
def _extract_budgets(
    self,
    country: int,
    categories: List[int],  # ← ADDED
    time_from: date,
    time_to: date
) -> pd.DataFrame:
```

### Query Construction

```python
categories_str = ','.join(map(str, categories))

query = f"""
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
"""
```

### Call Site Update

In `extract_data()` method:

**Before:**
```python
budgets = self._extract_budgets(country, time_from, time_to)
```

**After:**
```python
budgets = self._extract_budgets(country, categories, time_from, time_to)
```

## Performance Expectations

### Baseline (Current)

- Query time: ~500ms
- Records returned: ~50,000
- Network transfer: ~3 MB
- DataFrame memory: ~50 MB
- Cache file size: ~3 MB (parquet)

### Optimized (Expected)

- Query time: ~50ms (10x faster)
- Records returned: ~1,000 (50x fewer)
- Network transfer: ~60 KB (50x smaller)
- DataFrame memory: ~1 MB (50x smaller)
- Cache file size: ~300 KB (10x smaller)

### Why Improvement?

1. **Subquery is fast:** SELECT DISTINCT ad_id with category filter uses indices → ~10ms
2. **Main query scans less:** ad_id IN (1,000 values) vs full country scan
3. **Less data transfer:** 1,000 records vs 50,000 records
4. **Less Python processing:** DataFrame with 1,000 rows vs 50,000 rows

## Testing Strategy

### Correctness Validation

1. **Exact match test:**
   - Run old implementation → save budgets_old.csv
   - Run new implementation → save budgets_new.csv
   - Compare: assert budgets_old == budgets_new (after sorting)

2. **Row count test:**
   - Count unique ad_ids in impressions → N
   - Count rows in budgets (after dedup) → M
   - Assert M <= N * days (each ad can have budget for each day)

3. **No missing ads:**
   - Get ad_ids with budget>0 from impressions
   - Check all are present in budgets_df
   - No KeyError when accessing budgets

### Performance Validation

1. **Benchmark query time:**
   ```python
   import time
   start = time.time()
   budgets = extractor._extract_budgets(...)
   elapsed = time.time() - start
   print(f"Query time: {elapsed:.2f}s")
   ```

2. **Measure DataFrame size:**
   ```python
   import sys
   size_mb = sys.getsizeof(budgets) / 1024 / 1024
   print(f"DataFrame size: {size_mb:.2f} MB")
   ```

3. **Compare cache files:**
   ```bash
   ls -lh cache/*_budgets.parquet
   # Before: 3.0M
   # After:  300K
   ```

## Rollback Plan

If optimization causes issues:

1. **Revert method signature:**
   - Remove `categories` parameter
   - Restore old query (without subquery)

2. **Rollback takes <5 minutes:**
   - Single file change: `data_extraction.py`
   - No database schema changes
   - No config changes

3. **No data loss risk:**
   - Read-only queries
   - Cache files are regenerated automatically
