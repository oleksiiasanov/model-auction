## Context
The simulator must handle thousands of categories with very different traffic and paid participation regimes. Static parameters (especially fixed `bid_step`) are not portable enough:
- Low-paid categories can under-spend even with full eligibility.
- High-paid categories can exhaust quickly and distort distribution.

Existing controls are necessary but insufficient:
- `pressure` decides rank priority.
- pacing gate prevents over-fast spending.
Neither introduces adaptive price scaling to meet spend trajectory targets.

## Goals / Non-Goals
- Goals:
  - Provide universal, category-agnostic spend control.
  - Maintain budget safety and reach conservation invariants.
  - Minimize manual tuning across categories.
  - Keep deterministic behavior and traceability.
- Non-Goals:
  - No ML policy or black-box optimizer.
  - No user-level engagement prediction.
  - No change to organic fallback math in this proposal.

## Decisions
- Decision: Add PI-style feedback controller per `category_id x date`
  - State: `price_multiplier`, cumulative error integral.
  - Update cadence: hourly (configurable).
  - Update source: cumulative spend gap vs target path.

- Decision: Apply multiplier to bid pricing only
  - Preserve ranking from pressure logic.
  - Preserve winner selection mechanics.

- Decision: Add strict guardrails
  - `multiplier_min <= price_multiplier <= multiplier_max`
  - max step change per update (`delta_limit`)
  - optional EMA smoothing.

## Control Model
Definitions per category/day:
- `B` = total daily paid budget
- `S_t` = cumulative simulated spend by hour `t`
- `T_t` = target cumulative spend by hour `t`
- `e_t = T_t - S_t`

Target curve (default):
- linear: `T_t = B * time_progress_t`
- extensible: configurable shape (front/neutral/back loaded)

Controller update (hourly):
- `I_t = clip(I_{t-1} + e_t, I_min, I_max)`
- `u_t = Kp * e_t + Ki * I_t`
- `multiplier_t = clip(multiplier_{t-1} * exp(u_t), m_min, m_max)`
- optional smoothing:
  - `multiplier_t = alpha * multiplier_t + (1-alpha) * multiplier_{t-1}`

Pricing:
- `effective_bid = base_effective_bid * multiplier_t`

## Risks / Trade-offs
- Risk: oscillation from aggressive gains.
  - Mitigation: conservative defaults, delta limit, smoothing, bounded integrator.
- Risk: low-liquidity category still cannot fully spend.
  - Mitigation: explicitly report saturation (controller at max multiplier + unmet spend).
- Risk: interaction with pacing gate and cap charging.
  - Mitigation: evaluate jointly in regression suite.

## Validation Plan
- Unit tests:
  - multiplier boundedness
  - monotonic corrective response to deficit/surplus
  - no overspend invariant with capped charging
- Integration tests:
  - sparse-paid category (N small)
  - dense-paid category (N large)
  - mixed category with changing N intra-day
- Acceptance metrics:
  - utilization variance across categories decreases
  - under-spend tail reduces without conservation violations
  - no budget overspend

## Open Questions
- Default gains (`Kp`, `Ki`) and smoothing (`alpha`) values.
- Preferred default target curve: linear vs mildly back-loaded.
