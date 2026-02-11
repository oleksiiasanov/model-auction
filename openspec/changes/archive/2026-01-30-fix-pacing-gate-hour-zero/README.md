# Fix Pacing Gate Hour Zero Blocking

**Status**: ✅ Validated (Awaiting Approval)
**Change ID**: `fix-pacing-gate-hour-zero`
**Created**: 2026-01-30

## Quick Summary

Add `min_time_progress_threshold` parameter to prevent pacing gate from blocking all paid ads at hour 0.

**Problem**: At hour 0, `time_progress=0` → `max_allowed=0` → any ad that wins auction gets blocked for remaining hour.

**Solution**: Use `safe_time_progress = max(time_progress, 0.042)` to ensure minimum 5% budget availability in first hour.

**Impact**:
- ✅ Fixes paid impression ratio: 98.5% → ~3.6% (27x correction)
- ✅ Fixes organic impression ratio: 1.5% → ~96.4% (64x correction)
- ✅ Enables natural N decrease throughout day (was stuck at 81)

## Files

- **[proposal.md](./proposal.md)**: Full problem statement, solution rationale, impact analysis
- **[tasks.md](./tasks.md)**: Implementation tasks with validation steps
- **[specs/auction-engine/spec.md](./specs/auction-engine/spec.md)**: Spec delta with new pacing gate scenarios

## Validation Evidence

Test comparison shows fix effectiveness:

| Batch | Before (eligible) | After (eligible) | Improvement |
|-------|------------------|------------------|-------------|
| #1    | 3/3 (100%)       | 3/3 (100%)       | = |
| #2    | 0/3 (0%)         | 3/3 (100%)       | ✅ +100% |
| #3    | 0/3 (0%)         | 3/3 (100%)       | ✅ +100% |
| #4    | 0/3 (0%)         | 3/3 (100%)       | ✅ +100% |
| #5    | 0/3 (0%)         | 3/3 (100%)       | ✅ +100% |

See `auction-simulator/test_pacing_comparison.py` for full test output.

## Implementation Complexity

- **Risk**: 🟢 Low (single formula change, symmetric to existing pattern)
- **Effort**: 2-3 hours
- **Breaking**: No (only changes broken hour 0 behavior)

## Next Steps

1. **Review**: Stakeholder approval of proposal
2. **Apply**: Use `openspec apply fix-pacing-gate-hour-zero` to implement
3. **Validate**: Run 1-day simulation, verify metrics
4. **Archive**: Use `openspec archive fix-pacing-gate-hour-zero` when complete

---

**Related Changes**:
- [fix-fractional-kopecks-bid-step](../fix-fractional-kopecks-bid-step/) (recently completed, documented this issue)
