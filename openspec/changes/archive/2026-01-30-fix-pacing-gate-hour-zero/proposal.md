# Proposal: Fix Pacing Gate Hour Zero Blocking

**Change ID**: `fix-pacing-gate-hour-zero`
**Status**: Proposed
**Created**: 2026-01-30

## Why

The current pacing gate implementation causes a critical bug at hour 0 where `time_progress=0` leads to `max_allowed=0`, blocking all paid ads after their first auction win. This breaks the simulation's core behavior, causing 27x inflation in paid impressions (98.5% vs actual 3.6%) and preventing natural budget exhaustion (N stuck at 81 all day). Without this fix, hour 0 simulations are unusable.

## Problem Statement

The pacing gate mechanism blocks ALL paid ads after the first auction batch at hour 0 (00:00), causing:
- 98.5% paid impressions vs 3.6% actual (27x inflation)
- 1.5% organic impressions vs 96.4% actual (64x deflation)
- N (ads with budget) remaining at 81 throughout entire day instead of decreasing

### Root Cause

```python
# At hour=0:
time_progress = 0 / 24.0 = 0.0
expected_spend = daily_budget × 0.0 = 0 kopecks
max_allowed = 0 × (1 + pacing_tolerance) = 0 kopecks

# After first auction batch:
actual_spend = 0.15 kopecks (typical bid)
0.15 > 0 → ❌ BLOCKED for remaining 59 batches in hour 0
```

The pacing gate formula `expected_spend = daily_budget × time_progress` produces `max_allowed = 0` at hour 0, blocking any ad that wins even a single auction.

## What Changes

This change adds a single configuration parameter `min_time_progress_threshold` (default: 0.042) and modifies the pacing gate formula to use `safe_time_progress = max(time_progress, min_time_progress_threshold)` instead of raw `time_progress`. This prevents `max_allowed = 0` at hour 0 while preserving existing behavior for hours 1-23.

**Files affected:**
- `config/config.yaml` and `config/local.yaml`: Add `min_time_progress_threshold: 0.042`
- `auction_engine.py`: Update `__init__` and `check_pacing_gate()` to use threshold
- `test_auction_engine.py` and `test_config.py`: Add parameter to test configs
- `docs/faq/03-pacing-gate.md`: Update documentation with solution

See spec delta in `specs/auction-engine/spec.md` for detailed requirement changes.

## Proposed Solution

Introduce `min_time_progress_threshold` parameter (symmetric to existing `min_time_left_threshold`) to prevent zero-value edge case:

```python
# New formula:
safe_time_progress = max(time_progress, min_time_progress_threshold)
expected_spend = daily_budget × safe_time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

**Recommended value**: `min_time_progress_threshold = 0.042` (1 hour = 1/24)

### Why This Solution?

1. **Symmetric**: Mirrors existing `min_time_left_threshold` pattern (defensive programming)
2. **Simple**: Single-line change to formula
3. **Universal**: Works for all hours, not just hour=0 special case
4. **Configurable**: Operators can tune threshold based on needs
5. **Consistent**: Follows established codebase conventions

### Comparison with Alternatives

| Solution | Complexity | Universality | Consistency |
|----------|------------|--------------|-------------|
| **min_time_progress_threshold** | 🟢 Low | 🟢 High | 🟢 Symmetric with time_left |
| Fixed 5% budget minimum | 🟡 Medium | 🟡 Medium | 🟡 Different pattern |
| `if hour == 0: pass` | 🟢 Low | 🔴 Only hour=0 | 🔴 Special case hack |

## Expected Impact

### Before (Current Behavior)
```
Batch #1 at 00:00: max_allowed = 0.00 koп
  Ad wins, pays 0.15 koп → actual_spend = 0.15
Batch #2-60 at 00:00: max_allowed = 0.00 koп
  0.15 > 0 → ❌ BLOCKED (all ads blocked for remaining hour)
```

### After (With min_time_progress_threshold=0.042)
```
All batches at 00:00: max_allowed = 5.04 koп (100 × 0.042 × 1.2)
  Ads can win ~33 auctions before blocking (5.04 / 0.15 = 33 wins)
  Natural budget exhaustion resumes normal operation
```

### Metrics Improvement

| Metric | Current | Expected | Fix |
|--------|---------|----------|-----|
| **Paid impressions** | 98.5% | ~3.6% | ✅ 27x reduction |
| **Organic impressions** | 1.5% | ~96.4% | ✅ 64x increase |
| **N stability** | 81 constant | Decreases gradually | ✅ Natural decrease |
| **max_allowed at hour 0** | 0.00 koп | 5.04 koп | ✅ ∞ improvement |

## Validation Evidence

Simulation comparison (`test_pacing_comparison.py`) shows:
- **Current**: 3/3 ads eligible in batch #1, then 0/3 in batches #2-5
- **With fix**: 3/3 ads eligible in ALL batches #1-5
- **Wins before block**: 1 → 33 (33x improvement)

Full test output in change documentation.

## Scope

### In Scope
- Add `min_time_progress_threshold` config parameter
- Update pacing gate formula to use `safe_time_progress`
- Update spec to document new threshold requirement
- Add FAQ entry explaining threshold behavior

### Out of Scope
- Changes to hourly update mechanism (remains hourly)
- Alternative pacing strategies (minute-level, dynamic tolerance)
- Retroactive data correction for previous simulations

## Dependencies

- **Relates to**: `fix-fractional-kopecks-bid-step` (recently completed)
- **Blocks**: None (independent fix)
- **Blocked by**: None

## Risks and Mitigations

### Risk 1: Threshold too permissive (ads overspend early)
- **Mitigation**: Use conservative 0.042 value (matches minimum hourly time_left)
- **Fallback**: Configurable parameter allows tuning without code changes

### Risk 2: Breaking existing simulations
- **Mitigation**: Default value 0.042 ensures backward-compatible behavior at hour 1-23
- **Impact**: Only changes hour 0 behavior (currently broken)

### Risk 3: Confusion with min_time_left_threshold
- **Mitigation**: Clear documentation and symmetric naming
- **Note**: Both thresholds serve similar defensive programming purpose

## Questions for Stakeholders

1. **Threshold value**: Confirm 0.042 (1 hour) is appropriate, or prefer alternative (e.g., 0.05 = 5%)?
2. **Naming**: Confirm `min_time_progress_threshold` naming follows project conventions?
3. **Documentation**: Should we add comparison table in FAQ showing all three threshold proposals?

## Success Criteria

- ✅ Paid impression ratio returns to ~3.6% (within ±20%)
- ✅ Organic impression ratio returns to ~96.4% (within ±20%)
- ✅ N (ads with budget) decreases throughout day as budgets exhaust
- ✅ No ads blocked at hour 0 due to single auction win
- ✅ All existing tests pass with new threshold parameter
- ✅ Spec updated with new pacing gate requirement scenarios

## References

- **FAQ Documentation**: [docs/faq/03-pacing-gate.md#проблема-hour0](../../auction-simulator/docs/faq/03-pacing-gate.md#L258-L372)
- **Test Evidence**: [test_pacing_comparison.py](../../auction-simulator/test_pacing_comparison.py)
- **Related Change**: [fix-fractional-kopecks-bid-step/SUMMARY.md](../fix-fractional-kopecks-bid-step/SUMMARY.md#L41-L44)
- **Current Code**: [auction_engine.py:85-86](../../auction-simulator/src/auction_simulator/auction_engine.py#L85-L86)
