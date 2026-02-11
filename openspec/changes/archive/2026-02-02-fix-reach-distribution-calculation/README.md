# Change: Fix Reach Distribution Calculation

**Status**: ✅ Completed (Ready for Archive)
**Change ID**: `fix-reach-distribution-calculation`
**Type**: Bug Fix
**Date**: 2026-02-02
**Completed**: 2026-02-02

## Quick Links

- [Proposal](./proposal.md) - Problem statement and root cause analysis
- [Tasks](./tasks.md) - Implementation checklist (3 tasks)
- [Spec Delta](./specs/reporting-enhancements/spec.md) - Added requirement for accurate calculation

## Problem Summary

"Reach Distribution Analysis" section in summary statistics shows **incorrect paid reach** (18.3% inflation) due to wrong column aggregation.

**Symptom:**
- Section 1 shows: "Paid Reach: Actual: 81,152" ✅
- Section 2 shows: "Paid Reach: Actual: 96,014" ❌
- Difference: **14,862 reach** (incorrect)

**Root Cause:**
```python
# WRONG (line 442):
paid_reach_actual = ad_comparison[ad_comparison['actual_reach_paid'] > 0]['actual_reach_total'].sum()
#                                                                         ^^^^^^^^^^^^^^^^^^
# Sums 'total' (paid+organic) instead of just 'paid'
```

## Solution

Change 2 lines in [reporting.py:442-443](../../../auction-simulator/src/auction_simulator/reporting.py#L442-L443):

```python
# CORRECT:
paid_reach_actual = ad_comparison['actual_reach_paid'].sum()
free_reach_actual = ad_comparison['actual_reach_organic'].sum()
```

## Impact

- ✅ **Consistency**: Both sections show same value (81,152)
- ✅ **Accuracy**: Matches CSV data exactly
- ✅ **Conservation**: `paid + organic = total` (81,152 + 152,654 = 233,806 ✓)
- ✅ **Risk**: Very low (display-only, no simulation logic)

## Files Changed

```
auction-simulator/src/auction_simulator/reporting.py (lines 442-443)
```

## Validation Command

```bash
python -m auction_simulator.cli simulate \
  --country 13 --categories 1361 \
  --time-from 2026-01-31 --time-to 2026-02-01 \
  --no-cache

# Check: Both "Paid Reach: Actual" sections should show 81,152
```

## Implementation Results

**All tasks completed successfully (2026-02-02 15:48:01):**
- ✅ Lines 442-443 in reporting.py fixed
- ✅ Simulation ran successfully
- ✅ Both "Paid Reach" sections now show 81,152 (was 96,014 vs 81,152)
- ✅ Conservation law validated: 81,152 + 152,654 = 233,806 ✓
- ✅ CSV data matches summary statistics exactly
- ✅ No other incorrect patterns found

**Evidence:**
- Output file: [summary_statistics_20260202_154801.txt](../../../auction-simulator/outputs/summary_statistics_20260202_154801.txt)
- CSV file: [ad_comparison_20260202_154801.csv](../../../auction-simulator/outputs/ad_comparison_20260202_154801.csv)

## Next Steps

1. ✅ Proposal created and validated
2. ✅ Implementation completed
3. ✅ Validation passed
4. ⏳ Ready for archive (after deployment)
