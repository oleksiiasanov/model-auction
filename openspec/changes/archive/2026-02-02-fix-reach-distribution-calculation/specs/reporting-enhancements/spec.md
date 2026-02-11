# reporting-enhancements Spec Delta

**Change ID**: `fix-reach-distribution-calculation`

## ADDED Requirements

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
