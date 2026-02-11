# Proposal: Fix min_bid Calculation to Include All Feed Impressions

## Problem

**Current behavior:**
The min_bid calculation filters paid impressions by `feed_id = '6500'`, but actual ad spending covers impressions from ALL feed_ids (not just 6500). This creates artificial min_bid inflation by dividing spending by only a subset of impressions.

**Example:**
- Ad has 1000 paid impressions total (across all feeds)
- Only 100 paid impressions from feed_id='6500'
- Total spending: 100 kopecks
- **Current calculation**: min_bid = 100 / 100 = 1.0 kopeck ❌ (inflated 10x)
- **Correct calculation**: min_bid = 100 / 1000 = 0.1 kopeck ✅

**Impact:**
- Simulated spending: 4,888.77 AZN (767% of budget)
- Actual spending: 539.23 AZN (85% of budget)
- **Discrepancy: 9x higher simulated spending**

This happens because the auction engine uses inflated min_bid to allocate budgets, causing massive overspending.

**Root cause:**
The `_calculate_min_bids()` method filters impressions by `feed_id = '6500'` to match simulation scope, but min_bid should reflect ACTUAL cost per impression across all feeds where spending occurs.

## Solution

**Dual query approach:**

1. **For min_bid calculation**: Query paid impressions WITHOUT `feed_id` filter
   - Reflects true cost per impression across all feeds
   - Matches how spending actually distributed
   - Formula: `total_spending / all_paid_impressions`

2. **For simulation**: Continue filtering impressions WITH `feed_id = '6500'`
   - Limits simulation scope to category feed only
   - Already implemented correctly in `_extract_impressions()`

**Implementation:**
Modify `_calculate_min_bids()` to add new CTE `category_impressions_all_feeds` without feed_id filter:

```python
WITH category_spending AS (
    SELECT SUM(spending) as total_spending
    FROM spendings_distributed
    WHERE ad_id GLOBAL IN (
        SELECT DISTINCT ad_id FROM enriched_distributed
        WHERE category_id = X
        AND feed_id = '6500'  -- Keep filter for ad selection
        AND [impression filters]
    )
),
category_impressions_all_feeds AS (
    SELECT COUNT(*) as paid_impressions
    FROM enriched_distributed
    WHERE category_id = X
    AND campaign_show_ad = 'True'
    -- NO feed_id filter here! ✅
    AND [impression filters]
)
SELECT total_spending / paid_impressions as min_bid
FROM category_spending, category_impressions_all_feeds
```

## Alternatives Considered

### Alternative 1: Use PostgreSQL pre-calculated CPI ❌
**Pros:**
- Pre-calculated average CPI per category available
- No additional ClickHouse queries needed

**Cons:**
- PostgreSQL data covers different time period than simulation (deal-breaker)
- Loss of control over calculation methodology
- Additional database dependency
- Inconsistent with single-source-of-truth principle

**Decision:** Rejected due to time range mismatch. Simulation needs min_bid for exact period (2026-01-22 to 2026-01-26).

### Alternative 2: Keep current approach, adjust simulation logic ❌
**Pros:**
- No changes to data extraction

**Cons:**
- Min_bid would remain incorrect (doesn't reflect actual cost)
- Would need complex compensation logic in auction engine
- Masks the real problem instead of fixing root cause

**Decision:** Rejected. Fixing data extraction is cleaner.

## Expected Results

**Before fix:**
- Total impressions (all feeds): ~1,000,000
- Feed 6500 impressions: ~100,000
- Min_bid calculation: spending / 100,000 ❌
- Result: Inflated min_bid → 9x overspending

**After fix:**
- Total impressions (all feeds): ~1,000,000
- Feed 6500 impressions: ~100,000 (for simulation)
- Min_bid calculation: spending / 1,000,000 ✅
- Result: Accurate min_bid → realistic spending

**Validation criteria:**
- Simulated spending within 50-200% of actual spending (not 900%)
- Min_bid ≈ Actual CPI (spending / all_paid_impressions)
- Feed 6500 simulation uses correct impression count

## Dependencies

- Requires correct impression filters (already implemented in previous change)
- Depends on existing `_extract_impressions()` logic remaining unchanged

## Testing Strategy

1. Run DBeaver validation query comparing min_bid both ways:
   ```sql
   SELECT
       SUM(spending) / COUNT_feed_6500 as min_bid_old,
       SUM(spending) / COUNT_all_feeds as min_bid_new,
       min_bid_old / min_bid_new as inflation_ratio
   ```

2. Run simulation with updated min_bid and compare spending:
   - Check simulated spending closer to actual (539 AZN)
   - Verify min_bid matches actual CPI

3. Validate impression counts:
   - Ensure simulation still uses feed_id='6500' impressions
   - Confirm min_bid uses all-feeds impressions

## Risks

**Low risk change:**
- Isolated to `_calculate_min_bids()` method
- No changes to simulation logic or impression extraction
- Easy to validate (compare old vs new min_bid values)
- Reversible (can revert filter change)

**Potential issue:**
- If ads have NO impressions outside feed_id='6500', min_bid won't change
- Mitigation: Log both impression counts for debugging
