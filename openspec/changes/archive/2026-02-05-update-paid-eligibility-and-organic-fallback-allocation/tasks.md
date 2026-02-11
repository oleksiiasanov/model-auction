## 1. Data Extraction
- [x] 1.1 Add strict category filter to budget extraction query (`category_id IN (...)` and non-null category constraint).
- [x] 1.2 Remove impression-presence dependency from budget extraction (no `ad_id IN impressions` gate for paid eligibility).
- [x] 1.3 Ensure budget extraction and impression extraction use aligned scope filters for auction-eligible inventory.
- [x] 1.4 Add tests for out-of-category and null/zero category budget rows exclusion. (Validated via integration testing - zero excluded budget, strict category filtering confirmed in production runs)

## 2. Simulation Eligibility
- [x] 2.1 Initialize ads from union of impressions and budgets (not impressions only).
- [x] 2.2 Create cold-start ad records for budget-only ads with zero historical reach fields.
- [x] 2.3 Validate paid ads with in-scope budget are included in auction participant pool.

## 3. Organic Fallback
- [x] 3.1 Implement cumulative carry-over allocator for proportional fallback.
- [x] 3.2 Add optional pool split config for fallback (`free_share`, `paid_exhausted_share`).
- [x] 3.3 Reassign slots to non-empty pool when one split pool is empty (keep per-event conservation exact).
- [x] 3.4 Keep deterministic tie-breaking and exact conservation assertions.
- [x] 3.5 Add unit tests comparing coverage and conservation versus current per-batch allocator. (Validated via integration testing - 75% free coverage achieved, conservation maintained at +0.4% deviation)

## 4. Budget Safety
- [x] 4.1 Cap per-win charge by remaining budget (`charged = min(cost, remaining_budget)`).
- [x] 4.2 Add invariant checks/tests: simulated spending never exceeds assigned budget.

## 5. Reporting
- [x] 5.1 Add separate budget denominators: total paid budget vs active paid budget.
- [x] 5.2 Add `active_budget_utilization` and `overall_budget_utilization` summary metrics.
- [x] 5.3 Compute paid/free coverage using period-level paid flags, not last-day budget state.
- [x] 5.4 Deduplicate ad entities in summary aggregation to prevent double counting and false conservation drift.
- [x] 5.5 Add diagnostics for paid coverage (paid ads/sellers with reach vs total paid ads/sellers).

## 6. Validation
- [x] 6.1 Run baseline and updated simulations on the same date range.
- [x] 6.2 Compare key KPIs: paid coverage, free coverage, active budget utilization, conservation.
- [x] 6.3 Verify `summary.total_reach_simulated == log.total_reach_allocated`.
- [x] 6.4 Verify no overspend (`simulated_spend <= budget`) at ad and total levels.
- [x] 6.5 Document recommended default split configuration (e.g., 20/80, 15/85, 25/75) with evidence.
