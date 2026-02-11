# Change: Update Paid Eligibility and Organic Fallback Allocation

## Why
Recent simulation runs (2026-02-05) show three persistent issues that block target behavior for a production replacement auction algorithm:

1. **Paid coverage gap**: 10 paid ads and 5 paid sellers receive zero simulated reach.
2. **Budget utilization gap**: reported utilization remains ~94% instead of target ~100%.
3. **Organic coverage collapse**: only 5 free ads receive simulated organic reach out of 8,266 free ads.

Root causes are structural, not parameter tuning:
- Paid eligibility depends on historical reach presence (ads from budgets without impressions are excluded from simulation state).
- Budget extraction can include ad IDs that are not strictly category-aligned in source data quality edge cases.
- Organic fallback uses per-batch floor/remainder allocation that resets fractional proportions each batch, starving long-tail ads.
- Reporting currently contains denominator/counting inconsistencies that can misstate coverage and conservation in summary outputs.
- Auction charging currently allows slight budget overshoot due to fractional bids, producing utilization >100%.

Tests with `bid_step` tuning (0.003 -> 0.005) do not materially fix these issues.

## What Changes
- Add strict category-safe filtering in budget extraction.
- Remove dependency on impression-presence subquery for paid budget eligibility (budget-driven participation in selected scope).
- Make paid auction eligibility budget-driven (not historical-reach-driven) by initializing simulation ad state from the union of impressions and budgets.
- Replace per-batch organic fallback allocation with cumulative carry-over allocation (fractional debt/credit preserved across batches).
- Add optional paid/free pool split for organic fallback with configurable shares.
- Reallocate pool-split residual when one organic pool is empty to preserve exact per-event conservation.
- Cap per-win charge by remaining budget to enforce `simulated_spend <= budget` invariants.
- Add reporting metrics to distinguish total paid budget from active paid budget and to expose active utilization separately.
- Fix summary/report counting to use period-level paid/free status and deduplicated ad entities, with exact conservation parity against simulation allocation totals.

## Impact
- **Affected specs**:
  - `data-extraction`
  - `auction-engine`
  - `comparison-reporting`
- **Affected code (expected)**:
  - `auction-simulator/src/auction_simulator/data_extraction.py`
  - `auction-simulator/src/auction_simulator/simulation.py`
  - `auction-simulator/src/auction_simulator/auction_engine.py`
  - `auction-simulator/src/auction_simulator/reporting.py`
  - `auction-simulator/config/config.yaml`
  - `auction-simulator/config/local.yaml.template`
- **Behavioral impact**:
  - Increase paid ad/seller reach coverage to include budgeted cold-start ads.
  - Increase budget utilization by removing artificial exclusions from denominator and participant pool.
  - Improve free-ad organic coverage while preserving total reach conservation.
