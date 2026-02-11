## Context
Budget utilization is constrained by a per-batch single-win limit and pacing gate. Dynamic pricing alone does not increase spend if paid inventory is small.

## Goals / Non-Goals
- Goals:
  - Increase paid spend by allowing multiple wins per ad when under-spending.
  - Only relax pacing after sustained under-spend (2 hours).
  - Keep logic deterministic and bounded.
- Non-Goals:
  - Redesign of auction ranking or bid formula.
  - Per-user modeling or exploration systems.

## Decisions
- Decision: Evaluate cascade at hour granularity per category.
  - Rationale: aligns with current hourly simulation loop and controller cadence.
- Decision: Use `under_spend_ratio = cumulative_spend / target_spend` with target curve from existing feedback controller.
  - Rationale: consistent with pacing target and avoids new calibration.
- Decision: Primary lever is `win_per_ad_cap` (max 4), secondary lever is pacing relaxation after 2 consecutive under-spend hours.

## Risks / Trade-offs
- Risk: Higher win cap can reduce diversity in a batch.
  - Mitigation: clamp cap to `max_win_per_ad_cap` and only increase when under-spend persists.
- Risk: Relaxed pacing could overspend late day.
  - Mitigation: relax only after 2 consecutive hours and clamp tolerance.

## Migration Plan
1. Add config defaults (win cap thresholds, pacing relax thresholds).
2. Implement hourly cascade evaluation and logging.
3. Run simulation and verify spend increase without overspend.

## Open Questions
- Confirm exact thresholds for cap steps and pacing tolerance increments.
