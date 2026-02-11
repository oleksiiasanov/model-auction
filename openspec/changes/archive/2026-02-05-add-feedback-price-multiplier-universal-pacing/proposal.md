# Change: Add Feedback Price Multiplier for Universal Pacing

## Why
Current auction controls (`pressure` + pacing gate) prioritize and limit spending but do not guarantee sufficient spend in structurally different categories.

Observed behavior across runs:
- Some categories under-spend heavily (e.g., ~30% utilization) when paid participant count is low.
- Some categories can overspend or aggressively concentrate spend when paid density is high.
- Fixed or manually tuned `bid_step` is not robust across ~3000 heterogeneous categories (small, large, sparse-paid, dense-paid).

A universal mechanism is needed that adapts automatically per category/day without manual tuning.

## What Changes
- Add a per-category/day **feedback controller** that adjusts a `price_multiplier` over time.
- Apply multiplier to paid auction price calculation:
  - `effective_bid = base_effective_bid * price_multiplier`
- Compute controller error from spend trajectory gap:
  - `error_t = target_cumulative_spend_t - actual_cumulative_spend_t`
- Update multiplier hourly (or per configurable cadence) with bounded PI-style control.
- Keep existing safety invariants:
  - budget-safe charging (`charged = min(cost, remaining_budget)`)
  - reach conservation
  - deterministic winner selection.
- Add observability to logs and reports:
  - multiplier path by hour
  - spend trajectory tracking vs target
  - per-category utilization diagnostics.

## Impact
- **Affected specs**:
  - `auction-engine`
  - `comparison-reporting`
  - `simulation-logging`
- **Affected code (expected)**:
  - `auction-simulator/src/auction_simulator/auction_engine.py`
  - `auction-simulator/src/auction_simulator/simulation.py`
  - `auction-simulator/src/auction_simulator/reporting.py`
  - `auction-simulator/src/auction_simulator/logger.py`
  - `auction-simulator/config/config.yaml`
  - `auction-simulator/config/local.yaml.template`
- **Expected outcomes**:
  - Improved budget utilization consistency across category sizes/compositions.
  - Reduced need for manual `bid_step` tuning per category.
  - Stable spend pacing with explicit guardrails.
