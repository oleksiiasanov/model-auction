# Spec Delta: Fix Pacing Gate Hour Zero Blocking

**Capability**: auction-engine
**Change**: fix-pacing-gate-hour-zero

---

## MODIFIED Requirements

### Requirement: Pacing Gate for Budget Distribution

The system SHALL enforce a pacing gate to prevent ads from spending their entire budget early in the day, ensuring even distribution, **with a minimum time_progress threshold to prevent blocking at hour 0**.

#### Scenario: Minimum time_progress threshold (prevents hour 0 blocking)

- **WHEN** calculating pacing eligibility with time_progress value
- **THEN** system uses `safe_time_progress = max(time_progress, min_time_progress_threshold)` where `min_time_progress_threshold = 0.042`
- **PURPOSE**: Prevents `max_allowed=0` at hour 0 which blocks all ads after first auction
- **CURRENT STATE**: Actively used at hour 0:
  - At hour 0, `time_progress = 0/24 = 0.0`
  - `0.0 < 0.042`, so threshold triggers → `safe_time_progress = 0.042`
  - `max_allowed = daily_budget × 0.042 × 1.2 ≈ 5%` of daily budget
- **RATIONALE**:
  - Symmetric to `min_time_left_threshold` (defensive programming)
  - Allows ads to spend proportional amount in first hour
  - Value 0.042 = 1 hour (1/24), consistent with hourly update granularity
- **EXAMPLE**:
  - `daily_budget = 100` kopecks
  - At hour 0: `max_allowed = 100 × 0.042 × 1.2 = 5.04` kopecks
  - Ads can win ~33 auctions (`5.04 / 0.15 = 33` wins) before pacing pause
- **CONFIGURATION**: Parameter `simulation.min_time_progress_threshold` in config YAML

#### Scenario: Hour 0 no longer blocks all ads after first win

- **WHEN** `hour=0`, `time_progress=0.0`, ad wins first auction and spends `0.15` kopecks
- **THEN**
  - `safe_time_progress = max(0.0, 0.042) = 0.042`
  - `expected_spend = 100 × 0.042 = 4.2` kopecks
  - `max_allowed = 4.2 × 1.2 = 5.04` kopecks
  - `actual_spend = 0.15 < 5.04` → ad remains eligible ✅
- **BEFORE FIX**:
  - `max_allowed = 100 × 0.0 × 1.2 = 0` kopecks
  - `actual_spend = 0.15 > 0` → ad blocked after single win ❌
- **IMPACT**:
  - Fixes paid impression ratio: `98.5% → ~3.6%` (27x correction)
  - Fixes organic impression ratio: `1.5% → ~96.4%` (64x correction)
  - Enables natural N decrease throughout day

#### Scenario: Threshold transparent at other hours

- **WHEN** `hour=1`, `time_progress = 1/24 = 0.042`
- **THEN**
  - `safe_time_progress = max(0.042, 0.042) = 0.042` (threshold equals real value)
  - Behavior identical to pre-fix implementation
- **WHEN** `hour=6`, `time_progress = 6/24 = 0.25`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - Behavior identical to pre-fix implementation
- **RATIONALE**: Fix only affects hour 0, preserves existing behavior for hours 1-23

#### Scenario: Ad within pacing limits (existing scenario, unchanged)

- **WHEN** `time_progress=0.25` (6 hours elapsed), `daily_budget=1000`, `actual_spend=200`, `pacing_tolerance=0.2`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - `expected_spend = 1000 × 0.25 = 250`
  - `max_allowed = 250 × 1.2 = 300`
  - `actual_spend = 200 < 300` → ad remains eligible ✅
- **NOTE**: Behavior unchanged from pre-fix implementation

#### Scenario: Ad exceeding pacing limits (existing scenario, unchanged)

- **WHEN** `time_progress=0.25`, `daily_budget=1000`, `actual_spend=350`, `pacing_tolerance=0.2`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - `expected_spend = 1000 × 0.25 = 250`
  - `max_allowed = 250 × 1.2 = 300`
  - `actual_spend = 350 > 300` → ad is paused (pressure set to 0) ❌
- **NOTE**: Behavior unchanged from pre-fix implementation

#### Scenario: Configurable threshold for different strategies

- **WHEN** operator wants more/less permissive hour 0 behavior
- **THEN** edit `config/local.yaml`: `simulation.min_time_progress_threshold: [value]`
- **GUIDANCE**:
  - Conservative: `0.042` (1 hour, ~5% budget with tolerance=0.2)
  - Moderate: `0.05` (1.2 hours, ~6% budget)
  - Aggressive: `0.083` (2 hours, ~10% budget)
- **RECOMMENDATION**: Use `0.042` for consistency with hourly update granularity

---

## Implementation Notes

### Code Location

**File**: `auction-simulator/src/auction_simulator/auction_engine.py`

**Method**: `check_pacing_gate(self, ad: Ad, time_progress: float) -> bool`

**Change**:
```python
# BEFORE:
expected_spend = ad.daily_budget * time_progress
max_allowed = expected_spend * (1 + self.pacing_tolerance)

# AFTER:
safe_time_progress = max(time_progress, self.min_time_progress_threshold)
expected_spend = ad.daily_budget * safe_time_progress
max_allowed = expected_spend * (1 + self.pacing_tolerance)
```

### Configuration

**File**: `auction-simulator/config/local.yaml`

**Parameter**:
```yaml
simulation:
  min_time_progress_threshold: 0.042  # 1 hour = 1/24
```

**Comment**:
```yaml
# Minimum time_progress threshold for pacing gate (prevents zero max_allowed at hour 0)
# NOTE: Actively used at hour 0 (time_progress=0.0 < 0.042)
# Serves as safety net similar to min_time_left_threshold
# Value 0.042 = 1 hour (1/24), allows ~5% budget in first hour with tolerance=0.2
```

### Testing

**New Test**: `test_pacing_gate_hour_zero_not_blocked`

**Assertion**: Ad with `actual_spend=0.15` remains eligible at `time_progress=0.0` (hour 0)

**Validation**: 1-day simulation shows:
- Paid impressions ~3.6% (before: 98.5%)
- Organic impressions ~96.4% (before: 1.5%)
- N decreases throughout day (before: stuck at 81)

---

## Cross-References

- **Related requirement**: "Minimum time_left threshold (safety net)" in same spec
- **Symmetric pattern**: Both `min_time_left_threshold` and `min_time_progress_threshold` follow same defensive programming approach
- **FAQ documentation**: [docs/faq/03-pacing-gate.md](../../../../auction-simulator/docs/faq/03-pacing-gate.md)
- **Problem analysis**: [fix-fractional-kopecks-bid-step/SUMMARY.md](../../fix-fractional-kopecks-bid-step/SUMMARY.md#L41-L44)

---

## Revision History

- **2026-01-30**: Initial spec delta (fix-pacing-gate-hour-zero)
