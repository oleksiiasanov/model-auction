## ADDED Requirements
### Requirement: Active vs Total Budget Utilization Reporting
The system SHALL report both overall paid budget utilization and active paid budget utilization.

#### Scenario: Separate denominators in summary output
- **WHEN** simulation includes paid ads without historical reach
- **THEN** summary includes:
  - `budget_total_all_paid`
  - `budget_total_active_paid`
  - `overall_budget_utilization = simulated_spend / budget_total_all_paid`
  - `active_budget_utilization = simulated_spend / budget_total_active_paid`

#### Scenario: Active utilization approaches full spend for active pool
- **WHEN** active paid ads spend nearly all assigned budget
- **THEN** active utilization can be near 100% even if overall utilization is lower due to inactive paid rows
- **AND** report explains the denominator difference

### Requirement: Paid Coverage Diagnostics
The system SHALL report paid reach coverage diagnostics for ads and sellers.

#### Scenario: Paid ads coverage summary
- **WHEN** simulation completes
- **THEN** summary includes `paid_ads_with_reach / total_paid_ads`
- **AND** includes count of paid ads with zero simulated reach

#### Scenario: Paid sellers coverage summary
- **WHEN** simulation completes
- **THEN** summary includes `paid_sellers_with_reach / total_paid_sellers`
- **AND** includes count of paid sellers with zero simulated reach

### Requirement: Period-Level Paid/Free Classification in Summary
The system SHALL compute paid/free coverage using period-level paid status, not day-end budget state.

#### Scenario: Paid ad exhausted mid-period remains paid in coverage metrics
- **WHEN** ad has budget on any day in simulation period
- **AND** day-end `daily_budget` state is zero
- **THEN** ad is still counted in paid denominator for coverage metrics
- **AND** free denominator excludes that ad

### Requirement: Deduplicated Summary Aggregation
The system SHALL deduplicate entity rows before aggregate summary metrics to prevent double counting.

#### Scenario: No duplicate ad contribution in simulated total reach
- **WHEN** ad comparison contains multiple rows for same ad entity due to merge artifacts
- **THEN** summary aggregation deduplicates ad entity before totals
- **AND** `total_reach_simulated` in summary equals allocated reach total from simulation engine/log
