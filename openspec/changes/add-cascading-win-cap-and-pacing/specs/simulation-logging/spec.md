## ADDED Requirements

### Requirement: Cascade Decision Logging
The system SHALL log cascade decisions per category/hour including under-spend ratio, `win_per_ad_cap`, and pacing tolerance applied.

#### Scenario: Cascade log emitted
- **WHEN** an hour starts for a category
- **THEN** a log entry includes `under_spend_ratio`, `win_per_ad_cap`, and `pacing_tolerance`
