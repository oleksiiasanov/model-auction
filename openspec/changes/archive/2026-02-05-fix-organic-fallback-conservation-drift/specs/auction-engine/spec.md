## ADDED Requirements
### Requirement: Exact Conservation in Cumulative Organic Allocation
The system SHALL guarantee exact slot conservation for each cumulative organic fallback event.

#### Scenario: Per-event conservation holds
- **WHEN** fallback is called with `remaining_slots = N`
- **THEN** sum of all allocated slots equals exactly `N`
- **AND** event-level conservation check reports valid

#### Scenario: Residual allocation preserves debt semantics
- **WHEN** residual slots are assigned to ads by carry ranking
- **THEN** each assigned residual slot decrements winner carry by `1.0`
- **AND** carry is allowed to become negative to represent debt
- **AND** no carry clamping to zero is applied in this step

#### Scenario: Multi-batch cumulative allocation has zero drift
- **WHEN** many fallback batches execute sequentially
- **THEN** cumulative allocated slots equal cumulative requested slots exactly
- **AND** no systematic positive or negative drift is introduced
