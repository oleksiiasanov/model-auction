# Implementation Tasks

**Change ID**: `fix-reach-distribution-calculation`

## 1. Fix Calculation Logic

- [x] 1.1 Update `reporting.py:442-443` - Fix paid/organic reach calculation
  - File: `src/auction_simulator/reporting.py`
  - Change line 442: `paid_reach_actual = ad_comparison['actual_reach_paid'].sum()`
  - Change line 443: `free_reach_actual = ad_comparison['actual_reach_organic'].sum()`
  - Keep lines 445-446 unchanged (simulated calculation is correct)
  - Validation: Verify calculation uses correct column names
  - ✅ **Completed**: Lines 442-443 updated to use correct columns

## 2. Validation

- [x] 2.1 Run simulation for test period
  - Command: `python -m auction_simulator.cli simulate --country 13 --categories 1361 --time-from 2026-01-31 --time-to 2026-02-01 --no-cache`
  - Verify: "Paid Reach: Actual" in both sections matches (should be 81,152)
  - Verify: "Organic Reach: Actual" matches CSV sum (should be 152,654)
  - ✅ **Verified**: Both sections now show 81,152 for paid reach, 152,654 for organic reach

- [x] 2.2 Validate conservation law
  - Check: `paid_reach_actual + free_reach_actual == total_reach_actual`
  - Expected: 81,152 + 152,654 = 233,806 ✓
  - Compare with "Total Reach (user × ad × date combinations): Actual: 233,806"
  - ✅ **Validated**: Conservation law holds perfectly (81,152 + 152,654 = 233,806)

- [x] 2.3 Cross-check with CSV data
  - Extract from `ad_comparison_*.csv`:
    ```bash
    # Sum actual_reach_paid column (column 8)
    awk -F',' 'NR>6 {paid+=$8; organic+=$7} END {print "Paid:", paid, "Organic:", organic}' outputs/ad_comparison_*.csv
    ```
  - Verify matches summary statistics exactly
  - ✅ **Cross-checked**: CSV shows paid=81,152, organic=152,654 (exact match with summary)

## 3. Documentation

- [x] 3.1 Update spec delta (if needed)
  - File: `openspec/changes/fix-reach-distribution-calculation/specs/reporting-enhancements/spec.md`
  - Add scenario validating correct column usage in reach distribution
  - Note: May be optional since this is bug fix, not new requirement
  - ✅ **Already created**: Spec delta includes 8 scenarios for correct calculation

- [x] 3.2 Verify no other usages of same pattern
  - Search for similar incorrect patterns in reporting.py
  - Check seller_comparison calculation uses correct logic
  - Validation: `grep -n "actual_reach_total" src/auction_simulator/reporting.py`
  - ✅ **Verified**: All other usages of actual_reach_total are correct (diff calculations, count filters)

## Task Dependencies

```
Task 1.1 (fix code)
    ↓
Task 2.1 (run simulation) → Task 2.2 (validate conservation) → Task 2.3 (CSV check)
    ↓
Task 3.1 (update spec) ← Task 3.2 (verify no other issues)
```

## Completion Criteria

- ✅ Both "Paid Reach" sections show identical actual values (81,152)
- ✅ Conservation law holds: paid + organic = total (no rounding errors)
- ✅ CSV data matches summary statistics exactly
- ✅ No other incorrect calculations found in reporting.py
- ✅ Simulation runs successfully without errors

## Notes

- **Scope**: Single 2-line fix in reporting.py
- **Risk**: Very low (display-only change, no simulation logic affected)
- **Testing**: Can validate immediately with existing CSV output
- **No breaking changes**: Output format unchanged, only values corrected
