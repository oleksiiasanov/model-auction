# comparison-reporting Specification

## Purpose
TBD - created by archiving change add-auction-simulator. Update Purpose after archive.
## Requirements
### Requirement: Seller-Level Comparison Table
The system SHALL generate a comparison table showing actual vs simulated metrics for each seller.

#### Scenario: Complete seller metrics row
- **WHEN** generating report for a seller who participated in both actual and simulated systems
- **THEN** output row contains: seller_id, paid_impressions_actual, paid_impressions_simulated, total_impressions_actual, total_impressions_simulated, plan_budget, spendings_actual, spendings_simulated

#### Scenario: Seller only in actual data
- **WHEN** a seller had impressions in actual data but zero in simulation (budget exhausted differently)
- **THEN** simulated columns show 0, actual columns show real values

#### Scenario: Seller only in simulated data
- **WHEN** a seller had no impressions in actual data but won impressions in simulation
- **THEN** actual columns show 0, simulated columns show simulated values

### Requirement: Ad-Level Comparison Table
The system SHALL generate a comparison table showing actual vs simulated metrics for each ad.

#### Scenario: Complete ad metrics row
- **WHEN** generating report for an ad that participated in both systems
- **THEN** output row contains: ad_id, seller_id, category_id, paid_impressions_actual, paid_impressions_simulated, total_impressions_actual, total_impressions_simulated, spendings_actual, spendings_simulated

### Requirement: CSV Export
The system SHALL export comparison tables as CSV files for easy analysis in Excel or other tools.

#### Scenario: Export seller comparison table
- **WHEN** simulation completes successfully
- **THEN** a CSV file named "seller_comparison_YYYY-MM-DD.csv" is created with all seller rows

#### Scenario: Export ad comparison table
- **WHEN** simulation completes successfully
- **THEN** a CSV file named "ad_comparison_YYYY-MM-DD.csv" is created with all ad rows

#### Scenario: Include metadata header
- **WHEN** exporting CSV
- **THEN** file includes comment lines at top with simulation date, categories processed, and key parameters used

### Requirement: Summary Statistics
The system SHALL calculate and include summary statistics across all sellers and ads.

#### Scenario: Total impressions summary with paid/organic split
- **WHEN** generating summary statistics
- **THEN** report total_impressions_actual, total_impressions_simulated (should be equal), total_paid_actual, total_paid_simulated, total_organic_actual, total_organic_simulated

#### Scenario: Paid impression redistribution
- **WHEN** generating summary statistics
- **THEN** report shows paid_impressions_simulated may be higher than paid_impressions_actual (more ads have budget when they win), organic correspondingly lower

#### Scenario: Total spending summary
- **WHEN** generating summary statistics
- **THEN** report total_spendings_actual, total_spendings_simulated, and difference

#### Scenario: Seller distribution summary
- **WHEN** generating summary statistics
- **THEN** report average impressions per seller, median, min, max for both actual and simulated

### Requirement: Data Integrity Validation
The system SHALL validate that comparison data meets integrity constraints before export.

#### Scenario: No negative values
- **WHEN** preparing comparison table
- **THEN** all impression counts and spending values must be >= 0

#### Scenario: Budget overrun check
- **WHEN** preparing comparison table
- **THEN** for each seller, spendings_simulated must be <= plan_budget (log warning if violated)

#### Scenario: Total impression conservation check
- **WHEN** preparing comparison table
- **THEN** sum of total_impressions_simulated across all ads equals sum of total_impressions_actual (same volume redistributed, but paid/organic split may differ)
- **MECHANISM**: Conservation achieved through:
  1. Batch-based auction for paid ads (budget > 0)
  2. Proportional organic fallback with remainder control when all budgets exhausted
  3. Equal distribution fallback with remainder control when no historical organic data
  4. Validation: SUM(allocated_slots) == remaining_slots after each fallback
- **TOLERANCE**: Absolute difference must be 0 (exact conservation, no rounding errors allowed at aggregate level)

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

### Requirement: Summary Reach Consistency Check
The system SHALL validate and report consistency between simulated reach totals and allocated/log totals.

#### Scenario: Consistent totals
- **WHEN** simulation run is valid
- **THEN** summary reports `simulated_total_reach == allocated_total_reach`
- **AND** no conservation warning is emitted

#### Scenario: Mismatch detected
- **WHEN** simulated total reach differs from allocated/log total
- **THEN** summary includes explicit mismatch value
- **AND** marks conservation status as failed for the run

### Requirement: Feedback Pricing Diagnostics in Summary
The system SHALL report feedback-pricing diagnostics to explain utilization behavior per run.

#### Scenario: Summary includes multiplier statistics
- **WHEN** feedback pricing is enabled
- **THEN** summary includes multiplier min/max/mean over the run
- **AND** includes count of updates where multiplier hit configured min/max bounds

#### Scenario: Summary includes spend trajectory diagnostics
- **WHEN** feedback pricing is enabled
- **THEN** summary includes target vs actual cumulative spend error at end of run
- **AND** includes per-category under-spend/over-spend flags

