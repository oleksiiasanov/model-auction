## ADDED Requirements

### Requirement: Correct Metric Terminology in Summary Statistics

The system SHALL use correct terminology to distinguish between reach, impressions, and unique users in all reports and output.

#### Scenario: Summary statistics shows all three metrics

- **WHEN** generating summary statistics
- **THEN** output SHALL include three distinct metrics:
  1. **Unique Users (globally)**: COUNT(DISTINCT user_id) across all data (estimated if user_id not tracked)
  2. **Total Reach**: SUM(COUNT(DISTINCT user_id) GROUP BY ad_id, date) - user × ad × date combinations
  3. **Raw Impressions**: COUNT(*) - all views including repeats
- **RATIONALE**: These are fundamentally different metrics that cannot be compared directly
- **EXAMPLE OUTPUT**:
  ```
  Unique Users (globally):
    Estimated: ~3,458 (from reach / avg combinations)

  Total Reach (user × ad × date combinations):
    Actual:    233,806
    Simulated: 233,806
    Diff:      0

  Raw Impressions (all views):
    Actual:    583,065
    Note: Simulation works with reach, not raw impressions
  ```

#### Scenario: Metric labels match SQL queries

- **WHEN** user reads "Total Reach: 233,806" in summary statistics
- **THEN** user can verify with SQL:
  ```sql
  -- Method 1: Sum of reach records
  SELECT SUM(cnt) FROM (
      SELECT COUNT(DISTINCT user_id) as cnt
      FROM enriched_distributed
      WHERE ...
      GROUP BY ad_id, toDate(timestamp)
  )
  -- Result: 233,806 ✅
  ```
- **RATIONALE**: Labels must match what users naturally query in database

#### Scenario: Raw impressions shown separately

- **WHEN** user reads "Raw Impressions: 583,065" in summary statistics
- **THEN** user can verify with SQL:
  ```sql
  SELECT COUNT(*) FROM enriched_distributed WHERE ...
  -- Result: 583,065 ✅
  ```
- **PREVIOUS**: Raw impressions were not shown at all
- **IMPACT**: Users can now verify impression counts directly

#### Scenario: Unique users estimation explained

- **WHEN** exact unique user count is not available (user_id not stored per record)
- **THEN** show estimated value with formula:
  ```
  Unique Users (globally):
    Estimated: ~3,458
    Formula: total_reach / avg_combinations_per_user
    Note: Exact count requires tracking user_id list (not implemented)
  ```
- **RATIONALE**: Transparent about limitations, users know it's estimated

#### Scenario: Ratios provide context

- **WHEN** showing multiple metrics
- **THEN** include ratio calculations:
  ```
  Metrics Ratios:
    Impressions per reach: 2.49x (each user×ad combination viewed 2.5 times avg)
    Reach per unique user: ~68 (each user saw 68 different ad×day combinations)
  ```
- **RATIONALE**: Helps users understand relationships between metrics

## MODIFIED Requirements

### Requirement: Summary Statistics Output Format

The system SHALL generate summary statistics with **correct metric names and clear explanations**, distinguishing reach from impressions.

#### Scenario: Summary file header includes metric definitions

- **WHEN** generating summary statistics file
- **THEN** include header with definitions:
  ```
  Generated: 2026-02-02T14:35:18
  Time Range: 2026-01-31 to 2026-02-01

  METRIC DEFINITIONS:
  - Unique Users: COUNT(DISTINCT user_id) globally (estimated)
  - Reach: COUNT(DISTINCT user_id) per ad per day, then summed
  - Impressions: COUNT(*) - all views including repeats within same user×ad×day

  ================================================================================
  SIMULATION SUMMARY STATISTICS
  ================================================================================
  ```
- **PREVIOUS**: No header, no metric definitions
- **IMPACT**: Self-documenting reports, users understand what they're reading

#### Scenario: Paid/organic metrics use reach terminology

- **WHEN** showing paid vs organic breakdown
- **THEN** use "Paid Reach" and "Organic Reach", not "Paid Impressions":
  ```
  Paid Reach:
    Actual:    96,014
    Simulated: 109,353
    Change:    +13,339 (+13.9%)

  Organic Reach:
    Actual:    137,792
    Simulated: 124,453
    Change:    -13,339 (-9.7%)
  ```
- **PREVIOUS**: Called these "Paid Impressions" and "Free Impressions"
- **CONSISTENCY**: Matches terminology used throughout system

#### Scenario: Conclusion uses correct terminology

- **WHEN** generating conclusion summary
- **THEN** use "reach" not "impressions":
  ```
  Conclusion:
    Simulation INCREASED paid reach by 13,339 (13.9%)
    Simulation DECREASED organic reach by 13,339 (9.7%)
  ```
- **PREVIOUS**: "Simulation INCREASED paid impressions by ..."
- **ACCURACY**: Reflects what was actually measured (reach, not raw impressions)

## ADDED Requirements

### Requirement: Terminology Consistency Across Reports

The system SHALL use consistent terminology (reach vs impressions) across all report types: summary statistics, CSV exports, and logs.

#### Scenario: CSV column headers use reach terminology

- **WHEN** generating ad_comparison_*.csv or seller_comparison_*.csv
- **THEN** column names SHALL be:
  - `total_reach_actual`
  - `total_reach_simulated`
  - `organic_reach_actual`
  - `paid_reach_simulated`
- **PREVIOUS**: Mixed terminology (sometimes "impressions", sometimes "reach")
- **CONSISTENCY**: All reports use same metric names

#### Scenario: Simulation logs use reach terminology

- **WHEN** logging simulation progress
- **THEN** use "reach" in log messages:
  ```
  Initialized 8407 ads
  Reset budgets for 2026-01-31: 141 ads with budget
  Simulating reach allocation for category 1361, hour 0
  Total reach allocated: 5,500
  ```
- **PREVIOUS**: "Simulating impressions", "Total impressions allocated"
- **CONSISTENCY**: Logs match spec and summary statistics

#### Scenario: Error messages use correct terminology

- **WHEN** validation fails or errors occur
- **THEN** error messages use correct terms:
  ```
  ❌ Reach conservation check failed: allocated 5,500 reach but expected 5,265
  ✅ Reach conservation verified: 5,265 = 5,265
  ```
- **CLARITY**: Users know what metric failed validation
