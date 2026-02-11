## ADDED Requirements

### Requirement: Cascading Win Cap
The system SHALL compute a per-category, per-hour `win_per_ad_cap` based on under-spend ratio and apply it during batch winner selection.

#### Scenario: Under-spend triggers higher cap
- **WHEN** cumulative spend / target spend falls below the configured threshold for the hour
- **THEN** `win_per_ad_cap` is increased up to a maximum of 4

#### Scenario: On-target spend keeps cap at baseline
- **WHEN** cumulative spend / target spend is at or above the configured threshold
- **THEN** `win_per_ad_cap` remains at 1

### Requirement: Pacing Relaxation Fallback
The system SHALL relax pacing only after 2 consecutive hours of under-spend for a category.

#### Scenario: Under-spend streak triggers pacing relaxation
- **WHEN** under-spend persists for 2 consecutive hours
- **THEN** pacing gate tolerance is increased by the configured increment for that category/hour

#### Scenario: No streak keeps pacing unchanged
- **WHEN** under-spend streak is less than 2 hours
- **THEN** pacing gate tolerance remains at its configured baseline
