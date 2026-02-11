## ADDED Requirements
### Requirement: Feedback Price Multiplier Control
The system SHALL maintain a feedback-controlled `price_multiplier` per category/day to adapt paid pricing toward a target spend trajectory.

#### Scenario: Deficit increases multiplier within bounds
- **WHEN** cumulative simulated spend is below target trajectory at update time
- **THEN** controller increases `price_multiplier`
- **AND** resulting value is clamped to configured bounds

#### Scenario: Surplus decreases multiplier within bounds
- **WHEN** cumulative simulated spend is above target trajectory at update time
- **THEN** controller decreases `price_multiplier`
- **AND** resulting value is clamped to configured bounds

#### Scenario: Controller state resets daily
- **WHEN** simulation starts a new day for a category
- **THEN** controller integral and multiplier state reset to configured initial values

### Requirement: Multiplier-Aware Effective Bid
The system SHALL apply feedback `price_multiplier` to paid effective bid calculation while preserving ranking determinism.

#### Scenario: Paid effective bid scaled by multiplier
- **WHEN** `base_effective_bid` is computed for a paid winner
- **THEN** charged bid basis uses `base_effective_bid * price_multiplier`
- **AND** winner ordering remains deterministic from rank logic

#### Scenario: Budget safety remains enforced
- **WHEN** scaled cost exceeds remaining budget
- **THEN** charged amount is capped at remaining budget
- **AND** no overspend occurs
