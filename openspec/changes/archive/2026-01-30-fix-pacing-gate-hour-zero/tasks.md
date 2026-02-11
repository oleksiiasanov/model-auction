# Implementation Tasks: Fix Pacing Gate Hour Zero Blocking

**Change ID**: `fix-pacing-gate-hour-zero`

## Overview

Add `min_time_progress_threshold` parameter to prevent pacing gate from blocking all ads at hour 0.

**Estimated effort**: 2-3 hours
**Risk level**: Low (single formula change, configurable parameter)

---

## Phase 1: Configuration and Core Logic

### Task 1.1: Add min_time_progress_threshold to config files

**Files**:
- `auction-simulator/config/config.yaml` (template)
- `auction-simulator/config/local.yaml` (production)

**Changes**:
```yaml
simulation:
  # ... existing parameters ...

  # Minimum time_progress threshold for pacing gate (prevents zero max_allowed at hour 0)
  # NOTE: Actively used at hour 0 (time_progress=0.0 < 0.042)
  # Serves as safety net similar to min_time_left_threshold
  # Value 0.042 = 1 hour (1/24), allows ~5% budget in first hour
  min_time_progress_threshold: 0.042
```

**Validation**: Config files parse without errors

---

### Task 1.2: Update AuctionEngine to use threshold

**File**: `auction-simulator/src/auction_simulator/auction_engine.py`

**Changes**:

1. Add parameter to `__init__`:
```python
def __init__(self, config):
    self.min_time_left_threshold = config.simulation.min_time_left_threshold
    self.min_time_progress_threshold = config.simulation.min_time_progress_threshold  # NEW
    self.pacing_tolerance = config.simulation.pacing_tolerance
    self.bid_step = config.simulation.bid_step
    self.batch_size = config.simulation.batch_size
```

2. Update `check_pacing_gate` method:
```python
def check_pacing_gate(self, ad: Ad, time_progress: float) -> bool:
    """
    Check if ad is within pacing limits.

    Args:
        ad: Ad object with budget and spend state
        time_progress: Fraction of day elapsed (0.0 to 1.0)

    Returns:
        True if ad is eligible (within pacing limits), False if paused
    """
    if ad.daily_budget <= 0:
        return True  # No budget = always eligible (simulated organic)

    # Apply minimum threshold to prevent zero max_allowed at hour 0
    # NOTE: At hour 0, time_progress=0.0 < 0.042, so threshold is applied
    # This allows ads to spend ~5% of budget in first hour
    safe_time_progress = max(time_progress, self.min_time_progress_threshold)

    expected_spend = ad.daily_budget * safe_time_progress  # CHANGED: use safe_time_progress
    max_allowed = expected_spend * (1 + self.pacing_tolerance)

    is_eligible = ad.actual_spend <= max_allowed

    if not is_eligible:
        logger.debug(f"Ad {ad.ad_id} paused by pacing gate: "
                     f"spend={ad.actual_spend:.2f} > max_allowed={max_allowed:.2f}")

    return is_eligible
```

**Validation**: Code compiles, no syntax errors

---

### Task 1.3: Update tests to include new parameter

**File**: `auction-simulator/tests/test_auction_engine.py`

**Changes**:

1. Update config fixture:
```python
@pytest.fixture
def config():
    return Config({
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,  # NEW
            'pacing_tolerance': 0.2,
            'bid_step': 0.1,
            'batch_size': 40
        }
    })
```

2. Add test for hour 0 behavior:
```python
def test_pacing_gate_hour_zero_not_blocked(engine):
    """Test that ads are not blocked at hour 0 after first win."""
    ad = Ad(
        ad_id=1,
        daily_budget=100.0,
        remaining_budget=100.0,
        actual_spend=0.0,
        simulated_impressions=0
    )

    time_progress = 0.0  # Hour 0

    # First batch: ad has not spent yet
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Simulate winning auction (cost ~0.15)
    ad.actual_spend = 0.15

    # Second batch: ad should still be eligible
    # max_allowed = 100 × max(0.0, 0.042) × 1.2 = 5.04 kopecks
    # 0.15 < 5.04 → eligible
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Continue spending up to threshold
    ad.actual_spend = 5.0
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Exceed threshold
    ad.actual_spend = 5.1
    assert engine.check_pacing_gate(ad, time_progress) is False
```

**Validation**: `pytest tests/test_auction_engine.py -v` passes

---

**File**: `auction-simulator/tests/test_config.py`

**Changes**:
```python
def test_config_attribute_access():
    """Test nested attribute access in Config."""
    config_dict = {
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,  # NEW
            'batch_size': 40
        },
        # ...
    }

    config = Config(config_dict)

    assert config.simulation.min_time_left_threshold == 0.001
    assert config.simulation.min_time_progress_threshold == 0.042  # NEW
    assert config.simulation.batch_size == 40
```

**Validation**: `pytest tests/test_config.py -v` passes

---

## Phase 2: Validation

### Task 2.1: Run 1-day simulation and verify hour 0 behavior

**Command**:
```bash
./venv/bin/python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1361 \
  --time-from 2026-01-22 \
  --time-to 2026-01-22
```

**Check**:
- Logs at hour 0 show `max_allowed ≈ 5.04 kopecks` (not 0)
- Ads eligible after first win in hour 0 batches
- N (ads with budget) starts at 81 and decreases throughout day

**Expected evidence**:
```
Hour 0, Batch 1: max_allowed=5.04, Ad 123: spend=0.00 <= 5.04 ✅ ELIGIBLE
Hour 0, Batch 2: max_allowed=5.04, Ad 123: spend=0.15 <= 5.04 ✅ ELIGIBLE
...
Hour 0, Batch 33: max_allowed=5.04, Ad 123: spend=4.95 <= 5.04 ✅ ELIGIBLE
```

---

### Task 2.2: Verify paid/organic impression ratio

**Check**: `summary_statistics_*.txt` report

**Metrics**:
- **Paid impressions**: Should be ~3.6% (±20% acceptable)
- **Organic impressions**: Should be ~96.4% (±20% acceptable)

**Before fix**: 98.5% paid / 1.5% organic (inverted!)
**After fix**: ~3.6% paid / ~96.4% organic ✅

---

### Task 2.3: Verify N stability and budget exhaustion

**Check**: Logs throughout day

**Expected behavior**:
- N starts at 81 at hour 0
- N decreases gradually as ads exhaust budgets
- By end of day, N significantly lower (e.g., N < 20)

**Before fix**: N=81 constant throughout day (ads blocked, not spending)
**After fix**: N decreases naturally ✅

---

## Phase 3: Documentation

### Task 3.1: Add spec requirement for min_time_progress_threshold

**File**: `openspec/changes/fix-pacing-gate-hour-zero/specs/auction-engine/spec.md`

**Content**:
```markdown
## MODIFIED Requirements

### Requirement: Pacing Gate for Budget Distribution

#### Scenario: Minimum time_progress threshold (prevents hour 0 blocking)
- **WHEN** calculating pacing eligibility with time_progress value
- **THEN** system uses safe_time_progress = max(time_progress, min_time_progress_threshold) where min_time_progress_threshold = 0.042
- **PURPOSE**: Prevents max_allowed=0 at hour 0 which blocks all ads after first auction
- **CURRENT STATE**: Actively used at hour 0:
  - At hour 0, time_progress = 0/24 = 0.0
  - 0.0 < 0.042, so threshold triggers → safe_time_progress = 0.042
  - max_allowed = daily_budget × 0.042 × 1.2 ≈ 5% of budget
- **RATIONALE**: Symmetric to min_time_left_threshold, defensive programming for edge cases
- **EXAMPLE**:
  - daily_budget = 100 kopecks
  - At hour 0: max_allowed = 100 × 0.042 × 1.2 = 5.04 kopecks
  - Ads can win ~33 auctions (5.04 / 0.15) before pacing pause

#### Scenario: Hour 0 no longer blocks all ads
- **WHEN** hour=0, time_progress=0.0, ad wins first auction and spends 0.15 kopecks
- **THEN**
  - safe_time_progress = max(0.0, 0.042) = 0.042
  - max_allowed = 100 × 0.042 × 1.2 = 5.04 kopecks
  - actual_spend = 0.15 < 5.04 → ad remains eligible ✅
- **BEFORE**: max_allowed = 0, ad blocked after single win ❌
- **IMPACT**: Fixes 98.5% → 3.6% paid impression ratio (27x correction)
```

---

### Task 3.2: Update FAQ with solution status

**File**: `auction-simulator/docs/faq/03-pacing-gate.md`

**Changes**:

Update section "## Проблема hour=0" to reflect:
- ✅ **Виправлено** в change `fix-pacing-gate-hour-zero`
- Link to proposal and spec
- Show "before/after" comparison with new threshold

Add new Q&A:
```markdown
## min_time_progress_threshold

**🏷️ Теги:** `pacing`, `threshold`, `hour-zero`, `safety`

**❓ Питання:**
Що таке min_time_progress_threshold і чому він потрібен?

**💡 Коротка відповідь:**
**min_time_progress_threshold** = мінімальне значення для time_progress (0.042 = 1 година) — запобігає блокуванню ads о 00:00.

**📚 Детальна відповідь:**

### Проблема яку вирішує:

О 00:00, time_progress=0.0 → max_allowed=0 → будь-які витрати блокуються!

### Формула:

```python
safe_time_progress = max(time_progress, min_time_progress_threshold)
expected_spend = daily_budget × safe_time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

### Приклад (daily_budget=100 коп., threshold=0.042):

| Година | time_progress | safe_progress | max_allowed | Коментар |
|--------|---------------|---------------|-------------|----------|
| 0 | 0.000 | **0.042** | 5.04 коп. | Threshold застосовується! |
| 1 | 0.042 | 0.042 | 5.04 коп. | Threshold = реальне значення |
| 6 | 0.250 | 0.250 | 30.0 коп. | Threshold НЕ застосовується |

**💻 Код:**
```python
# Локація: auction_engine.py:85-86
safe_time_progress = max(time_progress, self.min_time_progress_threshold)
expected_spend = ad.daily_budget * safe_time_progress
```

**🔗 Пов'язані питання:**
- [Проблема hour=0](#проблема-hour0)
- [Що таке min_time_left_threshold?](#min_time_left_threshold)

**📅 Додано:** 2026-01-30
```

---

### Task 3.3: Update main spec with threshold

**File**: `openspec/specs/auction-engine/spec.md`

**Changes**: Merge content from Task 3.1 spec delta into main spec under "Requirement: Pacing Gate for Budget Distribution"

---

## Phase 4: Cleanup

### Task 4.1: Remove test comparison script (optional)

**File**: `auction-simulator/test_pacing_comparison.py`

**Action**: Move to `tests/manual/` or delete (was temporary validation script)

---

## Dependencies

```
Task 1.1 (config) ──→ Task 1.2 (engine code) ──→ Task 1.3 (tests)
                                                      ↓
                                                  Task 2.1 (validation)
                                                      ↓
                                    Task 2.2 ←──────┴──────→ Task 2.3
                                       ↓
                                    Task 3.1 → Task 3.2 → Task 3.3
```

## Completion Criteria

- ✅ All Phase 1 tasks completed (config + code + tests)
- ✅ Phase 2: Paid impressions ~3.6% (±20% acceptable)
- ✅ Phase 2: Organic impressions ~96.4% (±20% acceptable)
- ✅ Phase 2: N decreases throughout day (not stuck at 81)
- ✅ Phase 3: Documentation updated (spec + FAQ)
- ✅ All tests pass (`pytest -v`)

## Notes

- **Simple change**: Single formula modification, low risk
- **Symmetric design**: Mirrors existing `min_time_left_threshold` pattern
- **Configurable**: Value can be tuned without code changes
- **Backward compatible**: Only affects hour 0 behavior (currently broken)
