## Context
The simulator is used to evaluate a replacement auction algorithm, not to replicate historical distribution exactly. Current implementation over-concentrates paid and organic allocation among a small subset of ads due to eligibility and fallback math constraints.

Observed from latest runs:
- `paid ads with reach`: 141/151
- `paid sellers with reach`: 96/101
- `free ads with reach`: 5/8266
- `reported budget utilization`: ~94.4%

## Goals / Non-Goals
- Goals:
  - Ensure all budgeted ads in selected scope can participate in paid auction (including cold-start ads).
  - Preserve strict category/country correctness of budget input set.
  - Preserve total reach conservation while reducing fallback starvation of long-tail ads.
  - Enforce hard budget invariant: simulated spend never exceeds assigned budget.
  - Provide reporting that separates active utilization from total budget utilization.
  - Ensure summary-level metrics match simulation allocations (no reporting-only conservation drift).
- Non-Goals:
  - No attempt to match historical paid/organic split exactly.
  - No introduction of user-level behavioral model.
  - No dynamic bid-step optimization in this change.

## Decisions
- Decision: Initialize simulation ad state from union(impressions ads, budgets ads)
  - Why: paid eligibility must be budget-driven for replacement-auction evaluation.
  - Consequence: budgeted ads without historical reach become cold-start participants with zero historical reach weight.

- Decision: Apply strict budget extraction filters
  - Why: prevent category leakage and category_id=0/null artifacts from entering paid denominator.
  - Consequence: cleaner paid budget denominator and participant set.
  - Additional: remove requirement that budget rows must appear in impressions subquery, because that blocks budget-driven participation.

- Decision: Replace per-batch fallback with cumulative allocator
  - Why: per-batch floor/remainder resets fractional shares and starves long-tail ads.
  - Consequence: allocation fairness improves across many small fallback batches while preserving deterministic conservation.

- Decision: Add configurable organic pool split
  - Why: gives explicit control over organic allocation policy between paid-exhausted and free ads.
  - Consequence: business can tune policy (e.g., 20/80, 15/85, 25/75) without code change.

- Decision: Preserve per-event conservation under split edge cases
  - Why: if one pool is empty, fixed slot split can silently drop slots.
  - Consequence: reassign unused slots to non-empty pool in the same event before final allocation.

- Decision: Make reporting period-aware and entity-deduplicated
  - Why: day-end state and outer-merge duplicates can distort paid coverage and total simulated reach in summary.
  - Consequence: period-level paid flags and ad-entity dedup are required before aggregate summary computation.

## Algorithm Notes
### Budget-driven paid eligibility
- Build ad dictionary from:
  - impressions tuples `(ad_id, seller_id, category_id)`
  - budgets tuples `(ad_id, seller_id, category_id)`
- For budget-only ads:
  - `total_reach_historical = 0`
  - `raw_impressions_historical = 0`
  - `source = budget_only` (for debug/reporting only)

### Cumulative organic allocator
For each pool (paid-exhausted and free):
1. Keep per-ad `carry[ad_id]` across fallback batches.
2. For batch with `slots` and per-ad weight `p_i`:
   - `carry_i += slots * p_i`
   - `base_i = floor(carry_i)`
   - allocate `base_i`
   - `carry_i -= base_i`
3. If residual slots remain due to numerical edge cases, assign by highest `carry_i`, tie-break `ad_id` asc.
4. Reset carry state at day boundary.

### Pool split
- Config:
  - `organic_fallback.free_share` (0..1)
  - `organic_fallback.paid_exhausted_share = 1 - free_share`
- Apply split per fallback event:
  - `free_slots = round(remaining_slots * free_share)`
  - `paid_exhausted_slots = remaining_slots - free_slots`
- If one pool is empty:
  - reassign all slots to the non-empty pool
  - keep conservation: `free_allocated + paid_exhausted_allocated == remaining_slots`

### Budget-safe charging
- For each paid winner:
  - `charged = min(effective_bid * reach_won, remaining_budget_before_charge)`
  - `remaining_budget_after = remaining_budget_before_charge - charged`
- Invariant:
  - `remaining_budget_after >= 0`
  - cumulative `simulated_spending <= cumulative assigned budget`

## Risks / Trade-offs
- Risk: budget-driven eligibility may include ads not truly display-eligible in production.
  - Mitigation: if moderation/visibility flags become available, add hard eligibility filter in extraction.
- Risk: larger free coverage may reduce paid-exhausted organic allocations.
  - Mitigation: share split is configurable and can be tuned by simulation goals.
- Risk: cumulative allocator complexity vs current simple floor/remainder.
  - Mitigation: deterministic implementation, strict conservation assertions, dedicated tests.
- Risk: budget-driven eligibility may increase participant count and lower per-ad paid wins.
  - Mitigation: tune split share and pacing separately; keep paid coverage KPI visible in reports.
- Risk: reporting logic changes can invalidate historical dashboards if semantics are changed silently.
  - Mitigation: explicitly label new metrics and document denominator definitions in summary text.

## Validation Plan
- Unit tests:
  - union ad initialization includes budget-only ads.
  - strict extraction excludes category_id null/0 and out-of-scope categories.
  - strict extraction does not require impression presence for budget inclusion in selected scope.
  - cumulative allocator preserves exact conservation across variable batch sizes.
  - split allocator reassigns slots when one pool is empty.
  - charging logic never overspends budget (spend <= budget).
  - cumulative allocator increases non-zero coverage for long-tail ads vs baseline allocator.
- Integration tests:
  - run baseline scenario and compare:
    - paid ads with reach (target: >= previous baseline, ideally all budgeted in-scope)
    - free ads with reach (target: significant increase from baseline)
    - active budget utilization (target: near 100%)
- Reporting checks:
  - `budget_total_all_paid`
  - `budget_total_active_paid`
  - `active_budget_utilization`
  - `overall_budget_utilization`
  - `total_reach_simulated_summary == total_reach_allocated_from_simulation`
  - paid/free coverage uses period-level paid flags (not last-day state)

## Open Questions
- Default `free_share` value: 0.8 (proposed), or 0.7 for more paid-exhausted support?
- Should budget-only ads with zero historical reach receive a temporary rank boost or remain pure pressure-based?
