# reporting-enhancements Specification

## Purpose
TBD - created by archiving change add-detailed-logging-and-paid-flags. Update Purpose after archive.
## Requirements
### Requirement: Paid Status Classification for Sellers

The system SHALL include paid status flags in seller-level comparison reports to distinguish paying sellers from non-paying sellers in both actual and simulated data.

#### Scenario: Seller with paid campaigns in actual data

- **WHEN** seller has at least one ad with `daily_budget > 0` in `budgets_df` for any day in simulation period
- **THEN** `is_paid_actual = true` in seller comparison report

#### Scenario: Seller with no paid campaigns in actual data

- **WHEN** seller has no ads with `daily_budget > 0` in `budgets_df` (all ads organic)
- **THEN** `is_paid_actual = false` in seller comparison report

#### Scenario: Seller spent budget in simulation

- **WHEN** seller's `simulated_spending > 0` in simulation results
- **THEN** `is_paid_simulated = true` in seller comparison report

#### Scenario: Seller did not spend in simulation

- **WHEN** seller's `simulated_spending = 0` in simulation results
- **THEN** `is_paid_simulated = false` in seller comparison report

#### Scenario: Seller status change - became paid

- **WHEN** seller has `is_paid_actual = false` AND `is_paid_simulated = true`
- **THEN** indicates seller became paying customer in simulation (edge case: had budget but didn't spend historically)

#### Scenario: Seller status change - lost paid status

- **WHEN** seller has `is_paid_actual = true` AND `is_paid_simulated = false`
- **THEN** indicates seller had budget historically but exhausted it early or was paused by pacing in simulation

### Requirement: Paid Status Classification for Ads

The system SHALL include paid status flags in ad-level comparison reports to distinguish paid ads from organic ads in both actual and simulated data.

#### Scenario: Ad with paid campaign in actual data

- **WHEN** ad has `daily_budget > 0` in `budgets_df` for at least one day in simulation period
- **THEN** `is_paid_actual = true` in ad comparison report

#### Scenario: Ad with no paid campaign in actual data

- **WHEN** ad has `daily_budget = 0` or no campaign record in `budgets_df` for all days
- **THEN** `is_paid_actual = false` in ad comparison report

#### Scenario: Ad spent budget in simulation

- **WHEN** ad's `simulated_spending > 0` in simulation results
- **THEN** `is_paid_simulated = true` in ad comparison report

#### Scenario: Ad did not spend in simulation

- **WHEN** ad's `simulated_spending = 0` in simulation results
- **THEN** `is_paid_simulated = false` in ad comparison report

#### Scenario: Ad status change detection

- **WHEN** ad has different values for `is_paid_actual` and `is_paid_simulated`
- **THEN** indicates ad changed paid/organic status between actual and simulation
- **EXAMPLE**: `is_paid_actual=true, is_paid_simulated=false` means ad had budget but exhausted it early in simulation

### Requirement: CSV Column Placement

The system SHALL place paid status columns immediately after ID columns for easy visibility.

#### Scenario: Seller comparison CSV column order

- **WHEN** generating `seller_comparison_*.csv`
- **THEN** column order is:
  1. `seller_id`
  2. `is_paid_actual`
  3. `is_paid_simulated`
  4. `actual_impressions_total`
  5. `actual_impressions_paid`
  6. `actual_impressions_organic`
  7. ... (remaining columns)

#### Scenario: Ad comparison CSV column order

- **WHEN** generating `ad_comparison_*.csv`
- **THEN** column order is:
  1. `ad_id`
  2. `seller_id`
  3. `category_id`
  4. `is_paid_actual`
  5. `is_paid_simulated`
  6. `actual_impressions_total`
  7. `actual_impressions_paid`
  8. `actual_impressions_organic`
  9. ... (remaining columns)

### Requirement: Boolean Data Type in CSV

The system SHALL represent paid status flags as boolean values in CSV using lowercase strings.

#### Scenario: True value representation

- **WHEN** paid status flag is `True` (Python boolean)
- **THEN** CSV contains `"true"` (lowercase string)

#### Scenario: False value representation

- **WHEN** paid status flag is `False` (Python boolean)
- **THEN** CSV contains `"false"` (lowercase string)

#### Scenario: Null handling

- **WHEN** paid status cannot be determined (missing data)
- **THEN** CSV contains `"false"` (default to non-paid)
- **AND** log warning about missing data

### Requirement: Paid Status Calculation Logic

The system SHALL calculate paid status flags using aggregation over budgets DataFrame.

#### Scenario: Calculate seller is_paid_actual

- **WHEN** building seller comparison report
- **THEN** for each seller:
  1. Get all ads belonging to seller from `budgets_df`
  2. Check if `MAX(daily_budget) > 0` across all ads and all days
  3. Set `is_paid_actual = true` if condition met, else `false`

#### Scenario: Calculate ad is_paid_actual

- **WHEN** building ad comparison report
- **THEN** for each ad:
  1. Get all budget records for ad from `budgets_df`
  2. Check if `MAX(daily_budget) > 0` across all days
  3. Set `is_paid_actual = true` if condition met, else `false`

#### Scenario: Calculate seller is_paid_simulated

- **WHEN** building seller comparison report
- **THEN** for each seller:
  1. Get `simulated_spending` from aggregated simulation results
  2. Set `is_paid_simulated = true` if `simulated_spending > 0`, else `false`

#### Scenario: Calculate ad is_paid_simulated

- **WHEN** building ad comparison report
- **THEN** for each ad:
  1. Get `simulated_spending` from simulation results
  2. Set `is_paid_simulated = true` if `simulated_spending > 0`, else `false`

### Requirement: Metadata Documentation in CSV Headers

The system SHALL document paid status flags in CSV metadata comments.

#### Scenario: CSV metadata header for seller comparison

- **WHEN** generating `seller_comparison_*.csv`
- **THEN** metadata header includes:
  ```
  # Columns:
  #   is_paid_actual: TRUE if seller had paid campaigns in actual data (daily_budget > 0)
  #   is_paid_simulated: TRUE if seller spent any budget in simulation (simulated_spending > 0)
  ```

#### Scenario: CSV metadata header for ad comparison

- **WHEN** generating `ad_comparison_*.csv`
- **THEN** metadata header includes:
  ```
  # Columns:
  #   is_paid_actual: TRUE if ad had paid campaign in actual data (daily_budget > 0 on any day)
  #   is_paid_simulated: TRUE if ad spent any budget in simulation (simulated_spending > 0)
  ```

### Requirement: Filtering and Analysis Support

The system SHALL enable easy filtering of reports by paid status.

#### Scenario: Filter paid sellers only

- **WHEN** user loads `seller_comparison_*.csv` with pandas
- **THEN** can filter: `df[df['is_paid_actual'] == True]`
- **AND** get only sellers who had paid campaigns in actual data

#### Scenario: Identify status changes

- **WHEN** user wants to find sellers who changed paid status
- **THEN** can filter:
  - Newly paid: `df[(df['is_paid_actual'] == False) & (df['is_paid_simulated'] == True)]`
  - Lost paid: `df[(df['is_paid_actual'] == True) & (df['is_paid_simulated'] == False)]`

#### Scenario: Segment analysis by paid status

- **WHEN** user wants to compare paid vs organic performance
- **THEN** can group by `is_paid_actual` and calculate metrics:
  ```python
  df.groupby('is_paid_actual').agg({
      'actual_impressions_total': 'sum',
      'simulated_impressions_total': 'sum',
      'diff_impressions_total': 'sum'
  })
  ```

### Requirement: Accurate Reach Distribution Calculation in Summary Statistics

The system SHALL calculate paid vs organic reach distribution using correct column aggregation to ensure consistency and conservation laws.

#### Scenario: Use actual_reach_paid column for paid reach aggregation

- **WHEN** calculating "Paid Reach: Actual" in Reach Distribution Analysis section
- **THEN** system SHALL use `ad_comparison['actual_reach_paid'].sum()`
- **AND NOT** filter by `actual_reach_paid > 0` and sum `actual_reach_total`
- **RATIONALE**: `actual_reach_total` includes both paid AND organic reach; filtering + summing total double-counts organic portion for ads with both types

#### Scenario: Use actual_reach_organic column for organic reach aggregation

- **WHEN** calculating "Organic Reach: Actual" in Reach Distribution Analysis section
- **THEN** system SHALL use `ad_comparison['actual_reach_organic'].sum()`
- **AND NOT** filter by `actual_reach_paid == 0` and sum `actual_reach_total`
- **RATIONALE**: Ensures symmetry with paid calculation and avoids classification errors

#### Scenario: Conservation law validation

- **WHEN** calculating reach distribution totals
- **THEN** system SHALL validate: `paid_reach_actual + organic_reach_actual == total_reach_actual`
- **TOLERANCE**: 0 (exact equality, no rounding)
- **PURPOSE**: Catch calculation errors before displaying results
- **EXAMPLE**:
  - `paid_reach_actual = 81,152`
  - `organic_reach_actual = 152,654`
  - `total_reach_actual = 233,806`
  - Validation: `81,152 + 152,654 = 233,806` ✓

#### Scenario: Consistency between summary sections

- **WHEN** summary statistics contains multiple sections showing paid reach
- **THEN** all sections SHALL show identical "Paid Reach: Actual" value
- **CROSS-REFERENCE**:
  - "Paid Reach" section (line ~34)
  - "Reach Distribution Analysis" section (line ~68)
- **VALIDATION**: Both must show same value sourced from `ad_comparison['actual_reach_paid'].sum()`

#### Scenario: CSV data matches summary statistics

- **WHEN** comparing CSV output with summary statistics
- **THEN** `ad_comparison_*.csv` column sums SHALL exactly match summary values:
  - `SUM(actual_reach_paid)` = "Paid Reach: Actual"
  - `SUM(actual_reach_organic)` = "Organic Reach: Actual"
  - `SUM(actual_reach_total)` = "Total Reach: Actual"
- **PURPOSE**: Enable independent verification via CSV inspection

#### Scenario: Handle edge case - ad with only organic reach

- **WHEN** ad has `actual_reach_paid = 0` and `actual_reach_organic > 0`
- **THEN** ad SHALL contribute to organic total only
- **AND** NOT be excluded from calculations
- **EXAMPLE**: Ad with 50 organic reach contributes 50 to `organic_reach_actual`, 0 to `paid_reach_actual`

#### Scenario: Handle edge case - ad with only paid reach

- **WHEN** ad has `actual_reach_paid > 0` and `actual_reach_organic = 0`
- **THEN** ad SHALL contribute to paid total only
- **EXAMPLE**: Ad with 100 paid reach contributes 100 to `paid_reach_actual`, 0 to `organic_reach_actual`

#### Scenario: Handle edge case - ad with both paid and organic reach

- **WHEN** ad has `actual_reach_paid > 0` AND `actual_reach_organic > 0`
- **THEN** ad SHALL contribute to BOTH totals separately
- **AND** `actual_reach_total = actual_reach_paid + actual_reach_organic` for that ad
- **EXAMPLE**:
  - Ad: `paid=81`, `organic=100`, `total=181`
  - Contributes: 81 to paid total, 100 to organic total
  - NOT: 181 to paid total (previous bug)

