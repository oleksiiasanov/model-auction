# Design: Fix min_bid Category Filter

## Overview

Fix incorrect min_bid calculation in `_calculate_min_bids()` by adding category filter to spending aggregation query.

## Current Implementation Analysis

### File: `src/auction_simulator/data_extraction.py:316-389`

**Current Query Structure (lines 339-368):**
```sql
WITH category_spending AS (
    SELECT SUM(spending) as total_spending
    FROM analytics_reports.spendings_distributed s
    WHERE operationdate >= :time_from
      AND operationdate <= :time_to
      AND country_id = :country
      AND spending > 0
    -- ❌ MISSING: category filter
),
category_impressions AS (
    SELECT COUNT(*) as paid_impressions
    FROM enriched_distributed i
    WHERE data_chunk_date >= :time_from
      AND data_chunk_date <= :time_to
      AND country_id = :country
      AND category_id = :category_id  -- ✅ Has category filter
      AND campaign_show_ad = 'True'
      AND feed_id = '6500'
      AND ad_type = '1'
      AND client != 'backend'
)
SELECT s.total_spending, i.paid_impressions
FROM category_spending s, category_impressions i
```

**Problem**: Spending aggregated for **entire country**, impressions for **specific category** → min_bid inflated 431x.

---

## Design Approaches Considered

### Approach 1: Subquery with GLOBAL IN ✅ RECOMMENDED

**Pros:**
- ✅ Consistent with budget query optimization pattern
- ✅ Single query with clear separation of concerns
- ✅ Works with distributed tables (GLOBAL IN)
- ✅ Database-optimized (ClickHouse evaluates subquery once)
- ✅ Reusable subquery pattern across project

**Cons:**
- Slightly more complex SQL (but well-tested pattern)

**Implementation:**
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
    -- unchanged
)
```

---

### Approach 2: Direct JOIN

**Pros:**
- Single JOIN query (potentially more readable)

**Cons:**
- ❌ More complex to optimize (ClickHouse may scan both tables)
- ❌ Different pattern from budget query (inconsistent)
- ❌ Harder to debug if performance issues

**Implementation:**
```sql
SELECT
    SUM(s.spending) as total_spending,
    COUNT(*) as paid_impressions
FROM analytics_reports.spendings_distributed s
INNER JOIN enriched_distributed i
    ON s.ad_id = i.ad_id
    AND s.operationdate = i.data_chunk_date
WHERE s.operationdate >= toDate('{time_from}')
  AND i.category_id = {category_id}
  AND i.campaign_show_ad = 'True'
  AND s.spending > 0
```

**Rejected because**: Less consistent with existing codebase patterns, harder to optimize.

---

### Approach 3: Two-Step Python Extraction

**Pros:**
- Simple logic (extract ad_ids, then filter spending)

**Cons:**
- ❌ Two database round trips (slower)
- ❌ More memory usage (store ad_ids in Python)
- ❌ Doesn't leverage database optimizations

**Rejected because**: Performance overhead, unnecessary complexity.

---

## Selected Approach: Subquery with GLOBAL IN

### Rationale

1. **Consistency**: Uses same pattern as budget query optimization (already validated)
2. **Performance**: ClickHouse evaluates subquery once, filters spending efficiently
3. **Correctness**: Guarantees spending calculated only for category-specific ads
4. **Maintainability**: Well-established pattern, easy to understand

### Implementation Plan

**File to modify**: `src/auction_simulator/data_extraction.py`
**Method**: `_calculate_min_bids()`
**Lines**: 340-348 (category_spending CTE)

**Changes:**
1. Add `AND ad_id GLOBAL IN (...)` clause to category_spending WHERE
2. Use same subquery structure as budget extraction (lines 274-286)
3. Ensure consistent filter conditions (feed_id, ad_type, client, etc.)

### Query Performance

**Expected execution time**: ~200-300ms (similar to budget query)
**Data scanned**: Only ads from target category (50-100 ads typically)
**Network transfer**: Minimal (aggregated result: 2 numbers)

### Validation

**Before fix:**
```
Category 1361: min_bid=331.7339 kopecks (spending=452153.26, impressions=1363)
→ Simulated spending: 686.08 AZN (9x actual)
```

**After fix (expected):**
```
Category 1361: min_bid=~0.77 kopecks (spending=~7450, impressions=~9735)
→ Simulated spending: ~75 AZN (matches actual)
```

---

## Alternative Considered: Spec Clarification Only

Instead of fixing code, we could update spec to document that min_bid uses **country-level** spending.

**Rejected because**:
- ❌ Produces unrealistic simulation results
- ❌ Contradicts spec intent ("per category" calculation)
- ❌ Makes simulator unusable for real analysis

---

## Risk Assessment

### Low Risk
- Query pattern already validated in budget extraction
- GLOBAL IN works with distributed tables
- Fallback mechanism already exists (min_bid_fallback config)

### Mitigation
- Add logging to verify query returns expected spending/impression counts
- Test with multiple categories to ensure correct filtering
- Compare simulated spending to actual spending as validation

---

## Future Enhancements (Out of Scope)

1. **Cache min_bid calculations**: Store per-category min_bid in cache
2. **Dynamic min_bid updates**: Recalculate min_bid during simulation if spending patterns change
3. **Multi-category min_bid**: Calculate min_bid across category groups

These are **not included** in this proposal to keep scope focused on correctness fix.
