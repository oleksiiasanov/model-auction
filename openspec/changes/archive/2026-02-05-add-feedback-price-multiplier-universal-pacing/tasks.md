## 1. Configuration
- [x] 1.1 Add `feedback_pricing` config block (enabled, Kp, Ki, alpha, multiplier_min/max, delta_limit, update_cadence). (config.yaml, local.yaml)
- [x] 1.2 Add target curve config (`linear` default, optional shape presets). (target_curve: shape in config)

## 2. Auction Engine
- [x] 2.1 Add per-category/day controller state store. (self.controller_state in __init__)
- [x] 2.2 Implement PI update function with bounds and smoothing. (update_price_multiplier, calculate_target_spend methods)
- [x] 2.3 Apply `price_multiplier` to paid `effective_bid` calculation. (select_winners applies multiplier)
- [x] 2.4 Preserve budget cap charging and deterministic ranking. (charge_winners unchanged, ranking preserved)

## 3. Simulation Integration
- [x] 3.1 Update controller at configured cadence (default hourly) using spend trajectory error. (run_hour_auction updates controller at hour start)
- [x] 3.2 Reset controller state at day boundary per category. (reset_controller_state_for_day called per category)
- [x] 3.3 Track per-hour spend target vs actual for diagnostics. (controller_diagnostics logged in multiplier_update event)

## 4. Logging and Reporting
- [x] 4.1 Log controller events (`multiplier_update`, error, integral, clamps). (sim_logger.log_event('multiplier_update') in run_hour_auction)
- [x] 4.2 Add summary metrics: utilization gap, multiplier min/max/avg, saturation flags. (Feedback Pricing Controller section in build_summary_statistics)
- [ ] 4.3 Add per-category diagnostics table for controller behavior. (Deferred - can be added later if needed)

## 5. Validation
- [x] 5.1 Add unit tests for controller math and bounds. (test_feedback_pricing.py with 9 test cases)
- [ ] 5.2 Add integration scenarios for sparse-paid and dense-paid categories. (User to run with enabled=true)
- [ ] 5.3 Compare baseline vs feedback-pricing runs and document KPI deltas. (User to run validation)
