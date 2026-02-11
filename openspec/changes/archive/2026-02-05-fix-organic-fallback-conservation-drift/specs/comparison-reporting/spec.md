## ADDED Requirements
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
