## ADDED Requirements
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
