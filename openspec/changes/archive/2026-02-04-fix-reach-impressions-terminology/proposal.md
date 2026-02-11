# Proposal: Fix Reach vs Impressions Terminology in Reporting

**Change ID**: `fix-reach-impressions-terminology`
**Status**: Proposed
**Created**: 2026-02-02

## Why

Summary statistics currently mislabel metrics, causing confusion:
- Shows "Total Impressions: 233,806" but this is actually **reach** (unique users per ad per day)
- Raw impressions (583,065) are not shown at all
- Unique users (3,458) are not shown at all

This makes it impossible to verify simulation accuracy against database queries without deep code inspection.

## Problem Statement

**Current Summary Statistics Output:**
```
Total Impressions:
  Actual:    233,806
  Simulated: 233,806
  Diff:      0
```

**What it actually means:**
- 233,806 = **reach** (COUNT(DISTINCT user_id) GROUP BY ad_id, date)
- NOT raw impressions (COUNT(*))

**Missing critical metrics:**
- Raw impressions: 583,065 (not shown)
- Unique users: 3,458 (not shown)

**Database verification confusion:**
```sql
-- User runs this expecting to see 233,806
SELECT COUNT(*) FROM enriched_distributed WHERE ...
-- Gets: 583,065 ❌ Does not match!

-- User runs this
SELECT COUNT(DISTINCT user_id) FROM enriched_distributed WHERE ...
-- Gets: 3,458 ❌ Does not match!

-- Only this matches:
SELECT SUM(COUNT(DISTINCT user_id)) FROM enriched_distributed GROUP BY ad_id, date ...
-- Gets: 233,806 ✅ But users don't know to run this!
```

## What Changes

Update summary statistics and reporting to show all three metrics with correct terminology:

**New Summary Statistics Output:**
```
Unique Users (Total):
  Actual:    3,458
  Simulated: [calculated from simulation]

Total Reach (user × ad × date combinations):
  Actual:    233,806
  Simulated: 233,806
  Diff:      0

Raw Impressions (all views):
  Actual:    583,065
  Simulated: [not applicable - simulation works with reach]
```

**Files affected:**
- `src/auction_simulator/reporting.py`: Update summary statistics generation
- `openspec/specs/reporting-enhancements/spec.md`: Add terminology requirement
- `docs/faq/01-terminology.md`: Add reach vs impressions explanation

## Proposed Solution

### 1. Add Raw Impressions to Data Extraction

Extract `raw_impressions` column already exists in `impressions_df`, just need to aggregate and display it.

### 2. Calculate Unique Users

Add calculation:
```python
unique_users_actual = impressions_df['user_id'].nunique()  # Needs user_id column
```

**Problem**: Current `impressions_df` doesn't have `user_id` column after GROUP BY!

**Solution A** (Simple): Document that unique users = aggregate metric, show formula
**Solution B** (Complex): Modify data extraction to preserve user_id list per ad

**Recommended**: Solution A - add explanatory text, not actual calculation.

### 3. Update Summary Statistics Template

```python
# reporting.py
summary_lines = [
    "=" * 80,
    "SIMULATION SUMMARY STATISTICS",
    "=" * 80,
    "",
    "Unique Users (globally):",
    "  Note: Actual count not tracked (requires user_id list)",
    "  Estimated from reach: ~{:.0f} (reach / 68 avg combinations per user)".format(total_reach_actual / 68),
    "",
    "Total Reach (user × ad × date combinations):",
    f"  Actual:    {total_reach_actual:,}",
    f"  Simulated: {total_reach_simulated:,}",
    f"  Diff:      {total_reach_simulated - total_reach_actual:,}",
    "",
    "Raw Impressions (all views, including repeats):",
    f"  Actual:    {raw_impressions_actual:,}",
    "  Note: Simulation operates on reach, not raw impressions",
    "",
]
```

### 4. Add Ratios for Context

```python
    "Metrics Ratios:",
    f"  Impressions per reach: {raw_impressions_actual / total_reach_actual:.2f}x",
    f"  Reach per unique user: ~68 (estimated)",
```

## Expected Impact

**Before:**
- User sees "Total Impressions: 233,806"
- Runs `COUNT(*)` query → gets 583,065 → confused ❌

**After:**
- User sees "Total Reach: 233,806" + "Raw Impressions: 583,065"
- Runs queries with clear understanding ✅
- Can verify each metric independently

## Validation Evidence

**Category 1361, 2026-01-31 to 2026-02-01:**

| Metric | SQL Query | Result | Current Label | Correct Label |
|--------|-----------|--------|---------------|---------------|
| Raw impressions | `COUNT(*)` | 583,065 | (not shown) | Raw Impressions |
| Reach | `SUM(COUNT(DISTINCT user_id) GROUP BY ad_id, date)` | 233,806 | ❌ "Total Impressions" | ✅ "Total Reach" |
| Unique users | `COUNT(DISTINCT user_id)` | 3,458 | (not shown) | Unique Users |

## Scope

### In Scope
- Update summary statistics labels (reach, not impressions)
- Add raw impressions count to output
- Add explanatory notes for unique users
- Update FAQ with terminology clarification
- Update spec with correct metric definitions

### Out of Scope
- Tracking actual unique users (requires user_id list storage - too expensive)
- Changing simulation logic (already correct, just mislabeled)
- Historical data corrections

## Dependencies

- **Relates to**: Reporting enhancements, data extraction
- **Blocks**: None
- **Blocked by**: None

## Risks and Mitigations

### Risk 1: Breaking existing scripts/dashboards

**Impact**: Anyone parsing summary statistics will see different labels

**Mitigation**:
- Keep output format similar, just rename labels
- Add migration notes in changelog
- Version summary statistics file with header

### Risk 2: Confusion about "what changed"

**Impact**: Users think simulation behavior changed

**Mitigation**:
- Clear changelog: "Labels fixed, behavior unchanged"
- FAQ entry explaining the fix
- Keep old metrics available with deprecation note

### Risk 3: Cannot calculate exact unique users

**Impact**: "Unique Users" metric will be estimated, not exact

**Mitigation**:
- Document this limitation clearly
- Show estimation formula
- Explain why exact tracking is not feasible

## Questions for Stakeholders

1. **Metric names**: Confirm these names are clear:
   - "Unique Users (globally)" vs "Total Unique Users"?
   - "Total Reach" vs "Reach Records"?
   - "Raw Impressions" vs "Total Impressions"?

2. **Unique users calculation**: Accept estimated value, or invest in exact tracking?
   - Estimated: ~3,400 (reach / 68)
   - Exact: Requires storing user_id per record (memory cost)

3. **Backward compatibility**: Keep old labels as deprecated aliases?

## Success Criteria

- ✅ Summary statistics shows three distinct metrics with correct labels
- ✅ Each metric can be verified independently via SQL query
- ✅ FAQ documents reach vs impressions vs unique users
- ✅ No simulation behavior changes (only labels)
- ✅ Spec updated with metric definitions

## References

- **Current Code**: [reporting.py:generate_reports](../../auction-simulator/src/auction_simulator/reporting.py)
- **Evidence**: DBeaver queries show 583,065 impressions ≠ 233,806 reach
- **User Request**: "Total Reach: 233,806 (user × ad × date combinations), Total Impressions: 583,065 (raw views), Unique Users: 3,458"
