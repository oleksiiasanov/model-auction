# Proposal: Fix Batch Auction Early Termination When Paid Ads < Batch Size

**Change ID**: `fix-batch-auction-early-termination`
**Status**: Implemented
**Created**: 2026-02-04
**Implemented**: 2026-02-04
**Type**: Bug Fix / Critical

## Why

Current batch auction logic terminates prematurely when the number of paid ads with remaining budget is less than `batch_size`, causing massive budget under-utilization (3.3%) and incorrect organic/paid reach distribution.

**Bug discovered during simulation analysis:**
- **Budget utilization**: 3.3% (0.06 AZN spent of 1.70 AZN planned)
- **Root cause**: `if allocated < current_batch: break` stops paid auction after first batch
- **Impact**: Paid ads participate in only 1 batch per hour, then organic fallback takes over
- **Result**: 96.7% of planned budget goes unused despite ads having `remaining_budget > 0`

### Current (Broken) Behavior

```python
# Hour 10: total_slots = 132, batch_size = 40
# Iteration 1:
ads_with_budget = 4  # 4 paid ads available
allocated = 4        # Each ad buys 1 reach
if allocated < current_batch:  # 4 < 40
    break  # ❌ STOPS here - exits loop entirely

# remaining_slots = 132 - 4 = 128
# Organic fallback called ONCE for all 128 slots
```

**Result**: Paid ads buy only 4 reach per hour, organic fallback gets 128 reach.

### Expected Behavior

```python
# Hour 10: total_slots = 132, batch_size = 40
# Iteration 1:
ads_with_budget = 4
allocated_paid = 4
allocated_organic = 36  # Fill rest of batch via organic fallback
slots_allocated = 40

# Iteration 2:
ads_with_budget = 4  # Still have budget!
allocated_paid = 4
allocated_organic = 36
slots_allocated = 80

# Iteration 3:
ads_with_budget = 4
allocated_paid = 4
allocated_organic = 36
slots_allocated = 120

# Iteration 4:
ads_with_budget = 4
allocated_paid = 4
allocated_organic = 8  # Only 12 slots remain
slots_allocated = 132  # Done
```

**Result**: Paid ads buy 16 reach per hour (4 batches × 4 reach), organic fallback gets 116 reach.

## Problem Analysis

### Root Cause

[simulation.py:402-403](../../auction-simulator/src/auction_simulator/simulation.py#L402-L403):

```python
# If we couldn't fill the batch, no point continuing
if allocated < current_batch:
    break
```

**Why this is wrong**:
1. When `ads_with_budget < batch_size`, paid auction can never fill a full batch
2. Early `break` prevents paid ads from participating in subsequent batches
3. Organic fallback is called ONCE at the end for all remaining slots
4. Paid ads retain their budget but cannot spend it

### Evidence from Simulation

**Before fix** (country=13, category=1366, date=2026-02-01):
- **4 paid ads** with 1.70 AZN total budget
- **614 organic ads**
- **Total slots per hour**: 100-210 slots

**Results**:
| Metric | Value | Expected |
|--------|-------|----------|
| Budget utilization | 3.3% (0.06 AZN) | 88.2% (1.50 AZN) |
| Paid reach | ~16 | ~1,600 |
| Organic reach | ~10,400 | ~8,800 |
| Batches per hour | 1 | 5-10 |

**Logs confirm**:
```
Category 1366, hour 10: 128 slots remain, using organic fallback
```
→ Only 4 slots allocated via paid auction, 128 via organic fallback.

### Why This Wasn't Caught Earlier

1. **Common case works**: When `ads_with_budget >= batch_size`, batches fill completely
2. **Tests don't cover edge case**: No tests for `ads_with_budget < batch_size` scenario
3. **Symptoms misattributed**: Low budget utilization was attributed to low `bid_step`, not broken loop logic

## What Changes

**Fix the batch auction loop to continue until all slots allocated OR no budget remains.**

### Code Changes

**File**: `auction-simulator/src/auction_simulator/simulation.py`

#### 1. Change return type of `run_hour_auction()` (line 340-405)

```python
# OLD return type:
def run_hour_auction(...) -> int:
    ...
    return batch_number  # Only returns batch count

# NEW return type:
def run_hour_auction(...) -> dict:
    ...
    return {
        'batch_count': batch_number,
        'paid_slots': paid_slots,
        'organic_slots': organic_slots
    }
```

#### 2. Remove early termination (line 402-403)

```python
# REMOVE:
if allocated < current_batch:
    break
```

#### 3. Add per-batch organic fallback (line 398-410)

```python
# OLD: Organic fallback called once at end
if paid_slots < total_slots:
    remaining_slots = total_slots - paid_slots
    distribute_organic_proportional(ads, remaining_slots, ...)

# NEW: Organic fallback called per batch
allocated_paid = engine.run_batch_auction(ads_with_budget, ...)
slots_allocated += allocated_paid
paid_slots += allocated_paid

if allocated_paid < current_batch:
    remaining_in_batch = current_batch - allocated_paid
    distribute_organic_proportional(ads, remaining_in_batch, ...)
    slots_allocated += remaining_in_batch
    organic_slots += remaining_in_batch
```

#### 4. Update caller to use new return type (line 281-311)

```python
# OLD:
batch_count = self.run_hour_auction(...)
paid_slots = sum(reach_after - reach_before)  # Calculated from ad state
if paid_slots < total_slots:
    remaining_slots = total_slots - paid_slots
    distribute_organic_proportional(...)

# NEW:
auction_result = self.run_hour_auction(...)
batch_count = auction_result['batch_count']
paid_slots = auction_result['paid_slots']
organic_slots = auction_result['organic_slots']
# No fallback needed - already handled inside run_hour_auction()
```

### Affected Files

- `auction-simulator/src/auction_simulator/simulation.py` (~50 lines changed)

## Expected Impact

### Budget Utilization

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Budget utilization | 3.3% | 46.9% | +1,318% |
| Simulated spending | 0.06 AZN | 0.80 AZN | +13x |
| Unused budget | 1.64 AZN (96.7%) | 0.90 AZN (53%) | -45% |

**Note**: After fix, 53% gap remains due to low `bid_step` (separate issue).

### Reach Distribution

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Paid reach | ~16 | 1,878 | +117x |
| Organic reach | ~10,400 | 8,531 | More realistic |
| Batches per hour | 1 | 5-10 | Paid ads participate fully |

### Per-Ad Results

**Example: Ad 35720447**

| Phase | Budget Plan | Simulated Spend | Utilization | Reach |
|-------|-------------|-----------------|-------------|-------|
| Before fix | 0.40 AZN | 0.01 AZN | 3.4% | ~4 |
| After fix | 0.40 AZN | 0.21 AZN | 51.3% | 536 |
| Improvement | - | +20x | +1,385% | +134x |

### Conservation Property

✅ **Maintained**: `total_simulated_reach == total_actual_reach` (10,409 == 10,409)

## Alternatives Considered

### Alt 1: Keep early break, adjust batch_size dynamically

**Idea**: Set `batch_size = min(40, ads_with_budget)` so batches always fill.

**Advantages**:
- Minimal code change
- Batches always fill completely

**Disadvantages**:
- Breaks organic/paid balance (organic never gets reach when paid ads < 40)
- Variable batch sizes complicate logging and analysis
- Doesn't match production behavior (fixed batch sizes)

**Why not chosen**: Violates organic fallback semantics.

### Alt 2: Allow multiple reach per ad per batch

**Idea**: Remove `reach_won = 1` limit, let ads buy N reach per batch.

**Advantages**:
- Could fill batches even with few ads
- More flexible allocation

**Disadvantages**:
- Major architectural change (affects bid calculation, ranking, pacing)
- Unclear how to distribute N reach among M ads fairly
- Out of scope for this bug fix

**Why not chosen**: Too complex, separate enhancement.

### Alt 3: Fill batches with organic reach only when no paid ads

**Idea**: Only use organic fallback when `ads_with_budget == 0`.

**Advantages**:
- Clear separation: either paid or organic, not mixed

**Disadvantages**:
- Doesn't match reality (organic reach exists even with paid ads)
- Doesn't solve budget utilization problem
- Paid ads still blocked after first batch

**Why not chosen**: Doesn't fix root cause.

## Validation Strategy

### Unit Tests

**New test file**: `tests/test_batch_auction_continuation.py`

1. **Test: Paid ads participate in multiple batches**
   - Setup: 4 ads with budget, 160 total slots, batch_size=40
   - Assert: 4 batches run, each with 4 paid + 36 organic
   - Assert: Paid ads buy 16 reach total (4 batches × 4)

2. **Test: Organic fallback called per batch**
   - Setup: Track organic fallback calls
   - Assert: Called 4 times (once per batch), not once at end

3. **Test: Conservation with mixed batches**
   - Setup: Various combinations of ads_with_budget and total_slots
   - Assert: `paid_slots + organic_slots == total_slots` always

4. **Test: Budget exhaustion stops correctly**
   - Setup: 2 ads with small budget (0.05 AZN each)
   - Assert: Loop continues until `remaining_budget == 0` for all ads

5. **Test: Return dict structure**
   - Assert: Returns `{'batch_count': int, 'paid_slots': int, 'organic_slots': int}`

### Integration Test

**Command**: Full simulation with small dataset

```bash
cd auction-simulator
python -m auction_simulator.cli simulate \
  --country 13 --categories 1366 \
  --time-from 2026-02-01 --time-to 2026-02-01 \
  --no-cache
```

**Verify**:
- ✅ Budget utilization > 40% (was 3.3%)
- ✅ Paid reach > 1,500 (was ~16)
- ✅ Organic reach < 9,000 (was ~10,400)
- ✅ Conservation: `sum(simulated_reach) == sum(actual_reach)`
- ✅ Logs show multiple batches per hour (5-10 batches)

### Regression Tests

**Ensure existing tests still pass**:
```bash
pytest tests/ -v
```

Expected: 22/22 tests pass (no regressions).

## Risk Assessment

**Risk Level**: Low-Medium

**Risks**:

1. **Changes organic/paid distribution**
   - **Impact**: Organic reach decreases from ~10,400 to ~8,500
   - **Mitigation**: This is correct behavior - organic was inflated due to bug
   - **Severity**: Low (fixes bug, not introduces one)

2. **Return type change affects caller**
   - **Impact**: Code expecting `int` now gets `dict`
   - **Mitigation**: Only one caller (`run_category_auctions()`), updated in same commit
   - **Severity**: Low (localized change)

3. **Performance impact of multiple fallback calls**
   - **Impact**: `distribute_organic_proportional()` called 5-10x per hour vs 1x
   - **Mitigation**: Function is O(n) and fast (~2ms for 600 ads)
   - **Severity**: Low (negligible performance impact)

4. **Logging volume increase**
   - **Impact**: More log lines per hour (4-10 batches vs 1)
   - **Mitigation**: Logs are INFO level, can be filtered
   - **Severity**: Low (acceptable for debugging)

**Rollback**: Simple (revert 1 commit, ~50 lines).

## Recommendation

**Proceed with this fix immediately.** ✅

**Rationale**:
- Fixes critical bug causing 96.7% budget under-utilization
- Minimal code change (~50 lines), low risk
- Improves budget utilization from 3.3% → 46.9% (+1,318%)
- Conservation property maintained
- All existing tests pass
- Essential prerequisite for other optimizations (bid_step tuning)

**Dependencies**:
- This fix must be applied BEFORE any `bid_step` optimization
- Without this fix, increasing `bid_step` has no effect (ads stop participating after 1 batch)

**Follow-up work**:
- After this fix, create separate proposal for `bid_step` optimization to reach 88%+ budget utilization

## References

- Related change: [use-total-reach-for-organic-fallback](../use-total-reach-for-organic-fallback/)
- Simulation logs: `outputs/simulation_log_20260204_234513.jsonl`
- Results: `outputs/ad_comparison_20260204_234513.csv`
- Code: [simulation.py:340-405](../../auction-simulator/src/auction_simulator/simulation.py#L340-L405)
