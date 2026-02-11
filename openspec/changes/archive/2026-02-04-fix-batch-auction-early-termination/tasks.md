# Tasks: Fix Batch Auction Early Termination

**Change ID**: `fix-batch-auction-early-termination`

## Task List

### 1. Update `run_hour_auction()` return type and tracking
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~340-349**:
- [x] Change return type from `-> int` to `-> dict`
- [x] Update docstring: "Returns dictionary with batch_count, paid_slots, organic_slots"
- [x] Add local variables: `paid_slots = 0`, `organic_slots = 0`

**Validation:**
- Type hints correct ✓
- Docstring updated ✓

**Estimated complexity:** Simple (1 signature change + 2 variables)

---

### 2. Remove early termination condition
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~402-403**:
- [x] Remove entire `if allocated < current_batch: break` block
- [x] Remove comment: `# If we couldn't fill the batch, no point continuing`

**Validation:**
- Lines deleted ✓
- No syntax errors ✓

**Estimated complexity:** Trivial (2 lines deleted)

---

### 3. Add per-batch organic fallback
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~398-410** (after paid auction call):
- [x] Track `allocated_paid` (rename from `allocated`)
- [x] Add condition: `if allocated_paid < current_batch:`
- [x] Calculate `remaining_in_batch = current_batch - allocated_paid`
- [x] Call `distribute_organic_proportional()` with `remaining_in_batch`
- [x] Update `slots_allocated += remaining_in_batch`
- [x] Track `organic_slots += remaining_in_batch`
- [x] Track `paid_slots += allocated_paid`

**New code structure**:
```python
allocated_paid = self.engine.run_batch_auction(...)
slots_allocated += allocated_paid
paid_slots += allocated_paid

if allocated_paid < current_batch:
    remaining_in_batch = current_batch - allocated_paid
    self.engine.distribute_organic_proportional(
        ads,
        remaining_in_batch,
        category_id=category_id,
        hour=hour,
        sim_logger=self.sim_logger
    )
    slots_allocated += remaining_in_batch
    organic_slots += remaining_in_batch
```

**Validation:**
- Organic fallback called when batch not filled ✓
- Slots correctly tracked ✓
- Conservation maintained ✓

**Estimated complexity:** Medium (~15 lines added)

---

### 4. Handle zero paid ads case
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~371-375**:
- [x] Change logic: instead of `break`, distribute entire batch via organic fallback
- [x] Add `continue` to skip to next batch

**New code**:
```python
if len(ads_with_budget) == 0:
    # No paid ads - distribute entire batch via organic fallback
    self.engine.distribute_organic_proportional(
        ads,
        current_batch,
        category_id=category_id,
        hour=hour,
        sim_logger=self.sim_logger
    )
    slots_allocated += current_batch
    organic_slots += current_batch
    continue  # Continue to next batch
```

**Validation:**
- Loop continues when no paid ads ✓
- All slots allocated via organic ✓

**Estimated complexity:** Medium (~10 lines changed)

---

### 5. Update return statement
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~405**:
- [x] Change `return batch_number` to `return {'batch_count': batch_number, 'paid_slots': paid_slots, 'organic_slots': organic_slots}`

**Validation:**
- Returns dict with 3 keys ✓
- Values match tracked counts ✓

**Estimated complexity:** Trivial (1 line changed)

---

### 6. Update caller `run_category_auctions()`
**File:** `auction-simulator/src/auction_simulator/simulation.py`

**Changes at line ~281-311**:
- [x] Change `batch_count = self.run_hour_auction(...)` to `auction_result = self.run_hour_auction(...)`
- [x] Extract values: `batch_count = auction_result['batch_count']`
- [x] Extract values: `paid_slots = auction_result['paid_slots']`
- [x] Extract values: `organic_slots = auction_result['organic_slots']`
- [x] Remove old paid_slots calculation: `paid_slots = sum(reach_after - reach_before)`
- [x] Remove old organic fallback call (now handled inside `run_hour_auction()`)
- [x] Remove `reach_before` tracking (no longer needed)

**Validation:**
- Caller uses new return format ✓
- No double counting ✓
- Logs show correct values ✓

**Estimated complexity:** Medium (~15 lines changed)

---

### 7. Update comments and docstrings
**Files:** `auction-simulator/src/auction_simulator/simulation.py`

- [x] Line ~280: Update comment to mention organic fallback is handled inside
- [x] Line ~350: Update docstring to explain per-batch fallback behavior
- [x] Line ~385: Update comment explaining fixed vs old behavior

**Validation:**
- Comments accurate ✓
- Docstrings complete ✓

**Estimated complexity:** Simple (documentation)

---

### 8. Add unit tests
**File:** `tests/test_batch_auction_continuation.py` (NEW)

- [x] Test: Multiple batches with few paid ads
  - Setup: 4 paid ads, 160 slots, batch_size=40
  - Assert: 4 batches run ✓
  - Assert: paid_slots = 16, organic_slots = 144 ✓

- [x] Test: Organic fallback called per batch
  - Setup: Mock organic fallback, track calls
  - Assert: Called 4 times (once per batch) ✓

- [x] Test: Conservation property
  - Setup: Various ads_with_budget and total_slots combinations
  - Assert: paid_slots + organic_slots == total_slots ✓

- [x] Test: Budget exhaustion stops loop
  - Setup: 2 ads with small budget (exhaust after 2 batches)
  - Assert: Loop stops when remaining_budget == 0 ✓

- [x] Test: Return dict structure
  - Assert: Returns dict with 3 keys (batch_count, paid_slots, organic_slots) ✓

**Validation:**
- Run tests: `pytest tests/test_batch_auction_continuation.py -v` ✓
- All 5 tests pass ✓

**Estimated complexity:** High (new test file, ~250 lines)

---

### 9. Run integration test
**Command:** Full simulation with small dataset

```bash
cd auction-simulator
python -m auction_simulator.cli simulate \
  --country 13 --categories 1366 \
  --time-from 2026-02-01 --time-to 2026-02-01 \
  --no-cache
```

**Verify:**
- [x] Simulation completes without errors ✓
- [x] Budget utilization > 40% (was 3.3%) ✓
- [x] Paid reach > 1,500 (was ~16) ✓
- [x] Organic reach < 9,000 (was ~10,400) ✓
- [x] Conservation: 10,409 == 10,409 ✓
- [x] Logs show 5-10 batches per hour (was 1) ✓

**Analysis**:
```python
import pandas as pd
df = pd.read_csv('outputs/ad_comparison_*.csv', comment='#')

paid = df[df['daily_budget_azn'] > 0]
print(f"Budget utilization: {100 * paid['simulated_spending_azn'].sum() / paid['daily_budget_azn'].sum():.1f}%")
print(f"Paid reach: {paid['simulated_reach_total'].sum()}")
print(f"Organic reach: {df[df['daily_budget_azn'] == 0]['simulated_reach_total'].sum()}")
```

**Expected output**:
```
Budget utilization: 46.9%
Paid reach: 1878
Organic reach: 8531
```

**Estimated complexity:** High (full end-to-end test)

---

### 10. Run regression tests
**Command:** Ensure existing tests still pass

```bash
cd auction-simulator
pytest tests/ -v
```

**Verify:**
- [x] All 22 existing tests pass ✓
- [x] New 5 tests pass ✓
- [x] Total: 27/27 tests pass ✓

**Estimated complexity:** Medium (validation)

---

### 11. Update documentation
**Files:** FAQ and CHANGELOG

- [x] Add FAQ entry: "Why do paid ads participate in multiple batches per hour?"
- [x] Explain: Batch can contain both paid and organic reach
- [x] Add CHANGELOG entry under [Unreleased]
- [x] Document fix: "Fixed batch auction early termination bug"
- [x] Document impact: Budget utilization improved from 3.3% to 46.9%

**Validation:**
- Documentation accurate ✓
- Examples clear ✓

**Estimated complexity:** Simple (documentation)

---

## Task Dependencies

```
1. Update return type
   ↓
2. Remove early break → 3. Add per-batch fallback → 5. Update return
   ↓                      ↓                           ↓
4. Handle zero ads  ──────┘                           │
   ↓                                                   │
6. Update caller ←───────────────────────────────────┘
   ↓
7. Update comments
   ↓
8. Add unit tests
   ↓
9. Integration test → 10. Regression tests
   ↓
11. Update documentation
```

## Parallelizable Work

- Tasks 7 (Comments) can be done in parallel with Tasks 2-6
- Task 8 (Unit tests) can be drafted in parallel with implementation
- Task 11 (Documentation) can start after Task 6 completes

## Completion Criteria

- [x] All 11 tasks completed ✓
- [x] All existing tests pass: `pytest tests/` (22/22) ✓
- [x] New tests pass and provide coverage (5 new tests) ✓
- [x] Integration test shows expected improvements ✓
  - Budget utilization: 3.3% → 46.9% (+1,318%)
  - Paid reach: ~16 → 1,878 (+117x)
  - Conservation: Perfect (10,409 == 10,409)
  - Multiple batches per hour (5-10 vs 1)
- [x] No regressions in simulation metrics ✓
- [x] Documentation updated and accurate ✓
- [ ] Code review approved (pending)
- [x] Change validated with real simulation run ✓

## Performance Impact

- **Organic fallback calls**: 5-10x per hour (was 1x per hour)
- **Per-call cost**: ~2ms for 600 ads
- **Total overhead**: ~10-20ms per hour (negligible)
- **Memory**: No change (no new data structures)

## Notes

- This fix is a prerequisite for bid_step optimization
- After this fix, 53% budget gap remains (due to low bid_step = 0.003)
- Conservation property maintained throughout
- No breaking changes to external interfaces
