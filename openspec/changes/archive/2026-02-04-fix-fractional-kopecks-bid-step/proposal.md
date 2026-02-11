# Proposal: Fix Fractional Kopecks and Reduce Bid Step

**Change ID**: `fix-fractional-kopecks-bid-step`
**Status**: DRAFT
**Created**: 2026-01-30
**Author**: Claude Code

## Problem Statement

The auction simulator has two critical issues affecting bid accuracy:

### Issue 1: Integer Rounding Loses Small Bids

**Current behavior**: Budget values (`daily_budget`, `remaining_budget`) are stored as `int` (integer kopecks). When an ad wins with a small bid (e.g., `effective_bid = 0.1469` kopecks), the cost is rounded to integer before deduction:

```python
cost_integer = round(0.1469)  # = 0 kopecks
ad.remaining_budget -= 0  # Budget doesn't decrease!
```

**Impact**:
- With `bid_step=0.001`, all bids are < 0.5 kopecks → round to 0
- Budgets never decrease, ads can participate indefinitely
- Actual spend tracking (`actual_spend` as float) works, but budget gates fail
- N (ads with budget) stays constant at 81 throughout the day

**Evidence from logs**:
```
Auction #1: Budget ДО=165, Bid=0.1469, Budget ПІСЛЯ=165 (unchanged!)
Auction #2: Budget ДО=70, Bid=0.1469, Budget ПІСЛЯ=70 (unchanged!)
```

### Issue 2: Original bid_step Too Large

**Original value**: `bid_step = 0.1` kopecks
**With N=81 ads**: Max bid = 0.0702 + 80×0.1 = **8.07 kopecks**
**Problem**: Bids 100x too high compared to actual market prices (min_bid ≈ 0.07 kopecks)

**Experimentation results**:

| bid_step | Max bid (N=81) | Spending accuracy | N stability | Issue |
|----------|----------------|-------------------|-------------|-------|
| 0.1 | 8.07 koп. | 120% (too high) | Unstable (5-81) | Overspending |
| 0.01 | 0.87 koп. | 110% | Stable (43-81) | Still high |
| 0.001 | 0.15 koп. | 91.4% ✅ | Stable (81) ✅ | **Rounding to 0!** |

With `bid_step=0.001`, spending accuracy improved to 91.4% and N remained stable, BUT integer rounding broke budget tracking entirely.

## Proposed Solution

**Fix both issues simultaneously:**

1. **Support Fractional Kopecks**: Change `daily_budget` and `remaining_budget` from `int` to `float`
2. **Remove Rounding**: Deduct exact `effective_bid` (float) without rounding
3. **Keep bid_step=0.001**: Maintain accurate bid granularity

### Changes Required

#### 1. Data Types (`auction_engine.py`)

```python
@dataclass
class Ad:
    daily_budget: float  # was: int
    remaining_budget: float  # was: int
    actual_spend: float  # unchanged
```

#### 2. Budget Initialization (`simulation.py`)

```python
# Was: budget = int(row['daily_budget'])
budget = float(row['daily_budget'])  # Keep fractional precision
```

#### 3. Cost Deduction (`auction_engine.py`)

```python
# Was:
cost_integer = round(effective_bid * impressions_won)  # Loses precision!
ad.remaining_budget -= cost_integer

# Now:
cost = effective_bid * impressions_won  # Keep exact value
ad.remaining_budget = max(0.0, ad.remaining_budget - cost)
```

#### 4. Configuration (`config/local.yaml`)

```yaml
simulation:
  bid_step: 0.001  # Reduced from 0.1 (100x smaller)
```

#### 5. JSON Serialization (`logger.py`)

Added numpy type conversion for JSONL logging:
```python
def convert_to_python_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer): return int(obj)
    elif isinstance(obj, np.floating): return float(obj)
    # ... handle arrays, dicts, lists
```

## Expected Outcomes

### Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| **Spending accuracy** | 120% (bid_step=0.1) | 91.4% | 95-105% |
| **N stability** | 5-81 (volatile) | 81 (stable) ✅ | Stable |
| **Budget tracking** | ❌ Rounds to 0 | ✅ Exact deduction | Works |
| **Max bid (N=81)** | 8.07 koп. | 0.15 koп. | ~10x min_bid |

### Side Effects

**Known issue**: Pacing gate blocks ads after first batch when `time_progress=0`:
- `max_allowed = daily_budget × 0 × 1.2 = 0`
- Any `actual_spend > 0` → blocked
- **Separate issue**: Requires time-based or threshold solution (not addressed in this change)

**Current state**: 98.5% of impressions are paid (vs 3.6% actual) due to pacing gate blocking organic fallback. This is a **different problem** requiring separate fix.

## Testing Strategy

1. **Unit Tests**: Verify float budget arithmetic
2. **Integration Test**: Run 1-day simulation, verify:
   - Budgets decrease correctly (no rounding to 0)
   - spending_simulated ≈ spending_actual (within 10%)
   - N stays stable throughout day
3. **Regression**: Compare with actual spending for 5-day period

## Rollout Plan

1. Apply changes to `auction-engine` and `simulation` code
2. Run simulation for historical period (2026-01-22 to 2026-01-26)
3. Validate spending accuracy < 10% deviation
4. If validation passes, keep changes; otherwise revert

## Open Questions

1. **Should we address pacing gate in this change?**
   → NO, separate problem. This change focuses on bid/budget accuracy.

2. **Do we need min_bid validation?**
   → Not critical. Min_bid from PostgreSQL is authoritative.

3. **Should bid_step be configurable per category?**
   → Out of scope. Global config sufficient for now.

## Dependencies

- ✅ PostgreSQL min_bid integration (already done)
- ✅ N calculation fix (only count ads with budget > 0) (already done)
- ⏸️ Pacing gate fix (separate change, not blocking)

## Alternatives Considered

### Alt 1: Keep integer kopecks, increase bid_step to 1.0
- ❌ Would make max_bid = 81 kopecks (1000x too high)
- ❌ Defeats purpose of matching real market prices

### Alt 2: Use fixed-point arithmetic (store as 0.0001 kopeck units)
- ✅ Avoids float precision issues
- ❌ More complex, unnecessary (float64 has 15 decimal precision)

### Alt 3: Add min_threshold to pacing gate
- ✅ Solves pacing blocking issue
- ❌ Doesn't fix budget rounding problem
- 📝 Should be separate change

## References

- Issue discovered: 2026-01-30 session
- Related spec: `openspec/specs/auction-engine/spec.md`
- Config file: `auction-simulator/config/local.yaml`
