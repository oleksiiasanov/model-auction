# Proposal: Fix Reach Distribution Calculation in Summary Statistics

**Change ID**: `fix-reach-distribution-calculation`
**Status**: Proposed
**Created**: 2026-02-02
**Type**: Bug Fix

## Why

Summary statistics report contains incorrect paid/organic reach calculation in "Reach Distribution Analysis" section, causing misleading metrics.

**Evidence from latest run (2026-02-02 15:35):**

Two sections report conflicting paid reach values:
1. **"Paid Reach" section (lines 33-34)** - CORRECT:
   ```
   Paid Reach:
     Actual:    81,152 (34.7%)
   ```

2. **"Reach Distribution Analysis" section (lines 68-69)** - WRONG:
   ```
   Paid Reach:
     Actual:    96,014.0
   ```

**Discrepancy: 96,014 - 81,152 = 14,862 reach (18.3% inflation!)**

## Root Cause

File: [reporting.py:442-443](../../../auction-simulator/src/auction_simulator/reporting.py#L442-L443)

```python
# CURRENT CODE (WRONG):
paid_reach_actual = ad_comparison[ad_comparison['actual_reach_paid'] > 0]['actual_reach_total'].sum()
free_reach_actual = ad_comparison[ad_comparison['actual_reach_paid'] == 0]['actual_reach_total'].sum()
```

**Problem:**
- Filters ads by `actual_reach_paid > 0` (correct)
- But then sums `actual_reach_total` which includes **both paid AND organic** reach (wrong!)

**Example:**
- Ad has: `actual_reach_paid=81`, `actual_reach_organic=100`, `actual_reach_total=181`
- Current code takes: `actual_reach_total=181` ❌ (includes organic 100!)
- Should take: `actual_reach_paid=81` ✅

**Why inflation happens:**
Many ads have both paid and organic reach in the same period. When we filter by `actual_reach_paid > 0` and sum `actual_reach_total`, we're double-counting the organic portion.

## What Changes

Fix calculation to use correct columns:

```python
# CORRECT CODE:
paid_reach_actual = ad_comparison['actual_reach_paid'].sum()
free_reach_actual = ad_comparison['actual_reach_organic'].sum()

# Simulated remains same (no actual_reach_paid column in simulated data)
paid_reach_simulated = ad_comparison[ad_comparison['simulated_spending_azn'] > 0]['simulated_reach_total'].sum()
free_reach_simulated = ad_comparison[ad_comparison['simulated_spending_azn'] == 0]['simulated_reach_total'].sum()
```

**Files affected:**
- `auction-simulator/src/auction_simulator/reporting.py` (lines 442-443)

## Expected Impact

**Before fix (current output):**
```
Reach Distribution Analysis:
  Paid Reach:
    Actual:    96,014.0     ← WRONG (inflated)
    Simulated: 109,353.0
    Change:    +13,339.0 (+13.9%)
  Organic Reach:
    Actual:    137,792.0    ← WRONG (deflated)
    Simulated: 124,453.0
    Change:    -13,339.0 (-9.7%)
```

**After fix (expected output):**
```
Reach Distribution Analysis:
  Paid Reach:
    Actual:    81,152.0     ← CORRECT (matches CSV and Paid Reach section)
    Simulated: 109,353.0
    Change:    +28,201.0 (+34.7%)
  Organic Reach:
    Actual:    152,654.0    ← CORRECT (matches CSV)
    Simulated: 124,453.0
    Change:    -28,201.0 (-18.5%)
```

**Changes:**
- ✅ Consistency: Both sections show same actual paid reach (81,152)
- ✅ Accuracy: Values match CSV data exactly
- ✅ Conservation: `paid_actual + organic_actual = total_reach` (81,152 + 152,654 = 233,806 ✓)

## Validation Strategy

1. **CSV cross-check:**
   ```bash
   # Sum actual_reach_paid column in ad_comparison CSV
   awk -F',' 'NR>6 {sum+=$8} END {print sum}' outputs/ad_comparison_*.csv
   # Should match "Paid Reach: Actual:" in summary
   ```

2. **Conservation check:**
   ```python
   paid_reach_actual + free_reach_actual == total_reach_actual  # Must be True
   ```

3. **Run simulation and verify:**
   ```bash
   python -m auction_simulator.cli simulate \
     --country 13 --categories 1361 \
     --time-from 2026-01-31 --time-to 2026-02-01 \
     --no-cache
   ```

## Dependencies

- ✅ No dependencies (standalone bug fix)
- ✅ Does not conflict with active changes:
  - `fix-reach-impressions-terminology`: Naming changes only, no calculation logic
  - `fix-fractional-kopecks-bid-step`: Budget/bid logic, not reporting

## Alternatives Considered

### Alt 1: Keep current logic, document as "intended"
- ❌ Rejected: Current logic is mathematically incorrect
- ❌ Violates conservation law: paid + organic ≠ total

### Alt 2: Remove "Reach Distribution Analysis" section
- ❌ Rejected: Valuable metric for understanding simulation impact
- ✅ Better: Fix calculation, keep section

## Risk Assessment

**Risk**: Very Low
- Single 2-line change in reporting logic
- No impact on simulation engine, data extraction, or auction logic
- Only affects summary statistics display

**Rollback**: Trivial (revert 2 lines)

**Testing**: Can validate immediately by comparing CSV columns with summary output

## References

- Issue discovered: 2026-02-02 during results review
- Affected file: [reporting.py:442-443](../../../auction-simulator/src/auction_simulator/reporting.py#L442-L443)
- Evidence: [summary_statistics_20260202_153520.txt](../../../auction-simulator/outputs/summary_statistics_20260202_153520.txt)
- CSV data: [ad_comparison_20260202_153520.csv](../../../auction-simulator/outputs/ad_comparison_20260202_153520.csv)
