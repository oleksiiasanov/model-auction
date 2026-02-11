# Implementation Tasks

## 1. Add Paid Status Flags to Reports

### 1.1 Update Seller Comparison Report
- [ ] 1.1.1 In `Reporter.build_seller_comparison()`, calculate `is_paid_actual`:
  - [ ] Group `budgets_df` by `seller_id`
  - [ ] Calculate `MAX(daily_budget)` per seller
  - [ ] Set `is_paid_actual = true` if max > 0
- [ ] 1.1.2 Calculate `is_paid_simulated`:
  - [ ] Check if `simulated_spending > 0` per seller
- [ ] 1.1.3 Insert columns after `seller_id` column
- [ ] 1.1.4 Update CSV column order to place flags early

### 1.2 Update Ad Comparison Report
- [ ] 1.2.1 In `Reporter.build_ad_comparison()`, calculate `is_paid_actual`:
  - [ ] Group `budgets_df` by `ad_id`
  - [ ] Calculate `MAX(daily_budget)` per ad
  - [ ] Set `is_paid_actual = true` if max > 0
- [ ] 1.2.2 Calculate `is_paid_simulated`:
  - [ ] Check if `simulated_spending > 0` per ad
- [ ] 1.2.3 Insert columns after ID columns
- [ ] 1.2.4 Update CSV column order

### 1.3 Update CSV Metadata
- [ ] 1.3.1 Add documentation comments for `is_paid_actual` and `is_paid_simulated` in CSV header
- [ ] 1.3.2 Explain calculation logic in comments

### 1.4 Boolean Formatting
- [ ] 1.4.1 Ensure boolean values exported as lowercase strings ("true"/"false")
- [ ] 1.4.2 Handle null/missing values (default to "false")

### 1.5 Testing
- [ ] 1.5.1 Unit test: seller with paid campaigns → `is_paid_actual = true`
- [ ] 1.5.2 Unit test: seller with no campaigns → `is_paid_actual = false`
- [ ] 1.5.3 Unit test: seller spent in simulation → `is_paid_simulated = true`
- [ ] 1.5.4 Unit test: seller didn't spend → `is_paid_simulated = false`
- [ ] 1.5.5 Integration test: check CSV has columns in correct order
- [ ] 1.5.6 Integration test: verify boolean string format

## 2. Create SimulationLogger Class

### 2.1 Core Logger Implementation
- [ ] 2.1.1 Create `src/auction_simulator/logger.py` module
- [ ] 2.1.2 Implement `SimulationLogger` class with `__init__()`:
  - [ ] Accept `output_dir`, `timestamp`, `config` parameters
  - [ ] Open JSONL file handle if `log_format` in ['jsonl', 'both']
  - [ ] Open TXT file handle if `log_format` in ['text', 'both']
  - [ ] Create output directory if not exists
- [ ] 2.1.3 Implement `log_event(event_type, data)` method:
  - [ ] Call `_write_jsonl()` if JSONL enabled
  - [ ] Call `_write_text()` if text enabled
- [ ] 2.1.4 Implement `close()` method:
  - [ ] Flush all file handles
  - [ ] Close all file handles
- [ ] 2.1.5 Add context manager support (`__enter__`, `__exit__`)

### 2.2 JSONL Writer
- [ ] 2.2.1 Implement `_write_jsonl(event_type, data)`:
  - [ ] Create JSON object with `timestamp`, `event`, and data fields
  - [ ] Serialize to JSON string
  - [ ] Write line with newline
  - [ ] Flush file
- [ ] 2.2.2 Use ISO 8601 timestamp format
- [ ] 2.2.3 Handle nested data structures (arrays, objects)

### 2.3 Text Writer
- [ ] 2.3.1 Implement `_write_text(event_type, data)`:
  - [ ] Switch on `event_type`
  - [ ] Format output based on event type
  - [ ] Flush file
- [ ] 2.3.2 Implement formatting for `day_start` event
- [ ] 2.3.3 Implement formatting for `hour_start` event
- [ ] 2.3.4 Implement formatting for `batch_auction` event with indentation
- [ ] 2.3.5 Implement formatting for `organic_fallback` event
- [ ] 2.3.6 Add number formatting helpers:
  - [ ] Comma thousands separator
  - [ ] Decimal places control
  - [ ] Kopeck symbol (₭)

### 2.4 Configuration
- [ ] 2.4.1 Update `config/config.yaml` with logging section:
  ```yaml
  logging:
    simulation_log_enabled: true
    log_format: "both"  # jsonl, text, both
    log_top_n_winners: 10
    log_pressure_changes: true
    log_pacing_events: true
    log_budget_events: true
    log_directory: "outputs"
  ```
- [ ] 2.4.2 Update `config/local.yaml.template` with same section

### 2.5 Testing
- [ ] 2.5.1 Unit test: Logger creates JSONL file when enabled
- [ ] 2.5.2 Unit test: Logger creates TXT file when enabled
- [ ] 2.5.3 Unit test: Logger creates both files with format="both"
- [ ] 2.5.4 Unit test: Logger doesn't create files when disabled
- [ ] 2.5.5 Unit test: JSONL format is valid (parseable JSON per line)
- [ ] 2.5.6 Unit test: TXT format is readable
- [ ] 2.5.7 Unit test: Context manager properly closes files

## 3. Integrate Logging into Simulation

### 3.1 Add Logger to Simulation Class
- [ ] 3.1.1 In `Simulation.__init__()`, create logger if enabled:
  ```python
  self.logger = SimulationLogger(...) if config.logging.simulation_log_enabled else None
  ```
- [ ] 3.1.2 Add `close()` call in `run_simulation()` (try/finally block)
- [ ] 3.1.3 Pass logger to methods that need it

### 3.2 Log Day Events
- [ ] 3.2.1 In `run_simulation()`, log `day_start` at beginning of each day:
  - [ ] Count `total_ads`
  - [ ] Count `ads_with_budget`
  - [ ] Sum `total_daily_budget`
- [ ] 3.2.2 Log `day_complete` at end of each day:
  - [ ] Calculate `total_impressions_allocated`
  - [ ] Calculate `paid_impressions`, `organic_impressions`
  - [ ] Calculate `total_spending`
  - [ ] Count `ads_exhausted`

### 3.3 Log Hour Events
- [ ] 3.3.1 In `simulate_hour()`, log `hour_start`:
  - [ ] Include `category_id`, `hour`, `total_impressions`, `min_bid`
- [ ] 3.3.2 Log `hour_complete` at end:
  - [ ] Calculate `total_allocated`, `paid_slots`, `organic_slots`
  - [ ] Count `num_batches`, `unique_winners`

### 3.4 Testing
- [ ] 3.4.1 Integration test: Run simulation, verify day events logged
- [ ] 3.4.2 Integration test: Verify hour events logged for each hour
- [ ] 3.4.3 Integration test: Verify logger properly closed after simulation

## 4. Integrate Logging into AuctionEngine

### 4.1 Log Batch Auction Events
- [ ] 4.1.1 In `run_batch_auction()`, accept optional `logger` parameter
- [ ] 4.1.2 Log `batch_start` at beginning:
  - [ ] Count `eligible_ads`, `ads_with_budget`
  - [ ] Include `slots`, `time_progress`, `time_left`
- [ ] 4.1.3 After `select_winners()`, log `auction_winners`:
  - [ ] Extract top N winners (configurable)
  - [ ] Include `ad_id`, `seller_id`, `pressure`, `rank`, `bid`, `remaining_budget`
  - [ ] Include `total_winners` count
- [ ] 4.1.4 Log `batch_complete` at end:
  - [ ] Include `allocated`, `remaining_slots`

### 4.2 Track Pressure Changes
- [ ] 4.2.1 Store previous batch's top winners (if `log_pressure_changes = true`)
- [ ] 4.2.2 Compare current batch winners with previous:
  - [ ] If ad was in both batches, check if pressure changed
  - [ ] Log `pressure_change` event with before/after values
- [ ] 4.2.3 Include `budget_before`, `budget_after`, `reason`

### 4.3 Log Pacing Events
- [ ] 4.3.1 In `check_pacing_gate()`, detect when ad is paused
- [ ] 4.3.2 If `log_pacing_events = true`, log `pacing_exclusion`:
  - [ ] Include `actual_spend`, `expected_spend`, `max_allowed`, `pacing_tolerance`
- [ ] 4.3.3 Detect when ad resumes (was paused, now eligible)
- [ ] 4.3.4 Log `pacing_resume` event

### 4.4 Log Budget Exhaustion
- [ ] 4.4.1 In `charge_winners()`, detect when `remaining_budget` reaches 0
- [ ] 4.4.2 If `log_budget_events = true`, log `budget_exhaustion`:
  - [ ] Include `initial_budget`, `total_spent`, `impressions_won`, `time_progress`

### 4.5 Log Organic Fallback
- [ ] 4.5.1 In `distribute_organic_proportional()`, log `organic_fallback`:
  - [ ] Include `method = "proportional"`
  - [ ] Include array of allocations with `ad_id`, `organic_historical`, `allocated`
  - [ ] Include conservation check: `expected`, `actual`, `valid`
- [ ] 4.5.2 In `distribute_organic_equal()`, log with `method = "equal"`
- [ ] 4.5.3 Log ERROR if conservation check fails

### 4.6 Testing
- [ ] 4.6.1 Unit test: Batch events logged with correct data
- [ ] 4.6.2 Unit test: Top N winners limit respected
- [ ] 4.6.3 Unit test: Pressure changes detected and logged
- [ ] 4.6.4 Unit test: Pacing exclusions logged
- [ ] 4.6.5 Unit test: Budget exhaustion logged
- [ ] 4.6.6 Unit test: Organic fallback logged with conservation check

## 5. Update Documentation

### 5.1 Update README
- [ ] 5.1.1 Add section on paid status flags in reports
- [ ] 5.1.2 Add section on simulation logging
- [ ] 5.1.3 Add examples of filtering by `is_paid_actual`
- [ ] 5.1.4 Add examples of analyzing JSONL logs with jq
- [ ] 5.1.5 Add examples of loading logs with pandas

### 5.2 Update QUICKSTART
- [ ] 5.2.1 Mention new logging configuration options
- [ ] 5.2.2 Show how to disable logging for faster runs
- [ ] 5.2.3 Show example log output

### 5.3 Create Log Analysis Guide
- [ ] 5.3.1 Create `auction-simulator/LOG_ANALYSIS.md`
- [ ] 5.3.2 Document JSONL format and event types
- [ ] 5.3.3 Provide jq query examples
- [ ] 5.3.4 Provide Python analysis examples
- [ ] 5.3.5 Show how to trace specific ad through simulation
- [ ] 5.3.6 Show how to validate conservation at each step

## 6. Performance Testing and Optimization

### 6.1 Measure Overhead
- [ ] 6.1.1 Run simulation with logging disabled (baseline)
- [ ] 6.1.2 Run simulation with JSONL only
- [ ] 6.1.3 Run simulation with text only
- [ ] 6.1.4 Run simulation with both formats
- [ ] 6.1.5 Measure runtime difference (should be < 15%)

### 6.2 Optimize if Needed
- [ ] 6.2.1 If overhead > 15%, profile to find bottleneck
- [ ] 6.2.2 Consider batch writing (buffer N events before flush)
- [ ] 6.2.3 Consider reducing default `log_top_n_winners`
- [ ] 6.2.4 Consider lazy JSON serialization

### 6.3 File Size Testing
- [ ] 6.3.1 Measure log file sizes for typical simulation
- [ ] 6.3.2 Verify JSONL < 5MB per simulation day
- [ ] 6.3.3 Verify TXT < 2MB per simulation day
- [ ] 6.3.4 Document expected file sizes in README

## 7. Integration Testing

### 7.1 End-to-End Test with Logging
- [ ] 7.1.1 Run full simulation (3 days, multiple categories)
- [ ] 7.1.2 Verify both log files created
- [ ] 7.1.3 Verify CSV reports have `is_paid_*` columns
- [ ] 7.1.4 Load JSONL and verify all event types present
- [ ] 7.1.5 Manually inspect TXT summary for readability

### 7.2 Validate Log Correctness
- [ ] 7.2.1 Parse JSONL logs and reconstruct simulation state
- [ ] 7.2.2 Verify final state matches CSV reports
- [ ] 7.2.3 Check conservation holds at every hour (from logs)
- [ ] 7.2.4 Verify top winners match expected pressure ranking
- [ ] 7.2.5 Trace one ad through entire simulation, verify budget deductions

### 7.3 Edge Case Testing
- [ ] 7.3.1 Test with all ads organic (no budgets)
- [ ] 7.3.2 Test with all budgets exhausted early
- [ ] 7.3.3 Test with heavy pacing gate activity
- [ ] 7.3.4 Test with logging disabled (verify no performance impact)

## 8. Update Configuration Files

### 8.1 Default Config
- [ ] 8.1.1 Ensure `config/config.yaml` has logging section with sensible defaults

### 8.2 Template Config
- [ ] 8.2.1 Update `config/local.yaml.template` with logging section
- [ ] 8.2.2 Add comments explaining each option

## 9. Code Review and Cleanup

### 9.1 Code Quality
- [ ] 9.1.1 Add type hints to all new methods
- [ ] 9.1.2 Add docstrings to all new classes and methods
- [ ] 9.1.3 Run linter (flake8) and fix issues
- [ ] 9.1.4 Run type checker (mypy) and fix issues

### 9.2 Test Coverage
- [ ] 9.2.1 Run pytest with coverage
- [ ] 9.2.2 Ensure new code has > 80% coverage
- [ ] 9.2.3 Write missing tests if needed

## 10. Final Validation

### 10.1 Manual Testing
- [ ] 10.1.1 Run test connection script
- [ ] 10.1.2 Run simulation with real production data
- [ ] 10.1.3 Review generated CSV reports:
  - [ ] Verify `is_paid_actual` and `is_paid_simulated` columns present
  - [ ] Spot check a few sellers/ads for correctness
- [ ] 10.1.4 Review generated logs:
  - [ ] Open JSONL in text editor, verify format
  - [ ] Open TXT summary, verify readability
  - [ ] Check file sizes are reasonable

### 10.2 Stakeholder Demo
- [ ] 10.2.1 Prepare demo showing:
  - [ ] Paid status filtering in reports
  - [ ] Step-by-step auction trace in logs
  - [ ] Pressure changes over time
  - [ ] Conservation validation at each step
- [ ] 10.2.2 Walk through log analysis examples
- [ ] 10.2.3 Demonstrate debugging capability

---

## Summary

### Files to Create
- `src/auction_simulator/logger.py` (new SimulationLogger class)
- `auction-simulator/LOG_ANALYSIS.md` (new documentation)

### Files to Modify
- `src/auction_simulator/reporting.py` (add is_paid columns)
- `src/auction_simulator/simulation.py` (integrate logger, log day/hour events)
- `src/auction_simulator/auction_engine.py` (integrate logger, log batch/pressure/pacing/budget events)
- `config/config.yaml` (add logging section)
- `config/local.yaml.template` (add logging section)
- `README.md` (document new features)
- `QUICKSTART.md` (mention logging options)

### Key Dependencies
- No new external dependencies required
- Uses standard library: `json`, `datetime`, `pathlib`

### Estimated Complexity
- **Paid status flags**: Low complexity (simple aggregation)
- **Simulation logging**: Medium complexity (event tracking, dual format)
- **Total effort**: ~2-3 days for full implementation and testing

### Success Criteria
- ✅ CSV reports include `is_paid_actual` and `is_paid_simulated`
- ✅ JSONL logs capture all events with structured data
- ✅ TXT logs are human-readable and scannable
- ✅ Logging overhead < 15%
- ✅ All tests pass
- ✅ Documentation complete
