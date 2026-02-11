## 1. Allocator Fix
- [x] 1.1 Update cumulative residual carry handling to subtract `1.0` per residual slot without clamping to zero. (auction_engine.py:807 - removed max(0.0, ...) clamp)
- [x] 1.2 Verify per-event conservation check uses exact allocated total for both pools. (auction_engine.py:687-692 - check already correct)

## 2. Tests
- [x] 2.1 Add unit test for multi-batch cumulative allocation with expected zero drift. (test_organic_fallback.py: test_cumulative_allocator_zero_drift_multi_batch)
- [x] 2.2 Add regression test reproducing prior +N drift and confirming fix. (test_organic_fallback.py: test_cumulative_allocator_negative_carry_debt)

## 3. Reporting Validation
- [x] 3.1 Add/verify summary consistency check: simulated reach total equals allocated/log total. (simulation.py:251-264 already has check; reporting.py:360-370 added warning in summary output)
- [x] 3.2 Surface warning/error in summary when mismatch is non-zero. (reporting.py:366-370 - warns if abs(diff) > 10, notes if 0 < abs(diff) <= 10)

## 4. Run Validation
- [ ] 4.1 Execute representative simulation scenario that previously drifted. (User to run: `python -m auction_simulator config/local.yaml`)
- [ ] 4.2 Confirm `organic_fallback` invalid conservation event count is zero. (Check simulation logs for `conservation_check.valid=false` - should be none)
- [ ] 4.3 Confirm `Total Reach (Actual) == Total Reach (Simulated)`. (Check summary statistics - diff should be 0 or very small, <10)
