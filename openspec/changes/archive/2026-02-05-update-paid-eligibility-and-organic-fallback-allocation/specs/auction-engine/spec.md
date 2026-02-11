## ADDED Requirements
### Requirement: Budget-Driven Paid Eligibility
The system SHALL include all in-scope ads with positive budget in paid auction eligibility, even if they have zero historical reach in the simulation period.

#### Scenario: Budget-only ad participates in paid auction
- **WHEN** an ad has `daily_budget > 0` for selected category/date and no historical reach records
- **THEN** the ad is initialized in simulation state as a cold-start paid participant
- **AND** the ad can compete in paid auction batches using standard pressure/ranking logic

#### Scenario: Paid coverage includes budget-only participants
- **WHEN** simulation finishes for a day
- **THEN** paid reach coverage metrics include budget-only ads that won at least one paid slot
- **AND** budget-only ads are not silently excluded due to missing impressions history

### Requirement: Cumulative Organic Fallback Allocation
The system SHALL allocate organic fallback using cumulative proportional carry-over across batches to prevent long-tail starvation.

#### Scenario: Fractional shares persist across batches
- **WHEN** organic fallback runs in many small batches (e.g., 1-40 slots)
- **THEN** fractional allocation remainder for each ad carries into future batches
- **AND** ads with small proportions eventually receive slots according to cumulative share

#### Scenario: Conservation remains exact with cumulative allocation
- **WHEN** fallback allocates `remaining_slots = N` in a batch
- **THEN** the sum of all allocated fallback slots equals exactly `N`
- **AND** deterministic tie-breaking is applied for residual slot assignment

### Requirement: Configurable Organic Pool Split
The system SHALL support configurable fallback split between paid-exhausted ads and free ads.

#### Scenario: Apply configured split per fallback event
- **WHEN** `free_share=0.8` and fallback event has `remaining_slots=25`
- **THEN** system allocates 20 slots to free pool and 5 slots to paid-exhausted pool (after rounding rules)
- **AND** each pool is allocated proportionally using cumulative carry-over

#### Scenario: Split disabled uses single-pool allocation
- **WHEN** split feature is disabled
- **THEN** fallback uses one pool of all eligible organic recipients
- **AND** cumulative allocator still applies

#### Scenario: Reassign split slots when one pool is empty
- **WHEN** fallback event computes pool split but one pool has zero eligible ads
- **THEN** all slots for the empty pool are reassigned to the non-empty pool in the same event
- **AND** total allocated slots still equal `remaining_slots` exactly

### Requirement: Budget-Safe Charging
The system SHALL never charge more than the remaining budget for any winning ad.

#### Scenario: Winner cost exceeds remaining budget
- **WHEN** ad wins with `effective_bid > remaining_budget`
- **THEN** charged amount is capped at `remaining_budget`
- **AND** remaining budget becomes exactly zero
- **AND** no negative remaining budget is possible

#### Scenario: Total simulated spend never exceeds total budget
- **WHEN** simulation completes
- **THEN** for each paid ad and globally, `simulated_spending <= assigned_budget` holds
