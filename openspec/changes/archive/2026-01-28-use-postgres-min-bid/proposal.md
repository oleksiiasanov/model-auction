# Proposal: Use PostgreSQL for min_bid Lookup

## Why

**Problem:** ClickHouse-calculated min_bid is inflated by 19x compared to actual production min_bid values stored in PostgreSQL.

**Current behavior:**
- Min_bid calculated from ClickHouse: `spending / paid_impressions = 1.3404 kopecks`
- Actual min_bid from PostgreSQL: `price_per_day / fact_impression = 0.0704 kopecks`
- **Discrepancy: 19x inflation**

**Impact on simulation:**
- Simulated spending: 4,863 AZN (763% of budget)
- Actual spending: 539 AZN (85% of budget)
- **Result: 9x overspending in simulation**

**Root cause:** ClickHouse calculation uses historical spending/impression ratio, which doesn't reflect the current platform-wide min_bid policy. PostgreSQL stores the authoritative min_bid values that the production ad system actually uses.

## What Changes

**Replace ClickHouse min_bid calculation with PostgreSQL lookup:**

1. Add PostgreSQL connection to data extraction
2. Query `campaign_ad_price` table for min_bid by category/country
3. Calculate: `min_bid = price_per_day / fact_impression` (in kopecks)
4. Use PostgreSQL min_bid as source of truth for simulation

**Benefits:**
- ✅ Accurate min_bid matching production system (0.0704 vs 1.3404)
- ✅ Realistic simulated spending (~540 AZN vs 4,863 AZN)
- ✅ Single source of truth (production database)
- ✅ Stable values (changes rarely, good for historical simulation)

## Solution

### PostgreSQL Query

```sql
SELECT
    cac.category_id,
    cac.country_id,
    cap.price_per_day,      -- kopecks
    cap.fact_impression,    -- impressions count
    cap.price_per_day::float / cap.fact_impression AS min_bid_kopecks
FROM public.campaign_ad_price cap
JOIN campaign_ad_category cac ON cap.campaign_ad_category_id = cac.id
WHERE cac.category_id IN (:categories)
  AND cac.country_id = :country
  AND cap."default" = TRUE
ORDER BY cac.category_id;
```

### Implementation Approach

**Straightforward integration:**
1. Add `psycopg2-binary` dependency (already done ✅)
2. Add PostgreSQL connection config (already done ✅)
3. Create PostgreSQL client in `data_extraction.py`
4. Replace `_calculate_min_bids()` with `_fetch_min_bids_from_postgres()`
5. Keep fallback to default if category not found

**No breaking changes:**
- Same return type: `Dict[int, float]` (category_id → min_bid kopecks)
- Same error handling: fallback to `min_bid_fallback` config
- Same caching: parquet cache still works

## Alternatives Considered

### Alternative 1: Fix ClickHouse calculation (REJECTED)
**Attempted in previous proposal:** Remove feed_id filter, use all-feeds impressions.

**Why rejected:**
- Still produces inflated min_bid (1.34 kopecks vs 0.07 kopecks)
- Historical data doesn't reflect current platform policy
- More complex query with same wrong result

### Alternative 2: Hybrid approach (UNNECESSARY)
**Idea:** Use PostgreSQL for some categories, ClickHouse for others.

**Why rejected:**
- Adds complexity without benefit
- PostgreSQL has complete data for all categories
- Single source of truth is cleaner

## Expected Results

**Before (ClickHouse calculation):**
```
Category 1361 min_bid: 1.3404 kopecks
Simulated spending: 4,863 AZN (9x actual)
```

**After (PostgreSQL lookup):**
```
Category 1361 min_bid: 0.0704 kopecks
Simulated spending: ~540-800 AZN (1-1.5x actual) ✅
```

**Success criteria:**
- Min_bid from PostgreSQL < 0.1 kopecks
- Simulated spending within 50-200% of actual (not 900%)
- No regression in multi-category support

## Dependencies

**Prerequisites (already completed):**
- ✅ PostgreSQL connection config in `config/local.yaml`
- ✅ `psycopg2-binary>=2.9.0` in `requirements.txt`

**No external dependencies:**
- PostgreSQL database already accessible (read_only user)
- No schema changes required
- No coordination with other systems

## Risks

**Low-risk change:**
- ✅ Read-only database access (no writes)
- ✅ Isolated to data extraction layer
- ✅ Fallback mechanism if query fails
- ✅ Easy to validate (compare min_bid values)
- ✅ Reversible (can revert to ClickHouse calculation)

**Potential issues:**
1. **Network latency:** PostgreSQL query adds ~50-100ms
   - Mitigation: One query per simulation run, cached in parquet
2. **Missing categories:** Category not in PostgreSQL
   - Mitigation: Use `min_bid_fallback` config value (100 kopecks)
3. **Stale data:** PostgreSQL values change infrequently
   - Impact: Minimal, values stable for months

## Testing Strategy

1. **Unit test:** Mock PostgreSQL query, verify calculation
2. **Integration test:** Query real PostgreSQL, validate min_bid values
3. **Simulation test:** Run full simulation, compare spending vs actual
4. **Validation:** Check min_bid logged during extraction matches PostgreSQL

**Acceptance criteria:**
- PostgreSQL query returns min_bid < 0.2 kopecks for category 1361
- Simulated spending < 1,000 AZN (currently 4,863 AZN)
- Simulation completes without errors
