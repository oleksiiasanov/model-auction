# Proposal: Fix min_bid Category Filter

## Problem Statement

The `_calculate_min_bids()` method in `data_extraction.py` calculates min_bid incorrectly, causing simulated spending to be **431x higher** than actual spending (686 AZN vs 74.5 AZN).

### Root Cause

The `category_spending` CTE extracts **ALL spending for the entire country** (not filtered by category), while `category_impressions` correctly filters by **specific category**:

```sql
WITH category_spending AS (
    SELECT SUM(spending) as total_spending
    FROM spendings_distributed
    WHERE country_id = {country}  -- ❌ Missing category filter!
      AND spending > 0
),
category_impressions AS (
    SELECT COUNT(*) as paid_impressions
    FROM enriched_distributed
    WHERE category_id = {category_id}  -- ✅ Correct category filter
      AND campaign_show_ad = 'True'
)
```

### Impact

**Example from production data (2026-01-22, country=13, category=1361):**

| Metric | Value | Issue |
|--------|-------|-------|
| `category_spending` | 452,153 kopecks | ❌ ALL country spending (wrong) |
| `category_impressions` | 1,363 paid impressions | ✅ Category 1361 only (correct) |
| **Calculated min_bid** | **331.73 kopecks** | ❌ 431x too high |
| **Actual CPI** | **0.77 kopecks** | ✅ Real cost per impression |

Result: Simulator uses inflated min_bid (331.73 kop) → overspends by 9x → unrealistic simulation results.

## Proposed Solution

Add category filter to `category_spending` CTE using `GLOBAL IN` subquery (consistent with budget query optimization):

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
)
```

This ensures spending is calculated **only for ads within the target category**.

## Expected Outcomes

### Correctness
- ✅ min_bid calculated from category-specific spending/impressions
- ✅ Simulated spending matches actual spending magnitude (~74 AZN, not 686 AZN)
- ✅ Cost per impression realistic (0.5-1.0 kopecks, not 331 kopecks)

### Performance
- Query executes in ~200-300ms (similar to budget query)
- Uses GLOBAL IN for distributed tables (no "DISTRIBUTED_IN_JOIN_SUBQUERY_DENIED" error)
- Minimal data transfer (filters early)

### Validation
- Rerun simulation with fixed min_bid
- Compare simulated spending to actual spending (should be within 10-20% variance)
- Verify min_bid calculation logs show category-specific values

## Success Criteria

1. **Correctness**: min_bid = (category spending) / (category paid impressions) for same time period
2. **Realistic Spending**: Simulated spending within 2x of actual spending (currently 9x)
3. **Test Coverage**: Validation tests confirm category filter applied correctly
4. **Documentation**: Spec updated to clarify category filter requirement

## Non-Goals

- Changing auction engine logic or bidding algorithm
- Optimizing organic impression distribution
- Changing budget extraction queries (already optimized separately)

## Related Work

- Related to budget query optimization (commit: optimize-budget-query-filtering)
- Uses same GLOBAL IN pattern for distributed tables
- Builds on existing data_extraction infrastructure
