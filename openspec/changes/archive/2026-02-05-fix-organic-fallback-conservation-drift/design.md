## Context
The cumulative organic allocator maintains fractional carry per ad across batches. In current implementation, residual slot assignment can reset/clip carry in a way that loses debt semantics, producing positive drift over time.

Observed symptoms:
- Run-level simulated reach exceeds actual/target by drift value.
- Multiple fallback events fail conservation checks with over-allocation.

## Goals / Non-Goals
- Goals:
  - Guarantee exact conservation per fallback event.
  - Guarantee exact conservation across full run.
  - Preserve deterministic tie-breaking.
- Non-Goals:
  - No policy changes to paid/free split in this change.
  - No pricing/pacing control changes.

## Decisions
- Decision: Residual allocation must consume carry as debt-capable state
  - On residual grant, carry is decremented by 1.0 and allowed to become negative.
  - Rationale: if ad receives a slot before accumulating full carry, debt must be represented.

- Decision: Keep deterministic ordering
  - Residual winners sorted by carry desc, tie-break ad_id asc.

- Decision: Add reconciliation checks
  - Per-event: `sum(allocations) == remaining_slots`.
  - Run-level: summary total simulated reach equals allocated/log total.

## Algorithm Update
For each pool allocation event:
1. `carry_i += slots * proportion_i`
2. `base_i = floor(carry_i)`
3. `carry_i -= base_i`
4. `residual = slots - sum(base_i)`
5. Assign residual slots by highest carry
6. For each residual winner: `carry_i -= 1.0` (NO clamp)

Conservation follows because each residual slot maps to one explicit carry decrement.

## Risks / Trade-offs
- Risk: Negative carry values may look unusual in debug logs.
  - Mitigation: document as expected debt state.
- Risk: Existing ad-level distribution changes slightly after fix.
  - Mitigation: expected and correct; conservation has higher priority.

## Validation Plan
- Unit tests:
  - residual allocation with small slots over many batches has zero drift.
  - negative carry appears when expected and recovers over subsequent batches.
- Integration checks:
  - no `conservation_check.valid=false` events.
  - `simulated_total_reach == actual_total_reach` for fixed-volume runs.
