# Proposal: Fix Impression Filters and Organic Calculation

## Problem

The impressions extraction has two critical issues causing incorrect paid/organic metrics:

### Issue 1: Missing Impression Event Filters

**Current Implementation:**
```sql
SELECT ...
FROM enriched_distributed
WHERE category_id = 1361
  AND feed_id = '6500'
  AND ad_type = '1'
  AND client != 'backend'
  -- Missing impression-specific filters!
```

**Impact:** Extracts ALL platform events (clicks, scrolls, profile views, etc.), not just impression views.

**Data from enriched_distributed:**
- Without impression filters: 332,952 events
- With correct filters: 313,977 events (6% reduction)

### Issue 2: Incorrect Organic Impressions Calculation

**Current Implementation:**
```sql
SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as organic_impressions
```

**Problem:** In ClickHouse, the `!= 'True'` operator **DOES NOT include NULL values**!

**Business Logic:** NULL campaign_show_ad means **organic (free)** impressions, same as 'False'.

**Actual Behavior:**
- campaign_show_ad values: False (271,394), NULL (51,831), True (9,727)
- Current calc: organic = 271,394 (excludes NULL) ❌
- Correct calc: organic = 323,225 (includes NULL) ✅
- Paid impressions: 61,247 (current) vs 9,435 (correct) - **6.5x inflation!**

**Impact on Metrics:**
```
Current (WRONG):
  Organic: 271,394 (81.6%)
  Paid:    61,247 (18.4%)
  Actual CPI: 539.23 AZN / 61,247 = 0.88 kopecks

Correct:
  Organic: 323,225 (97.1%)
  Paid:    9,435 (2.9%)
  Actual CPI: 539.23 AZN / 9,435 = 5.72 kopecks
```

**Why Min_bid Seemed Wrong:**
- Min_bid calculation: 5.56 kopecks (actually CORRECT!)
- Appeared 6.3x higher than "actual CPI" (0.88 kopecks)
- But actual CPI was wrong due to NULL handling bug
- True CPI = 5.72 kopecks, so min_bid is accurate!

### Issue 3: Inflated Spending in Simulation

With incorrect paid impressions (61,247 instead of 9,435), the simulation:
- Thinks more ads need paid promotion
- Allocates budgets incorrectly
- Results in 9x higher simulated spending (4,888 AZN vs 539 AZN actual)

## Solution

### Fix 1: Add Impression Event Filters

Add required filters to ensure only impression view events are extracted:

```sql
SELECT ...
FROM enriched_distributed
WHERE category_id = 1361
  AND component = 'listing'       -- ✅ Event from listing page
  AND screen != 'my_profile'      -- ✅ Exclude profile views
  AND element = 'ad'              -- ✅ Element is an ad
  AND action = 'view'             -- ✅ Action is view (impression)
  AND ad_type = '1'
  AND feed_id = '6500'
  AND client != 'backend'
```

### Fix 2: Include NULL in Organic Count

Change organic calculation to explicitly include NULL values:

```sql
-- WRONG (current):
SUM(CASE WHEN campaign_show_ad != 'True' THEN 1 ELSE 0 END) as organic_impressions

-- CORRECT (proposed):
SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
```

This treats NULL and 'False' as organic (free) impressions.

## Scope

**In Scope:**
- Update `_extract_impressions()` query to add impression filters
- Fix organic impressions calculation to handle NULL correctly
- Update data-extraction spec to document correct filters and NULL handling
- Regenerate cache with correct data

**Out of Scope:**
- Changes to min_bid calculation (already correct!)
- Changes to simulation algorithm (will automatically improve with correct data)
- Historical data migration

## Expected Results

**Before Fix:**
- Total impressions: 332,641
- Organic: 271,394 (81.6%)
- Paid: 61,247 (18.4%)
- Actual CPI: 0.88 kopecks (wrong!)
- Min_bid appears 6.3x too high

**After Fix:**
- Total impressions: 313,977 (6% reduction, only impression events)
- Organic: 304,542 (97.1%)
- Paid: 9,435 (2.9%)
- Actual CPI: 5.72 kopecks (correct!)
- Min_bid = 5.56 kopecks matches actual CPI ✅

**Simulation Impact:**
- Correct paid/organic ratio improves budget allocation
- Simulated spending should be closer to actual (currently 9x higher)
- More realistic impression distribution

## Risks

**Low Risk:**
- Simple SQL filter additions and logic fix
- No algorithm changes, only data extraction
- Cache regeneration handles historical data

**Validation:**
- Verify impression count reduces to ~314k
- Verify organic % increases to ~97%
- Verify paid impressions = ~9,435
- Verify actual CPI ≈ min_bid (both ~5.5-5.7 kopecks)

## Dependencies

None (standalone fix)

## Alternatives Considered

1. **Keep current logic, adjust min_bid calculation** ❌
   - Doesn't fix root cause (wrong impression counts)
   - Would require arbitrary adjustment factor
   - Perpetuates data quality issues

2. **Only add impression filters, keep != 'True' logic** ❌
   - Doesn't fix NULL handling bug
   - Still inflates paid impressions by 6.5x
   - Doesn't solve the core problem

3. **Add filters AND fix NULL handling (CHOSEN)** ✅
   - Fixes both root causes
   - Data extraction becomes accurate
   - All downstream metrics improve automatically
   - Aligns with business semantics (NULL = organic)
