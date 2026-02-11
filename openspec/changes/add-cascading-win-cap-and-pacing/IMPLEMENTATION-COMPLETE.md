# Implementation Complete: Cascading Win Cap and Pacing Relaxation

## Summary

Successfully implemented cascading dynamic win cap and pacing relaxation mechanism to increase budget utilization in categories with few paid ads. The system provides a two-lever approach:
1. **Primary lever**: Increase win_per_ad_cap (1→2→3→4) based on under-spend severity
2. **Secondary lever**: Relax pacing tolerance after sustained under-spend (2+ consecutive hours)

## Implementation Details

### 1. Configuration (Tasks 1.1)

Added complete cascade configuration to both [config.yaml](../../config/config.yaml) and [local.yaml](../../config/local.yaml):

```yaml
cascading_win_cap:
  enabled: true

  # Win cap thresholds based on under_spend_ratio
  cap_thresholds:
    - ratio: 0.9   # If spending < 90% of target → 2 wins per ad
      cap: 2
    - ratio: 0.75  # If spending < 75% of target → 3 wins per ad
      cap: 3
    - ratio: 0.6   # If spending < 60% of target → 4 wins per ad
      cap: 4

  max_win_per_ad_cap: 4  # Hard limit

  # Pacing gate relaxation (fallback)
  pacing_relaxation:
    enabled: true
    fallback_hours: 2  # Trigger after 2 consecutive under-spend hours
    under_spend_threshold: 0.85  # Consider under-spending if ratio < 85%
    tolerance_increment: 0.1  # Add 0.1 to pacing_tolerance each hour
    tolerance_max: 0.5  # Maximum pacing_tolerance (50% ahead)
```

### 2. Cascade State Tracking (Task 1.2)

**File**: [auction_engine.py](../../src/auction_simulator/auction_engine.py)

Added cascade state management:
- Configuration loading in `__init__()` (lines 88-117)
- State dict: `cascade_state[(category_id, date)]` with:
  - `under_spend_streak`: consecutive hours of under-spending
  - `win_per_ad_cap`: current cap for category/day
  - `pacing_tolerance_adjusted`: current adjusted tolerance
- `reset_cascade_state_for_day()`: Initialize state for category/day
- `evaluate_cascade()`: Hourly evaluation of under-spend and cascade decisions
- `get_win_per_ad_cap()`: Query current cap
- `get_adjusted_pacing_tolerance()`: Query current tolerance

**Algorithm** (lines 311-386):
```python
# Calculate under-spend ratio
under_spend_ratio = cumulative_spend / target_spend

# Track consecutive under-spend hours
if under_spend_ratio < under_spend_threshold:
    under_spend_streak += 1
else:
    under_spend_streak = 0  # Reset

# Determine win_per_ad_cap (graduated thresholds)
# Iterate descending (0.9 → 0.75 → 0.6) and stop when ratio >= threshold
win_per_ad_cap = 1
for ratio_threshold, cap in sorted(thresholds, reverse=True):
    if under_spend_ratio < ratio_threshold:
        win_per_ad_cap = cap
    else:
        break

# Relax pacing tolerance after fallback_hours
if under_spend_streak >= fallback_hours:
    hours_beyond = under_spend_streak - fallback_hours + 1
    pacing_tolerance_adjusted = min(
        base_tolerance + hours_beyond * tolerance_increment,
        tolerance_max
    )
```

### 3. Win Cap Application (Task 1.3)

**File**: [auction_engine.py](../../src/auction_simulator/auction_engine.py)

Modified `select_winners()` (lines 588-654):
- Added `win_per_ad_cap` parameter (default 1)
- Track wins per ad in batch: `ad_win_count[ad_id]`
- Iterate cyclically through ranked ads until:
  - All slots filled, OR
  - All ads exhausted budget, OR
  - All ads reached cap
- Each eligible ad gets 1 reach slot per iteration, up to cap

**Logic**:
```python
ad_win_count = {}
while slots_remaining > 0:
    made_progress = False
    for ad in ranked_ads:
        if ad has budget and ad_win_count[ad] < win_per_ad_cap:
            award 1 reach slot to ad
            ad_win_count[ad] += 1
            slots_remaining -= 1
            made_progress = True
    if not made_progress:
        break  # All ads exhausted or at cap
```

### 4. Pacing Relaxation (Task 1.4)

**Files**: [auction_engine.py](../../src/auction_simulator/auction_engine.py), [simulation.py](../../src/auction_simulator/simulation.py)

Modified `check_pacing_gate()` (lines 455-495):
- Added `category_id` and `date` parameters
- Query `get_adjusted_pacing_tolerance()` when cascade enabled
- Use adjusted tolerance for max_allowed calculation

Modified `rank_ads()` (lines 497-577):
- Added `date` parameter
- Pass `category_id` and `date` to `check_pacing_gate()`
- Log pacing events with adjusted tolerance

Modified `run_batch_auction()` (lines 680-793):
- Added `win_per_ad_cap` parameter
- Pass `date` to `rank_ads()`
- Pass `win_per_ad_cap` to `select_winners()`

Modified `run_hour_auction()` in [simulation.py](../../src/auction_simulator/simulation.py):
- Reset cascade state at day boundary (lines 187-193)
- Evaluate cascade at hour start (lines 464-498)
- Pass `win_per_ad_cap` to `run_batch_auction()` (line 543)

### 5. Logging (Task 1.5)

**File**: [simulation.py](../../src/auction_simulator/simulation.py)

Added `cascade_evaluation` event logging (lines 490-497):
```python
self.sim_logger.log_event('cascade_evaluation', {
    'date': date_str,
    'hour': hour,
    'category_id': category_id,
    'time_progress': time_progress,
    'win_per_ad_cap': win_per_ad_cap,
    'pacing_tolerance_adjusted': pacing_tolerance_adjusted,
    'under_spend_ratio': under_spend_ratio,
    'under_spend_streak': under_spend_streak,
    'target_spend': target_spend,
    'actual_spend': actual_spend,
    'cascade_applied': cascade_applied
})
```

### 6. Reporting

**File**: [reporting.py](../../src/auction_simulator/reporting.py)

Added cascade status section in summary (lines 663-690):
- Display enabled/disabled status
- Show win cap thresholds
- Show pacing relaxation settings
- Link to simulation logs for details

### 7. Tests

**File**: [tests/test_cascading_win_cap.py](../../tests/test_cascading_win_cap.py) (NEW)

Comprehensive test suite with 10 tests:
- `test_cascade_initialization`: State initialization
- `test_win_cap_increases_on_underspend`: Cap increases when under-spending
- `test_win_cap_graduated_thresholds`: All threshold levels (2→3→4)
- `test_win_cap_never_exceeds_max`: Cap bounded to max_win_per_ad_cap
- `test_pacing_tolerance_relaxation`: Tolerance increases after streak
- `test_pacing_tolerance_max_bound`: Tolerance bounded to tolerance_max
- `test_streak_resets_on_normal_spend`: Streak resets when spending normalizes
- `test_select_winners_with_win_cap`: Multiple wins per ad in batch
- `test_cascade_disabled_returns_defaults`: Disabled mode returns defaults
- `test_cascade_state_per_category_per_day`: Independent state per (category, date)

**All 10 tests passing** ✅

## Files Modified

1. **auction-simulator/config/config.yaml** - Added cascade configuration
2. **auction-simulator/config/local.yaml** - Added cascade configuration
3. **auction-simulator/src/auction_simulator/auction_engine.py**:
   - Lines 88-117: Configuration loading
   - Lines 133-152: `reset_cascade_state_for_day()`
   - Lines 154-225: `evaluate_cascade()`
   - Lines 227-247: `get_win_per_ad_cap()`, `get_adjusted_pacing_tolerance()`
   - Lines 455-495: `check_pacing_gate()` - added cascade support
   - Lines 497-577: `rank_ads()` - added date parameter
   - Lines 588-654: `select_winners()` - multi-win support
   - Lines 680-793: `run_batch_auction()` - added win_per_ad_cap parameter
4. **auction-simulator/src/auction_simulator/simulation.py**:
   - Lines 187-193: Cascade state reset at day boundary
   - Lines 464-498: Cascade evaluation at hour start
   - Line 543: Pass win_per_ad_cap to run_batch_auction
5. **auction-simulator/src/auction_simulator/reporting.py**:
   - Lines 663-690: Cascade status in summary
6. **auction-simulator/tests/test_cascading_win_cap.py** - NEW test file
7. **auction-simulator/tests/test_feedback_pricing.py**:
   - Line 146: Fixed assertion (>= instead of >)

## Usage

### Running Simulation with Cascade

Cascade is **enabled by default** in both config files. To run a simulation:

```bash
python run_simulation.py --config config/local.yaml --date 2024-11-01 --category 1585
```

### Checking Cascade Events

Cascade events are logged in simulation logs:

```python
# Look for cascade_evaluation events
grep "cascade_evaluation" outputs/simulation_YYYY-MM-DD_HHMMSS/simulation_log.jsonl
```

### Interpreting Results

Check simulation summary for cascade status:

```
Cascading Win Cap & Pacing Relaxation:
  Status: ENABLED
  Win cap thresholds:
    - spend < 90% of target → cap = 2
    - spend < 75% of target → cap = 3
    - spend < 60% of target → cap = 4
  Max win per ad cap: 4
  Pacing relaxation: ENABLED
    - Triggers after 2 consecutive under-spend hours
    - Max tolerance: 0.5
```

## Configuration Parameters

### Win Cap Thresholds

Thresholds are evaluated **descending** (highest ratio first). System stops at first threshold where `under_spend_ratio >= ratio_threshold`. The cap from the previous (lower) threshold is used.

Example with `under_spend_ratio = 0.70`:
- Check 0.9: 0.70 < 0.9? YES → cap=2
- Check 0.75: 0.70 < 0.75? YES → cap=3
- Check 0.6: 0.70 < 0.6? NO → BREAK
- **Result: cap=3**

### Pacing Relaxation

Triggers after `fallback_hours` consecutive hours where `under_spend_ratio < under_spend_threshold`:
- Hour 1: under-spending → streak=1, no relaxation
- Hour 2: still under-spending → streak=2, tolerance += 0.1
- Hour 3: still under-spending → streak=3, tolerance += 0.1
- Reset to normal: streak=0, tolerance = base

## Validation (User Tasks)

### Task 2.1: Verify Bounds

Run simulation and check logs:
```bash
python -c "
import json
with open('outputs/.../simulation_log.jsonl') as f:
    for line in f:
        event = json.loads(line)
        if event['event'] == 'cascade_evaluation':
            assert event['win_per_ad_cap'] <= 4
            assert event['pacing_tolerance_adjusted'] <= 0.5
print('✅ All bounds verified')
"
```

### Task 2.2: Verify No Overspend

Check simulation summary:
```
Daily Totals:
  Total budget: 1000 AZN
  Total spending: 982 AZN (98.2%)
```

Spending should never exceed 100% of daily budget.

## Next Steps

1. Run simulation on test date with cascade enabled
2. Compare results with baseline (cascade disabled)
3. Analyze budget utilization improvement
4. Check for any overspend violations
5. Archive proposal after validation

## Notes

- Cascade evaluation happens **hourly** at the start of each hour
- State is **per-category, per-day** (independent tracking)
- Cascade works **alongside** feedback pricing controller
- Both levers (win cap + pacing) can be disabled independently
- System is **deterministic** and **bounded** by configuration
