# Proposal: Fix Impressions Seller ID Field

## Problem

The impression extraction query uses the wrong field for `seller_id`, causing massive data duplication and incorrect metrics:

**Current Implementation (WRONG)**:
```sql
SELECT
    category_id,
    ad_id,
    user_id as seller_id,  -- ❌ WRONG FIELD
    ...
FROM enriched_distributed
GROUP BY category_id, ad_id, user_id, date, hour  -- ❌ Groups by viewer ID
```

**Impact**:
- `user_id` represents the **viewer** who saw the impression (changes per impression)
- This creates 13x duplicate records: 108,060 unique (ad_id, seller_id) pairs vs 8,393 actual unique ads
- "Ads with Impressions" metric shows 102,881 instead of ~8,393 (1,225% inflation)
- Example: ad_id=33699836 has 125 different `user_id` values across hours
- Some records have NULL `user_id`, creating NULL seller_id (10.6% of records)

**Three Technical Impossibilities Occurring**:
1. Ads transferring between sellers (impossible on platform)
2. NULL seller_id values (impossible by business rules)
3. seller_id changing over time for same ad (impossible by design)

All three happening simultaneously confirms wrong field is being used.

## Solution

Use `lister_user_id` instead of `user_id` in the impressions extraction query:

```sql
SELECT
    category_id,
    ad_id,
    lister_user_id as seller_id,  -- ✅ CORRECT FIELD
    ...
FROM enriched_distributed
GROUP BY category_id, ad_id, lister_user_id, date, hour  -- ✅ Groups by actual seller
```

**Expected Results**:
- `lister_user_id` represents the **owner/seller** of the ad (constant per ad)
- Unique (ad_id, seller_id) pairs ≈ unique ad_ids (~8,393)
- "Ads with Impressions" metric shows realistic count (~8,393)
- No NULL seller_id values
- No ads changing sellers over time

## Scope

**In Scope**:
- Update `_extract_impressions()` query in data_extraction.py (lines 203, 218)
- Update `_extract_budgets()` query in data_extraction.py (line 264)
- Update data-extraction spec to document correct field usage
- Validate fix with test queries

**Out of Scope**:
- Changes to reporting logic (automatically fixed by correct data)
- Changes to auction simulation (uses data as-is)
- Historical data migration (cache will be regenerated)

## Risks

**Low Risk**:
- Simple field rename, no logic changes
- Affects only data extraction, not simulation algorithm
- Cache invalidation happens automatically (files regenerated on next run)
- No database schema changes required

**Validation**:
- Verify lister_user_id is constant per ad_id
- Confirm no NULL lister_user_id values
- Check unique (ad_id, lister_user_id) ≈ unique ad_id

## Dependencies

- None (standalone fix)

## Alternatives Considered

1. **Keep user_id and deduplicate in reporting** ❌
   - Doesn't fix root cause
   - Arbitrary choice of which user_id to keep
   - Loses data integrity

2. **Use GROUP BY ad_id only (drop seller_id)** ❌
   - Breaks budget tracking per seller
   - Can't aggregate seller-level metrics
   - Violates business requirement to track per-seller performance

3. **Use lister_user_id (CHOSEN)** ✅
   - Fixes root cause
   - Preserves data integrity
   - Aligns with business semantics

## Implementation Results

**Successfully Applied:**
- Changed enriched_distributed query to use `lister_user_id as seller_id`
- Kept spendings_distributed query using `user_id as seller_id` (table doesn't have lister_user_id)
- Updated spec documentation to clarify field differences between tables
- Cache regenerated with correct data

**Validation Results:**
- ✅ Ads with Impressions: 8,394 (was 102,881) - **13x reduction**
- ✅ Unique (ad_id, seller_id) pairs: 8,394 ≈ 8,393 unique ads
- ✅ NULL seller_id: 0 (was 10.6%)
- ✅ Ads with exactly one seller: 99.99% (8,392 of 8,393)
- ✅ Realistic seller count: 6,611 unique sellers

**Impact:**
The fix resolved the data duplication issue, bringing "Ads with Impressions" metric from 102,881 down to the realistic 8,394, matching the expected ~8,393 unique ads in the category.
