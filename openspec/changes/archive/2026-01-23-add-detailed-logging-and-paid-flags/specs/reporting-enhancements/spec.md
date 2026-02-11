# Reporting Enhancements Spec

## ADDED Requirements

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

## MODIFIED Requirements

None. This is an additive change with no modifications to existing requirements.

## REMOVED Requirements

None. All existing functionality is preserved.
