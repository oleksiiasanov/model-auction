# Change: Fix Organic Fallback Conservation Drift

## Why
Recent simulation runs show repeated conservation violations in organic fallback allocation:
- `Total Reach (Simulated)` exceeds `Total Reach (Actual)` by a small but non-zero drift (e.g., +344).
- `organic_fallback` log events contain `conservation_check.valid=false` with over-allocation.

This violates a core invariant of the simulator: exact slot conservation (`allocated == target`) per event and per run.

## What Changes
- Fix cumulative fallback residual allocation math to preserve carry/debt correctly across batches.
- Remove residual carry clamping that can create synthetic allocation mass.
- Add strict assertions/tests for per-event and run-level conservation.
- Add summary-level validation that reports mismatch if simulated total reach differs from allocated/log totals.

## Impact
- **Affected specs**:
  - `auction-engine`
  - `comparison-reporting`
- **Affected code (expected)**:
  - `auction-simulator/src/auction_simulator/auction_engine.py`
  - `auction-simulator/src/auction_simulator/reporting.py`
  - `auction-simulator/tests/` (new tests)
- **Behavioral impact**:
  - `Total Reach (Simulated)` must exactly match target allocated reach volume.
  - No `organic_fallback` conservation violations in valid runs.
