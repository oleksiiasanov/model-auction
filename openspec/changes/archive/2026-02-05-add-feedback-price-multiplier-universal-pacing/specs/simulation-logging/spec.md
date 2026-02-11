## ADDED Requirements
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
