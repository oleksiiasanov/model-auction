## ADDED Requirements
### Requirement: Strict Category-Safe Budget Extraction
The system SHALL extract budget records only for the requested categories and exclude null/invalid category rows to prevent out-of-scope paid ads from entering simulation.

#### Scenario: Exclude out-of-scope categories
- **WHEN** simulation runs with `categories=[1361]`
- **AND** `spendings_distributed` contains budget rows for categories outside 1361
- **THEN** those rows are excluded from extracted budgets
- **AND** excluded rows are not counted in simulation budget totals

#### Scenario: Exclude null or zero category artifacts
- **WHEN** source data contains budget rows with `category_id IS NULL` or `category_id=0`
- **THEN** these rows are excluded from extracted budgets for category-scoped simulation
- **AND** they do not create paid ads with missing category in reports

### Requirement: Budget Records Carry Category Context
The system SHALL preserve category context for each extracted budget record so budget-only ads can be initialized in the correct category.

#### Scenario: Budget-only ad gets category assignment
- **WHEN** an ad has budget for selected category and no impressions in period
- **THEN** extracted budgets include `(ad_id, seller_id, category_id, date, daily_budget, actual_spend)`
- **AND** simulation can initialize that ad in the selected category

### Requirement: Budget Eligibility Is Not Gated by Impression Presence
The system SHALL include in-scope budget rows even when the same ad has zero impression rows in the selected period.

#### Scenario: In-scope budget row without impressions is kept
- **WHEN** an ad has `daily_budget > 0` for selected category/date
- **AND** the ad has no matching rows in `enriched_distributed` during that period
- **THEN** the budget row is still extracted
- **AND** the ad can be initialized as budget-only (cold-start) for paid auction participation
