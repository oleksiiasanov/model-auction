# simulation-logging Specification

## Purpose
TBD - created by archiving change add-detailed-logging-and-paid-flags. Update Purpose after archive.
## Requirements
### Requirement: Dual-Format Logging System

The system SHALL provide dual-format logging (JSONL and human-readable text) for complete simulation traceability.

#### Scenario: Enable both log formats

- **WHEN** config specifies `logging.log_format = "both"`
- **THEN** system creates two log files:
  - `outputs/simulation_log_TIMESTAMP.jsonl` (structured)
  - `outputs/simulation_summary_TIMESTAMP.txt` (human-readable)

#### Scenario: Enable JSONL only

- **WHEN** config specifies `logging.log_format = "jsonl"`
- **THEN** system creates only `simulation_log_TIMESTAMP.jsonl`
- **AND** no text summary file is created

#### Scenario: Enable text only

- **WHEN** config specifies `logging.log_format = "text"`
- **THEN** system creates only `simulation_summary_TIMESTAMP.txt`
- **AND** no JSONL file is created

#### Scenario: Disable logging

- **WHEN** config specifies `logging.simulation_log_enabled = false`
- **THEN** no log files are created
- **AND** simulation runs without logging overhead

### Requirement: Day-Level Event Logging

The system SHALL log day-level events for multi-day simulation tracking.

#### Scenario: Log day start event

- **WHEN** simulation starts processing new day
- **THEN** log event with type `day_start` containing:
  - `date` (YYYY-MM-DD)
  - `total_ads` (count of all ads)
  - `ads_with_budget` (count of ads with daily_budget > 0)
  - `total_daily_budget` (sum of all daily budgets in kopecks)

#### Scenario: Log day complete event

- **WHEN** simulation completes processing day
- **THEN** log event with type `day_complete` containing:
  - `date`
  - `total_impressions_allocated`
  - `paid_impressions`
  - `organic_impressions`
  - `total_spending` (kopecks)
  - `ads_exhausted` (count of ads that exhausted budget)

### Requirement: Hour-Level Event Logging

The system SHALL log hour-level events for granular time-based analysis.

#### Scenario: Log hour start event

- **WHEN** simulation starts processing hour
- **THEN** log event with type `hour_start` containing:
  - `date` (YYYY-MM-DD)
  - `hour` (0-23)
  - `category_id`
  - `total_impressions` (target slots for this hour)
  - `min_bid` (kopecks, float)

#### Scenario: Log hour complete event

- **WHEN** simulation completes processing hour
- **THEN** log event with type `hour_complete` containing:
  - `category_id`
  - `hour`
  - `total_allocated` (should equal total_impressions from start)
  - `paid_slots`
  - `organic_slots`
  - `num_batches`
  - `unique_winners` (count of unique ad_ids that won)

### Requirement: Batch Auction Event Logging

The system SHALL log detailed information for each batch auction including top winners.

#### Scenario: Log batch start event

- **WHEN** batch auction begins
- **THEN** log event with type `batch_start` containing:
  - `batch` (batch number, 1-indexed)
  - `category_id`
  - `hour`
  - `slots` (impression slots for this batch)
  - `eligible_ads` (total ads eligible)
  - `ads_with_budget` (ads with remaining_budget > 0)
  - `time_progress` (fraction of day elapsed)
  - `time_left` (fraction of day remaining)

#### Scenario: Log auction winners

- **WHEN** winners are selected for batch
- **THEN** log event with type `auction_winners` containing:
  - `batch`
  - `category_id`
  - `hour`
  - `top_winners` (array of top N winners, configurable):
    - `ad_id`
    - `seller_id`
    - `pressure` (calculated pressure value)
    - `rank` (rank_index, 0-indexed)
    - `bid` (effective_bid in kopecks)
    - `remaining_budget` (before charging)
    - `impressions_won`
  - `total_winners` (total count, may be > top_winners length)

#### Scenario: Limit top winners logged

- **WHEN** config specifies `logging.log_top_n_winners = 10`
- **AND** batch has 40 winners
- **THEN** `top_winners` array contains only first 10 winners (by rank)
- **AND** `total_winners = 40`

#### Scenario: Log batch complete event

- **WHEN** batch auction completes
- **THEN** log event with type `batch_complete` containing:
  - `batch`
  - `allocated` (slots actually allocated in this batch)
  - `remaining_slots` (slots left for subsequent batches)

### Requirement: Pressure Change Tracking

The system SHALL log pressure changes for top ads between batches when enabled.

#### Scenario: Track pressure change after budget deduction

- **WHEN** config enables `logging.log_pressure_changes = true`
- **AND** ad was in top N winners in previous batch
- **AND** ad's pressure changed in current batch
- **THEN** log event with type `pressure_change` containing:
  - `batch`
  - `ad_id`
  - `pressure_before`
  - `pressure_after`
  - `budget_before`
  - `budget_after`
  - `reason` ("charged_for_impression")

#### Scenario: Track pressure change after time progress

- **WHEN** ad's pressure changes due to time progression (not budget change)
- **THEN** log event with `reason` = "time_progression"

#### Scenario: Disable pressure change tracking

- **WHEN** config specifies `logging.log_pressure_changes = false`
- **THEN** no `pressure_change` events are logged
- **AND** logging overhead is reduced

### Requirement: Pacing Gate Event Logging

The system SHALL log when ads are paused or excluded by pacing gate.

#### Scenario: Log pacing exclusion

- **WHEN** config enables `logging.log_pacing_events = true`
- **AND** ad is paused by pacing gate (`actual_spend > expected_spend * (1 + tolerance)`)
- **THEN** log event with type `pacing_exclusion` containing:
  - `batch`
  - `ad_id`
  - `reason` ("exceeded_pacing_limit")
  - `actual_spend` (kopecks)
  - `expected_spend` (kopecks)
  - `max_allowed` (expected * (1 + tolerance))
  - `pacing_tolerance` (from config, e.g., 0.2)

#### Scenario: Log pacing resume

- **WHEN** ad was previously paused and becomes eligible again
- **THEN** log event with type `pacing_resume` containing:
  - `batch`
  - `ad_id`
  - `actual_spend`
  - `expected_spend`
  - `reason` ("time_caught_up")

#### Scenario: Disable pacing event logging

- **WHEN** config specifies `logging.log_pacing_events = false`
- **THEN** no `pacing_exclusion` or `pacing_resume` events are logged

### Requirement: Budget Exhaustion Event Logging

The system SHALL log when ads exhaust their budget during simulation.

#### Scenario: Log budget exhaustion

- **WHEN** config enables `logging.log_budget_events = true`
- **AND** ad's remaining_budget reaches 0 during batch
- **THEN** log event with type `budget_exhaustion` containing:
  - `batch`
  - `ad_id`
  - `seller_id`
  - `category_id`
  - `hour`
  - `initial_budget` (daily_budget at day start)
  - `total_spent` (cumulative spending)
  - `impressions_won` (cumulative impressions)
  - `time_progress` (fraction when exhausted)

#### Scenario: Multiple ads exhaust budget in same batch

- **WHEN** multiple ads exhaust budget in same batch
- **THEN** log separate `budget_exhaustion` event for each ad

#### Scenario: Disable budget event logging

- **WHEN** config specifies `logging.log_budget_events = false`
- **THEN** no `budget_exhaustion` events are logged

### Requirement: Organic Fallback Event Logging

The system SHALL log organic fallback distribution when all budgets are exhausted.

#### Scenario: Log proportional organic fallback

- **WHEN** remaining slots are distributed using proportional method
- **THEN** log event with type `organic_fallback` containing:
  - `category_id`
  - `hour`
  - `remaining_slots`
  - `method` ("proportional")
  - `allocations` (array):
    - `ad_id`
    - `organic_historical` (historical organic impressions)
    - `allocated` (slots allocated)
  - `conservation_check`:
    - `expected` (remaining_slots)
    - `actual` (sum of allocated)
    - `valid` (boolean: expected == actual)

#### Scenario: Log equal organic fallback

- **WHEN** remaining slots are distributed using equal method (no historical organic data)
- **THEN** log event with `method` = "equal"
- **AND** `allocations` contains equal base allocation + remainder distribution

#### Scenario: Conservation check failure

- **WHEN** organic fallback violates conservation (sum != remaining_slots)
- **THEN** log event with `conservation_check.valid = false`
- **AND** log ERROR level message

### Requirement: JSONL Format Requirements

The system SHALL write JSONL logs with consistent structure and timestamps.

#### Scenario: JSONL line format

- **WHEN** logging event to JSONL file
- **THEN** each line is valid JSON object containing:
  - `timestamp` (ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ffffff)
  - `event` (event type string)
  - ... (event-specific data fields)

#### Scenario: JSONL line termination

- **WHEN** writing JSONL line
- **THEN** line ends with newline character (`\n`)
- **AND** no trailing comma or extra characters

#### Scenario: JSONL flush behavior

- **WHEN** event is logged
- **THEN** file is flushed after write
- **AND** data is immediately available for reading (not buffered)

### Requirement: Human-Readable Text Format Requirements

The system SHALL write text logs with visual hierarchy and readability.

#### Scenario: Day header formatting

- **WHEN** logging day start in text format
- **THEN** output formatted as:
  ```
  ================================================================================
  DAY: 2024-01-15 | Total Ads: 150 | Ads with Budget: 45
  ================================================================================
  ```

#### Scenario: Hour header formatting

- **WHEN** logging hour start in text format
- **THEN** output formatted as:
  ```
  [10:00] Category 1234 | Total Impressions: 5,000
  ------------------------------------------------------------------------
  ```

#### Scenario: Batch formatting with hierarchy

- **WHEN** logging batch auction in text format
- **THEN** output formatted with indentation:
  ```
    Batch #1 (slots: 40)
    ├─ Eligible: 100 ads (40 with budget, 60 organic)
    ├─ Top 10 Winners:
    │  1. Ad 777 | pressure=13,793 | bid=1.4₭ | remaining=9,998
    │  2. Ad 888 | pressure=10,234 | bid=1.3₭ | remaining=8,500
    │  ...
    └─ Allocated: 40 | Remaining: 4,960
  ```

#### Scenario: Number formatting

- **WHEN** logging numbers in text format
- **THEN** use comma thousands separator for large numbers (e.g., `10,000`)
- **AND** use 1-2 decimal places for floats (e.g., `13,793.5`)
- **AND** use kopeck symbol (₭) or "₭" suffix for currency

### Requirement: Configuration Options

The system SHALL provide comprehensive configuration for logging behavior.

#### Scenario: Default configuration

- **WHEN** no logging configuration specified
- **THEN** use defaults:
  - `simulation_log_enabled: true`
  - `log_format: "both"`
  - `log_top_n_winners: 10`
  - `log_pressure_changes: true`
  - `log_pacing_events: true`
  - `log_budget_events: true`
  - `log_directory: "outputs"`

#### Scenario: Minimal logging configuration

- **WHEN** config specifies minimal logging:
  ```yaml
  logging:
    simulation_log_enabled: true
    log_format: "text"
    log_top_n_winners: 5
    log_pressure_changes: false
    log_pacing_events: false
    log_budget_events: false
  ```
- **THEN** only basic auction events logged (no detailed tracking)
- **AND** performance overhead is minimal

#### Scenario: Full logging configuration

- **WHEN** config enables all logging features
- **THEN** all events are logged with maximum detail
- **AND** files are larger but provide complete audit trail

### Requirement: Logger Lifecycle Management

The system SHALL properly initialize and cleanup logger resources.

#### Scenario: Logger initialization

- **WHEN** `Simulation` object is created
- **AND** `logging.simulation_log_enabled = true`
- **THEN** `SimulationLogger` is instantiated
- **AND** log files are opened for writing
- **AND** log directory is created if not exists

#### Scenario: Logger cleanup

- **WHEN** simulation completes (successfully or with error)
- **THEN** logger files are flushed
- **AND** logger files are closed
- **AND** no file handles remain open

#### Scenario: Logger is None when disabled

- **WHEN** `logging.simulation_log_enabled = false`
- **THEN** `Simulation.logger = None`
- **AND** no logging overhead or file operations occur

### Requirement: Performance Optimization

The system SHALL minimize logging performance impact on simulation runtime.

#### Scenario: Conditional logging checks

- **WHEN** logging is disabled
- **THEN** no logging code is executed (early return on `if logger is None`)
- **AND** no performance penalty

#### Scenario: Buffered I/O

- **WHEN** logging many events
- **THEN** file writes use buffered I/O
- **AND** flush occurs after each event (for immediate visibility)

#### Scenario: Top-N winner limitation

- **WHEN** batch has 40 winners
- **AND** `log_top_n_winners = 10`
- **THEN** only first 10 winners are serialized to JSON/text
- **AND** reduces log size and serialization overhead

#### Scenario: Performance overhead measurement

- **WHEN** simulation runs with logging enabled
- **THEN** total runtime overhead is < 15%
- **AND** most overhead is I/O (writing files), not CPU

### Requirement: Log Analysis Tools Documentation

The system SHALL provide examples for analyzing JSONL logs programmatically.

#### Scenario: Query events with jq

- **WHEN** user wants to extract specific events
- **THEN** documentation provides jq examples:
  ```bash
  # Find all budget exhaustion events
  cat simulation_log_*.jsonl | jq 'select(.event == "budget_exhaustion")'

  # Count pacing exclusions per hour
  cat simulation_log_*.jsonl | jq -s '
    map(select(.event == "pacing_exclusion")) |
    group_by(.hour) |
    map({hour: .[0].hour, count: length})
  '
  ```

#### Scenario: Load JSONL with pandas

- **WHEN** user wants to analyze logs in Python
- **THEN** documentation provides example:
  ```python
  import json
  import pandas as pd

  events = []
  with open('simulation_log_*.jsonl') as f:
      for line in f:
          events.append(json.loads(line))

  df = pd.DataFrame(events)
  ```

#### Scenario: Trace ad behavior

- **WHEN** user wants to trace specific ad through simulation
- **THEN** documentation provides filtering examples:
  ```python
  ad_777_events = df[
      df.apply(lambda row:
          row['ad_id'] == 777 if 'ad_id' in row else
          any(w['ad_id'] == 777 for w in row.get('top_winners', [])),
          axis=1
      )
  ]
  ```

### Requirement: Feedback Controller Update Logging
The system SHALL log controller updates for feedback pricing decisions.

#### Scenario: Log multiplier update event
- **WHEN** controller updates multiplier for a category/day
- **THEN** log event `multiplier_update` contains:
  - `category_id`
  - `date`
  - `hour`
  - `target_cumulative_spend`
  - `actual_cumulative_spend`
  - `error`
  - `integral_error`
  - `multiplier_before`
  - `multiplier_after`
  - `clamped` flag

#### Scenario: Log disabled when feature is off
- **WHEN** feedback pricing is disabled
- **THEN** no `multiplier_update` events are emitted

