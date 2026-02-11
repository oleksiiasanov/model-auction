# reach-profile-simulator Specification

## Purpose
TBD - created by archiving change add-auction-simulator. Update Purpose after archive.
## Requirements
### Requirement: All Ads Always Eligible (MVP Simplification)
The system SHALL treat all ads from all sellers as always eligible for auction participation. No hourly rotation or Reach Profile windowing is implemented in MVP.

#### Scenario: All seller ads participate
- **WHEN** a seller has 100 ads for a category
- **THEN** all 100 ads are eligible to participate in every auction, subject only to budget and pacing constraints

#### Scenario: No rotation tracking needed
- **WHEN** simulation runs
- **THEN** no ad rotation logic is applied, no rotation seeds or hourly windows are calculated

#### Scenario: Future extension point
- **WHEN** Reach Profile rotation is needed in future iterations
- **THEN** this spec can be extended with hourly rotation requirements without changing core auction logic

