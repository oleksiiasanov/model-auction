# Critical Bugs Fixed During Development

This document tracks critical bugs discovered and fixed during simulator development. These insights are valuable for production implementation.

---

## Bug #1: Zero-Budget Ads Winning Paid Auction Slots

**Date Discovered**: 2026-02-04
**Severity**: 🔴 CRITICAL
**Impact**: ~78% of reach (182k slots) incorrectly distributed through auction instead of organic fallback

### Root Cause

**Location**: `simulation.py:385` (before fix)

```python
# WRONG: Passed all ads including zero-budget
allocated = self.engine.run_batch_auction(
    ads,  # ❌ Contains 8000+ zero-budget ads
    min_bid,
    ...
)
```

**Failure Chain**:
1. `run_hour_auction()` checked if any ads have `remaining_budget > 0`
2. If yes, called `run_batch_auction()` with **all ads** (not just ads_with_budget)
3. `check_pacing_gate()` always returns `True` for zero-budget ads (line 84-85):
   ```python
   if ad.daily_budget <= 0:
       return True  # Always eligible
   ```
4. Zero-budget ads get `pressure=0` but still participate in ranking
5. When paid ads are paused by pacing gate (also `pressure=0`), ranking becomes tie-breaking by `ad_id`
6. Zero-budget ads with lower `ad_id` win slots **without paying**
7. `charge_winners()` checks `if ad.remaining_budget > 0` before charging, so zero-budget ads pay nothing

**Result**: Zero-budget ads won ~180k reach slots for free through auction, bypassing organic fallback.

### Problem Details

**Observed Behavior**:
- Ad #33699836 (zero-budget): Won 4,618 auction batches, received 4,833 reach, paid 0 AZN
- Batches 33-35 in hour 0: All 40 winners had `pressure=0` and `budget=0`
- 9,884 pacing exclusions in batches 32-33: Paid ads blocked, zero-budget ads won

**Why It Happened**:
- Pacing gate blocks paid ads that spent too much → `pressure=0`
- Zero-budget ads always eligible → also `pressure=0`
- Tie-breaking by `ad_id` → zero-budget ads with lower IDs rank higher
- No budget check in `select_winners()` → zero-budget ads selected as winners

### Solution

**Fix**: Pass only `ads_with_budget` to auction

```python
# CORRECT: Only ads with budget can participate in paid auction
allocated = self.engine.run_batch_auction(
    ads_with_budget,  # ✅ Only remaining_budget > 0
    min_bid,
    ...
)
```

**Location**: `simulation.py:387` (after fix)

**Rationale**:
- Paid auction is for ads that can pay
- Zero-budget ads should **only** receive reach through organic fallback
- Organic fallback uses proportional distribution by historical organic reach
- This matches production behavior (ads without budget can't bid)

### Impact After Fix

| Metric | Before (Bug) | After (Fix) | Improvement |
|--------|-------------|-------------|-------------|
| **Organic ads with reach** | 249 (3%) | 4,428 (54%) | **17.8x** ↑ |
| **Organic fallback slots** | 652 (0.3%) | 182,576 (78%) | **280x** ↑ |
| **Paid reach** | 51,073 (22%) | 67,998 (29%) | More realistic |
| **Spending** | 207.95 AZN | 161.80 AZN | More conservative |

### Production Implications

**For Production Implementation**:
1. ✅ **Auction participation MUST require budget > 0**
   - Check `remaining_budget > 0` BEFORE adding to ranked list
   - Don't rely on `pressure=0` filtering (pacing gate can cause this for paid ads)

2. ✅ **Separate paid and organic reach mechanisms**
   - Paid: Auction with bidding (requires budget)
   - Organic: Natural distribution (no budget required)
   - Never mix the two

3. ⚠️ **Pacing gate side effect**
   - Pacing gate sets `pressure=0` for over-spending ads
   - This doesn't mean "no budget", it means "paused temporarily"
   - Budget check is separate: `remaining_budget > 0`

4. ⚠️ **Tie-breaking matters**
   - When multiple ads have same pressure, tie-breaking determines winners
   - If not filtered by budget first, zero-budget ads can slip through
   - Always filter BEFORE ranking, not after

### Testing Recommendations

**Red Flags to Watch**:
- Ads with `simulated_spending=0` but `simulated_reach>0` → likely won without paying
- Organic fallback triggers rarely (<5% of slots) → paid auction filling too much
- Many ads with `pressure=0` winning slots → pacing gate + zero-budget mixing issue

**Validation Checks**:
```python
# After simulation, check:
zero_budget_ads = ads[ads['daily_budget'] == 0]
winners = zero_budget_ads[zero_budget_ads['simulated_reach'] > 0]
paid_winners = winners[winners['simulated_spending'] > 0]

assert len(paid_winners) == 0, "Zero-budget ads should never pay!"
```

### Related Code

**Key Files**:
- `simulation.py:369-402` - `run_hour_auction()` loop
- `auction_engine.py:84-85` - `check_pacing_gate()` zero-budget bypass
- `auction_engine.py:229-244` - `charge_winners()` budget check
- `auction_engine.py:379-473` - `distribute_organic_proportional()` fallback

**Key Logic**:
- `ads_with_budget = [ad for ad in ads if ad.remaining_budget > 0]` - Filter before auction
- `if ad.daily_budget <= 0: return True` - Pacing gate always passes zero-budget
- `if ad.remaining_budget > 0:` - Charge check (doesn't prevent winning)

---

## Bug #2: Batch Auction Early Termination

**Date Discovered**: 2026-02-04
**Severity**: 🔴 CRITICAL
**Impact**: Budget utilization only 3.3% (should be 46.9%+)

### Root Cause

**Location**: `simulation.py:402-403` (before fix)

```python
# WRONG: Stops after first batch when paid ads < batch_size
if allocated < current_batch:
    break  # ❌ STOPS here - exits loop entirely
```

**Failure Chain**:
1. When `ads_with_budget < batch_size`, paid auction can never fill a full batch
2. Early `break` prevents paid ads from participating in subsequent batches
3. Organic fallback is called ONCE at the end for all remaining slots
4. Paid ads retain their budget but cannot spend it

**Result**: Paid ads participate in only 1 batch per hour, leaving 96.7% of budget unused.

### Problem Details

**Observed Behavior**:
- Hour 10: 132 total slots, batch_size=40, 4 paid ads with budget
- Batch 1: 4 paid ads buy 1 reach each = 4 slots
- Early break → loop exits
- Remaining 128 slots distributed via organic fallback ONCE
- Paid ads still have budget but cannot participate in batches 2-4

**Why It Happened**:
- Logic assumed: "If we couldn't fill the batch, no point continuing"
- This is wrong when `ads_with_budget < batch_size` (common scenario)
- Paid ads should participate in ALL batches until budget exhausted

### Solution

**Fix**: Removed early break, organic fallback now called per-batch

```python
# CORRECT: Continue processing all batches
while slots_allocated < total_slots:
    # ... paid auction ...
    if allocated_paid < current_batch:
        # Fill remaining slots via organic fallback per-batch
        remaining_in_batch = current_batch - allocated_paid
        self.engine.distribute_organic_with_pool_split(...)
    # Continue to next batch (no break!)
```

**Location**: `simulation.py:462-470` (after fix)

**Rationale**:
- Paid ads should participate in multiple batches per hour
- Each batch: paid auction first, organic fallback fills remaining slots
- Process continues until all slots allocated OR budget exhausted
- Matches production behavior where ads can bid multiple times per hour

### Impact After Fix

| Metric | Before (Bug) | After (Fix) | Improvement |
|--------|-------------|-------------|-------------|
| **Budget utilization** | 3.3% (0.06 AZN) | 46.9% (1.50 AZN) | **+1,318%** ↑ |
| **Paid reach per hour** | ~16 | ~1,878 | **+117x** ↑ |
| **Organic reach** | ~10,400 | ~8,531 | More realistic |
| **Batches per hour** | 1 | 5-10 | **5-10x** ↑ |

### Production Implications

**For Production Implementation**:
1. ✅ **Never stop auction early based on batch fill rate**
   - Continue processing batches until slots exhausted OR budget exhausted
   - Each batch is independent: paid auction first, then organic fallback

2. ✅ **Organic fallback should be per-batch, not per-hour**
   - Distribute remaining slots immediately after each paid auction
   - Don't accumulate slots for single distribution at end

3. ⚠️ **Batch size vs number of paid ads**
   - When `ads_with_budget < batch_size`, paid auction fills < batch_size slots
   - This is expected and normal - organic fallback fills the rest
   - Don't treat this as an error condition

### Testing Recommendations

**Red Flags to Watch**:
- Budget utilization < 10% → likely early termination bug
- Paid ads participate in only 1 batch per hour → early break present
- Organic fallback called once per hour instead of per-batch → wrong implementation

**Validation Checks**:
```python
# After simulation, check:
for hour in hours:
    batches = count_batches(hour)
    assert batches > 1, "Should process multiple batches per hour"
    
budget_utilization = total_spent / total_budget
assert budget_utilization > 0.4, "Budget utilization too low, check early termination"
```

### Related Code

**Key Files**:
- `simulation.py:407-489` - `run_hour_auction()` batch loop
- `simulation.py:462-470` - Organic fallback per-batch logic

**Key Logic**:
- `while slots_allocated < total_slots:` - Continue until all slots allocated
- `if allocated_paid < current_batch:` - Fill remaining slots via organic fallback
- No early break - loop continues naturally

---

## Bug #3: Organic Fallback Used Wrong Historical Metric

**Date Discovered**: 2026-02-04
**Severity**: 🟡 HIGH
**Impact**: 1,471 promoted-without-budget ads received 0 simulated reach

### Root Cause

**Location**: `auction_engine.py:434` (before fix)

```python
# WRONG: Used organic_reach_historical
total_reach_sum = sum(ad.organic_reach_historical for ad in ads)
proportions = {ad.ad_id: ad.organic_reach_historical / total_reach_sum for ad in ads}
```

**Failure Chain**:
1. Promoted ads have `organic_reach_historical=0` (they were paid-only)
2. But they have `total_reach_historical>0` (paid + organic combined)
3. Proportional allocation: `0 / total_sum = 0` → no allocation
4. 1,471 ads that were popular when promoted received 0 organic reach

**Result**: Ads that were popular when promoted (but now have no budget) received no organic reach in simulation.

### Problem Details

**Observed Behavior**:
- Ad #12345: `daily_budget=0`, `organic_reach_historical=0`, `total_reach_historical=500`
- Proportional allocation: `0 / total_sum = 0` → 0 slots allocated
- Ad #12345 receives 0 simulated reach despite being popular when promoted

**Why It Happened**:
- Logic assumed: "Use organic reach for organic fallback"
- This is wrong for ads that were promoted (paid-only) but now have no budget
- These ads deserve organic reach based on their total popularity, not just organic-only views

### Solution

**Fix**: Changed to `total_reach_historical` for proportional distribution

```python
# CORRECT: Use total_reach_historical (paid + organic)
total_reach_sum = sum(ad.total_reach_historical for ad in ads)
proportions = {ad.ad_id: ad.total_reach_historical / total_reach_sum for ad in ads}
```

**Location**: `auction_engine.py:434`, `auction_engine.py:763` (after fix)

**Rationale**:
- Total reach reflects overall ad popularity (paid + organic)
- Promoted ads should receive organic reach when budget exhausts
- Better matches production behavior where popular ads retain visibility

### Impact After Fix

| Metric | Before (Bug) | After (Fix) | Improvement |
|--------|-------------|-------------|-------------|
| **Promoted-without-budget ads with reach** | 0 (0%) | 1,471 (100%) | **∞** ↑ |
| **Low-reach organic ads coverage** | 44% | 99.3% | **+125%** ↑ |
| **Organic fallback distribution** | Skewed to organic-only ads | Balanced across all ads | More realistic |

### Production Implications

**For Production Implementation**:
1. ✅ **Use total reach (paid + organic) for organic fallback proportions**
   - Reflects overall ad popularity, not just organic-only views
   - Ensures promoted ads receive organic reach when budget exhausts

2. ✅ **Don't exclude promoted ads from organic distribution**
   - Ads that were popular when promoted deserve organic visibility
   - Total reach is the correct metric for popularity

### Testing Recommendations

**Red Flags to Watch**:
- Promoted-without-budget ads have `simulated_reach=0` → wrong metric used
- Organic fallback heavily skewed to organic-only ads → check proportions
- Coverage < 50% for free ads → likely wrong metric or floor issues

**Validation Checks**:
```python
# After simulation, check:
promoted_no_budget = ads[(ads['daily_budget'] == 0) & (ads['total_reach_historical'] > 0)]
with_reach = promoted_no_budget[promoted_no_budget['simulated_reach'] > 0]

assert len(with_reach) / len(promoted_no_budget) > 0.9, \
    "Promoted ads without budget should receive organic reach"
```

### Related Code

**Key Files**:
- `auction_engine.py:434` - Proportional allocation calculation
- `auction_engine.py:763` - Cumulative allocator proportions
- `data_extraction.py:250-276` - Data extraction (now uses `total_reach`)

**Key Logic**:
- `total_reach_historical` - Total historical reach (paid + organic)
- `organic_reach_historical` - Only organic historical reach (deprecated for fallback)

---

## Bug #4: Pacing Gate Hour Zero Blocking

**Date Discovered**: 2026-01-30
**Severity**: 🔴 CRITICAL
**Impact**: 98.5% paid impressions vs 3.6% actual (27x inflation)

### Root Cause

**Location**: `auction_engine.py:109` (before fix)

```python
# WRONG: At hour 0, time_progress=0 causes max_allowed=0
time_progress = hour / 24.0  # At hour 0: 0.0
expected_spend = daily_budget × 0.0 = 0 kopecks
max_allowed = 0 × (1 + pacing_tolerance) = 0 kopecks

# After first auction win:
actual_spend = 0.15 kopecks
0.15 > 0 → ❌ BLOCKED for remaining 59 batches in hour 0
```

**Failure Chain**:
1. At hour 0, `time_progress = 0 / 24.0 = 0.0`
2. `expected_spend = daily_budget × 0.0 = 0`
3. `max_allowed = 0 × (1 + pacing_tolerance) = 0`
4. Any ad that wins even 1 auction has `actual_spend > 0`
5. Pacing gate blocks all ads for remaining batches in hour 0
6. N (ads with budget) remains constant at 81 throughout day

**Result**: All paid ads blocked after first batch at hour 0, causing massive inflation in paid impressions.

### Problem Details

**Observed Behavior**:
- Hour 0: Batch 1: 40 ads win auctions, pay ~0.15 kopecks each
- Hour 0: Batches 2-60: All ads blocked by pacing gate (`actual_spend > max_allowed=0`)
- Result: 98.5% paid impressions vs 3.6% actual (27x inflation)
- N stays at 81 all day instead of decreasing naturally

**Why It Happened**:
- Pacing gate formula: `expected_spend = daily_budget × time_progress`
- At hour 0, `time_progress=0` → `max_allowed=0`
- No minimum threshold to prevent zero-value edge case

### Solution

**Fix**: Added `min_time_progress_threshold` parameter

```python
# CORRECT: Use minimum threshold to prevent zero max_allowed
safe_time_progress = max(time_progress, self.min_time_progress_threshold)
expected_spend = daily_budget × safe_time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

**Location**: `auction_engine.py:109` (after fix)
**Config**: `config.yaml: min_time_progress_threshold: 0.042` (1 hour = 1/24)

**Rationale**:
- Symmetric to existing `min_time_left_threshold` pattern
- Prevents zero-value edge case at hour 0
- Allows ~5% budget in first hour with tolerance=0.2
- Works for all hours, not just hour=0 special case

### Impact After Fix

| Metric | Before (Bug) | After (Fix) | Improvement |
|--------|-------------|-------------|-------------|
| **Paid impressions** | 98.5% | ~3.6% | **27x reduction** ↓ |
| **Organic impressions** | 1.5% | ~96.4% | **64x increase** ↑ |
| **N stability** | 81 constant | Decreases gradually | Natural decrease |
| **max_allowed at hour 0** | 0.00 kopecks | 5.04 kopecks | **∞ improvement** |

### Production Implications

**For Production Implementation**:
1. ✅ **Always use minimum threshold for time_progress**
   - Prevents zero-value edge cases
   - Recommended: `min_time_progress_threshold = 1 hour = 1/24 = 0.042`

2. ✅ **Test pacing gate at hour 0**
   - Ensure ads can participate in first hour
   - Verify `max_allowed > 0` at hour 0

3. ⚠️ **Pacing gate is approximate**
   - Simulator uses simplified logic
   - Production may have more sophisticated pacing algorithms

### Testing Recommendations

**Red Flags to Watch**:
- Paid impressions > 90% → likely hour 0 blocking bug
- N stays constant throughout day → pacing gate blocking all ads
- `max_allowed=0` at hour 0 → missing threshold

**Validation Checks**:
```python
# After simulation, check:
hour_0_paid = get_paid_impressions(hour=0)
total_paid = get_total_paid_impressions()

assert hour_0_paid / total_paid < 0.1, \
    "Hour 0 should not dominate paid impressions (check pacing gate)"

# Check pacing gate at hour 0
time_progress = 0.0
safe_time_progress = max(time_progress, 0.042)
max_allowed = daily_budget * safe_time_progress * 1.2

assert max_allowed > 0, "max_allowed should be > 0 at hour 0"
```

### Related Code

**Key Files**:
- `auction_engine.py:92-120` - `check_pacing_gate()` method
- `config.yaml:13` - `min_time_progress_threshold` configuration

**Key Logic**:
- `safe_time_progress = max(time_progress, min_time_progress_threshold)`
- `expected_spend = daily_budget × safe_time_progress`
- `max_allowed = expected_spend × (1 + pacing_tolerance)`

---

## Bug #5: Fractional Kopecks Rounding

**Date Discovered**: 2026-01-30
**Severity**: 🟡 HIGH
**Impact**: Budgets not decreasing due to integer rounding (rounding to 0 kopecks)

### Root Cause

**Location**: `auction_engine.py:229-244` (before fix)

```python
# WRONG: Integer rounding loses small bids
daily_budget: int  # Integer kopecks
remaining_budget: int  # Integer kopecks

effective_bid = 0.1469 kopecks  # Small bid with bid_step=0.001
cost_integer = round(0.1469)  # = 0 kopecks
ad.remaining_budget -= 0  # Budget doesn't decrease!
```

**Failure Chain**:
1. With `bid_step=0.001`, all bids are < 0.5 kopecks
2. `round(0.1469) = 0` kopecks (rounds to nearest integer)
3. Budget deduction: `remaining_budget -= 0` → budget unchanged
4. Ads can participate indefinitely without spending budget
5. N (ads with budget) stays constant at 81 throughout day

**Result**: Budgets never decrease, ads participate indefinitely, spending accuracy broken.

### Problem Details

**Observed Behavior**:
- Ad with `daily_budget=165` kopecks
- Wins auction with `effective_bid=0.1469` kopecks
- `cost_integer = round(0.1469) = 0` kopecks
- `remaining_budget = 165 - 0 = 165` (unchanged!)
- Ad continues participating in all auctions without spending

**Why It Happened**:
- Budgets stored as `int` (integer kopecks)
- Small bids (< 0.5 kopecks) round to 0
- No fractional kopecks support

### Solution

**Fix**: Changed to `float` for fractional kopecks support

```python
# CORRECT: Support fractional kopecks
daily_budget: float  # Fractional kopecks
remaining_budget: float  # Fractional kopecks

effective_bid = 0.1469 kopecks
ad.remaining_budget -= effective_bid  # Exact deduction, no rounding
```

**Location**: `auction_engine.py:21-22` (Ad dataclass), `auction_engine.py:229-244` (charge_winners)

**Rationale**:
- Fractional kopecks are necessary for small bid_step values
- Exact budget tracking without rounding errors
- Matches production behavior where costs can be fractional

### Impact After Fix

| Metric | Before (Bug) | After (Fix) | Improvement |
|--------|-------------|-------------|-------------|
| **Budget tracking** | Broken (rounding to 0) | Accurate (fractional) | **∞** ↑ |
| **N stability** | 81 constant | Decreases naturally | Natural decrease |
| **Spending accuracy** | Broken | 91-94% accurate | **Working** ✅ |

### Production Implications

**For Production Implementation**:
1. ✅ **Support fractional kopecks in budget tracking**
   - Use `float` or `Decimal` for budget values
   - Don't round costs before deduction

2. ✅ **Test with small bid_step values**
   - Verify budgets decrease correctly
   - Check that N decreases naturally throughout day

3. ⚠️ **Precision considerations**
   - `float` has precision limits (use `Decimal` if needed)
   - For kopecks, `float` is usually sufficient (0.001 precision)

### Testing Recommendations

**Red Flags to Watch**:
- Budgets not decreasing → likely integer rounding bug
- N stays constant throughout day → budgets not being spent
- Spending accuracy < 50% → check budget tracking

**Validation Checks**:
```python
# After simulation, check:
for ad in ads:
    if ad.daily_budget > 0:
        expected_decrease = ad.daily_budget - ad.remaining_budget
        assert expected_decrease > 0, \
            f"Ad {ad.ad_id} should have spent budget (decrease={expected_decrease})"
        
        # Check that spending matches budget decrease
        assert abs(ad.simulated_spending - expected_decrease) < 0.01, \
            f"Spending mismatch for ad {ad.ad_id}"
```

### Related Code

**Key Files**:
- `auction_engine.py:15-27` - `Ad` dataclass definition
- `auction_engine.py:229-244` - `charge_winners()` budget deduction
- `simulation.py:90` - Budget initialization from data

**Key Logic**:
- `daily_budget: float` - Fractional kopecks support
- `remaining_budget: float` - Fractional kopecks support
- `ad.remaining_budget -= effective_bid` - Exact deduction, no rounding

---

## Future Sections

Additional bugs will be documented here as they are discovered and fixed.

**Template**:
- Bug title
- Date discovered
- Severity (🔴 CRITICAL, 🟡 HIGH, 🟢 MEDIUM, 🔵 LOW)
- Root cause with code references
- Problem details
- Solution
- Impact before/after
- Production implications
- Testing recommendations
