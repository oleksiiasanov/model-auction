# auction-engine Specification

## Purpose
TBD - created by archiving change add-auction-simulator. Update Purpose after archive.
## Requirements
### Requirement: Pressure Calculation for Ad Prioritization
The system SHALL calculate pressure for each ad based on remaining budget and time left in the day to determine urgency to spend.

#### Scenario: Standard pressure calculation with budget
- **WHEN** an ad has remaining_budget=1000 and time_left=0.5 (12 hours remaining)
- **THEN** pressure is calculated as 1000 / max(0.5, min_time_left_threshold) = 1000 / 0.5 = 2000
- **NOTE**: With hourly updates, min time_left = 0.042 > min_time_left_threshold (0.001), so threshold is not applied

#### Scenario: High pressure near end of day
- **WHEN** an ad has remaining_budget=500 and time_left=0.05 (approximately 1 hour remaining)
- **THEN** pressure is calculated as 500 / 0.05 = 10000 (high urgency)

#### Scenario: Low pressure with low budget
- **WHEN** an ad has remaining_budget=10 and time_left=0.8 (19 hours remaining)
- **THEN** pressure is calculated as 10 / 0.8 = 12.5 (low urgency)

#### Scenario: Zero pressure for simulated organic ads
- **WHEN** an ad has remaining_budget=0 (no campaign, or budget exhausted)
- **THEN** pressure is set to 0 (simulated organic ad, ranks below all ads with budget)

#### Scenario: Minimum time_left threshold (safety net)
- **WHEN** calculating pressure with time_left value
- **THEN** system uses safe_time_left = max(time_left, min_time_left_threshold) where min_time_left_threshold = 0.001
- **PURPOSE**: Defensive programming - prevents division by near-zero values
- **CURRENT STATE**: Not actively used with hourly updates (hour ∈ [0,23]):
  - Minimum actual time_left = (24-23)/24 = 0.042 at hour 23
  - 0.042 > 0.001, so threshold never triggers
- **RATIONALE**: Safety net for edge cases and future implementations (e.g., minute-level or second-level time updates)
- **EXAMPLE**: If time_left = 0.0005, then safe_time_left = max(0.0005, 0.001) = 0.001 (threshold applied)

### Requirement: Pacing Gate for Budget Distribution

The system SHALL enforce a pacing gate to prevent ads from spending their entire budget early in the day, ensuring even distribution, **with a minimum time_progress threshold to prevent blocking at hour 0**.

#### Scenario: Minimum time_progress threshold (prevents hour 0 blocking)

- **WHEN** calculating pacing eligibility with time_progress value
- **THEN** system uses `safe_time_progress = max(time_progress, min_time_progress_threshold)` where `min_time_progress_threshold = 0.042`
- **PURPOSE**: Prevents `max_allowed=0` at hour 0 which blocks all ads after first auction
- **CURRENT STATE**: Actively used at hour 0:
  - At hour 0, `time_progress = 0/24 = 0.0`
  - `0.0 < 0.042`, so threshold triggers → `safe_time_progress = 0.042`
  - `max_allowed = daily_budget × 0.042 × 1.2 ≈ 5%` of daily budget
- **RATIONALE**:
  - Symmetric to `min_time_left_threshold` (defensive programming)
  - Allows ads to spend proportional amount in first hour
  - Value 0.042 = 1 hour (1/24), consistent with hourly update granularity
- **EXAMPLE**:
  - `daily_budget = 100` kopecks
  - At hour 0: `max_allowed = 100 × 0.042 × 1.2 = 5.04` kopecks
  - Ads can win ~33 auctions (`5.04 / 0.15 = 33` wins) before pacing pause
- **CONFIGURATION**: Parameter `simulation.min_time_progress_threshold` in config YAML

#### Scenario: Hour 0 no longer blocks all ads after first win

- **WHEN** `hour=0`, `time_progress=0.0`, ad wins first auction and spends `0.15` kopecks
- **THEN**
  - `safe_time_progress = max(0.0, 0.042) = 0.042`
  - `expected_spend = 100 × 0.042 = 4.2` kopecks
  - `max_allowed = 4.2 × 1.2 = 5.04` kopecks
  - `actual_spend = 0.15 < 5.04` → ad remains eligible ✅
- **BEFORE FIX**:
  - `max_allowed = 100 × 0.0 × 1.2 = 0` kopecks
  - `actual_spend = 0.15 > 0` → ad blocked after single win ❌
- **IMPACT**:
  - Fixes paid impression ratio: `98.5% → ~3.6%` (27x correction)
  - Fixes organic impression ratio: `1.5% → ~96.4%` (64x correction)
  - Enables natural N decrease throughout day

#### Scenario: Threshold transparent at other hours

- **WHEN** `hour=1`, `time_progress = 1/24 = 0.042`
- **THEN**
  - `safe_time_progress = max(0.042, 0.042) = 0.042` (threshold equals real value)
  - Behavior identical to pre-fix implementation
- **WHEN** `hour=6`, `time_progress = 6/24 = 0.25`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - Behavior identical to pre-fix implementation
- **RATIONALE**: Fix only affects hour 0, preserves existing behavior for hours 1-23

#### Scenario: Ad within pacing limits (existing scenario, unchanged)

- **WHEN** `time_progress=0.25` (6 hours elapsed), `daily_budget=1000`, `actual_spend=200`, `pacing_tolerance=0.2`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - `expected_spend = 1000 × 0.25 = 250`
  - `max_allowed = 250 × 1.2 = 300`
  - `actual_spend = 200 < 300` → ad remains eligible ✅
- **NOTE**: Behavior unchanged from pre-fix implementation

#### Scenario: Ad exceeding pacing limits (existing scenario, unchanged)

- **WHEN** `time_progress=0.25`, `daily_budget=1000`, `actual_spend=350`, `pacing_tolerance=0.2`
- **THEN**
  - `safe_time_progress = max(0.25, 0.042) = 0.25` (threshold not applied)
  - `expected_spend = 1000 × 0.25 = 250`
  - `max_allowed = 250 × 1.2 = 300`
  - `actual_spend = 350 > 300` → ad is paused (pressure set to 0) ❌
- **NOTE**: Behavior unchanged from pre-fix implementation

#### Scenario: Configurable threshold for different strategies

- **WHEN** operator wants more/less permissive hour 0 behavior
- **THEN** edit `config/local.yaml`: `simulation.min_time_progress_threshold: [value]`
- **GUIDANCE**:
  - Conservative: `0.042` (1 hour, ~5% budget with tolerance=0.2)
  - Moderate: `0.05` (1.2 hours, ~6% budget)
  - Aggressive: `0.083` (2 hours, ~10% budget)
- **RECOMMENDATION**: Use `0.042` for consistency with hourly update granularity

---

### Requirement: All Ads from Period Participate in Single Auction
The system SHALL include all ads from the selected period/categories (with and without budget) in each auction, with ads without budget receiving pressure=0.

**SCOPE CLARIFICATION**: "All ads" means ads that had impressions during the simulation period (time_from to time_to) within selected filters (country, categories). NOT all ads in the system.

#### Scenario: Mixed auction with paid and organic ads
- **WHEN** category has 10 ads with budget > 0 and 50 ads with budget=0
- **THEN** all 60 ads participate in auction, with paid ads ranking higher (pressure > 0) and organic ads ranking lower (pressure=0)

#### Scenario: Paid ad becomes simulated organic mid-day
- **WHEN** ad had budget=100 at hour 8, spent it by hour 14, budget becomes 0
- **THEN** from hour 14 onwards, ad participates as simulated organic (pressure=0, ranks below ads with budget)

#### Scenario: Simulated organic ad never charged
- **WHEN** ad with budget=0 wins an impression slot
- **THEN** ad is not charged (cost=0), impression counts as simulated organic

### Requirement: Eligibility Filtering for Auction Participation
The system SHALL filter ads for auction participation based on pacing compliance. All ads are eligible by default, but pacing may temporarily pause ads with budget.

#### Scenario: Ad eligible with budget and within pacing
- **WHEN** ad has remaining_budget=500 and passes pacing gate
- **THEN** ad participates in auction with pressure calculated from budget

#### Scenario: Ad eligible with zero budget (simulated organic)
- **WHEN** ad has remaining_budget=0
- **THEN** ad participates in auction with pressure=0, ranks below all ads with budget

#### Scenario: Ad paused due to pacing
- **WHEN** ad has remaining_budget=500 but exceeds pacing limit (actual_spend > daily_budget * time_progress * (1 + pacing_tolerance))
- **THEN** ad pressure is set to 0 (treated as simulated organic temporarily, will resume when time catches up)

### Requirement: Pressure-Based Ranking
The system SHALL rank eligible ads by pressure in descending order and assign rank_index starting from 0 for highest pressure.

#### Scenario: Three ads with different pressure
- **WHEN** ad A has pressure=5000, ad B has pressure=3000, ad C has pressure=1000
- **THEN** ranking is [A, B, C] with rank_index [0, 1, 2]

#### Scenario: Tie-breaking with equal pressure
- **WHEN** two ads have identical pressure
- **THEN** use secondary sort key (ad_id ascending) for deterministic ordering

### Requirement: Effective Bid Calculation

The system SHALL calculate effective bid for each eligible ad using min_bid, rank_index, and bid_step, where **N counts only ads with remaining_budget > 0** (ads that can actually pay).

**UNITS**: All bid values in kopecks (1/100 currency unit). Example: min_bid=0.0702 means 0.000702 AZN per impression, bid_step=0.001 means 0.00001 AZN increment.

**FORMULA**: `effective_bid = min_bid + (N - 1 - rank_index) * bid_step`

**WHERE**:
- `N` = count of ads with `remaining_budget > 0` (not total ads, see MODIFIED comparison: now checks float > 0.0)
- `rank_index` = position in pressure-sorted ranking (0 = highest pressure)
- `min_bid` = minimum bid for category (from PostgreSQL), typically 0.07-0.10 kopecks
- `bid_step` = bid increment per rank (from config, **default 0.001 kopecks, changed from 0.1**)

#### Scenario: N counts only ads with budget

- **WHEN** auction has 300 ads with remaining_budget > 0 and 8,091 ads with remaining_budget = 0
- **THEN** N = 300 (only ads that can pay), NOT N = 8,391 (total ads)
- **RATIONALE**: Ads without budget cannot pay and should not inflate competitive pressure
- **IMPACT**: Prevents artificially inflated bids (e.g., 65 kopecks when N=8,391 vs 6 kopecks when N=300)

#### Scenario: Top-ranked ad with correct N

- **WHEN** N=300 eligible ads with budget, rank_index=0 (best), min_bid=0.0705 kopecks, bid_step=0.1 kopecks
- **THEN** effective_bid = 0.0705 + (300-1-0)×0.1 = 0.0705 + 29.9 = **30.0705 kopecks**
- **CORRECT**: Uses N=300 (ads with budget)
- **INCORRECT**: If using N=8,391 (total), would be 839 kopecks (28x inflation!)

#### Scenario: Middle-ranked ad

- **WHEN** N=300, rank_index=150 (middle), min_bid=0.0705, bid_step=0.1
- **THEN** effective_bid = 0.0705 + (300-1-150)×0.1 = 0.0705 + 14.9 = **15.0705 kopecks**

#### Scenario: Lowest-ranked ad gets min_bid

- **WHEN** N=300, rank_index=299 (worst among paying ads), min_bid=0.0705, bid_step=0.1
- **THEN** effective_bid = 0.0705 + (300-1-299)×0.1 = 0.0705 + 0 = **0.0705 kopecks** (min_bid)

#### Scenario: Edge case with N=1 (single ad with budget)

- **WHEN** only 1 ad has remaining_budget > 0 (N=1), rank_index=0
- **THEN** effective_bid = min_bid + (1-1-0)×bid_step = **min_bid**
- **RATIONALE**: No competition → minimum bid
- **SAFETY**: Use `N = max(ads_with_budget_count, 1)` to prevent N=0 edge case

#### Scenario: Organic ads not counted in N

- **WHEN** ad with remaining_budget=0 participates in auction (simulated organic)
- **THEN** ad is NOT included in N count
- **AND** ad has pressure=0, ranks after all paying ads
- **AND** if ad wins (due to insufficient paying ads), pays **cost=0** (organic impression)

#### Scenario: N changes dynamically as budgets exhaust

- **WHEN** batch 1 has N=300 ads with budget, some ads spend all budget during batch 1
- **THEN** batch 2 recalculates N (e.g., N=285 if 15 ads exhausted budget)
- **RATIONALE**: N reflects current competitive landscape, not fixed at start of day

#### Scenario: Validation logging for debugging

- **WHEN** selecting winners in batch auction
- **THEN** log: `"Batch {n}: N={ads_with_budget} ads with budget (out of {total_ads} total)"`
- **PURPOSE**: Make N value visible in logs for debugging bid inflation issues

#### Scenario: min_bid per category from PostgreSQL

- **WHEN** calculating min_bid for category
- **THEN** fetch from PostgreSQL `campaign_ad_price` table: `min_bid = price_per_day / fact_impression`
- **DATA SOURCE**: PostgreSQL (authoritative pricing), NOT ClickHouse calculation
- **CROSS-REF**: See data-extraction spec for PostgreSQL query details

#### Scenario: Small bid_step for granular pricing

- **WHEN** `N=81`, `rank_index=0` (best), `min_bid=0.0702` kopecks, `bid_step=0.001` kopecks
- **THEN** `effective_bid = 0.0702 + (81-1-0)×0.001 = 0.0702 + 0.08 = 0.1502` kopecks
- **COMPARISON TO OLD**:
  - Old (`bid_step=0.1`): `effective_bid = 0.0702 + 80×0.1 = 8.0702` kopecks (53x higher!)
  - New (`bid_step=0.001`): `effective_bid = 0.1502` kopecks (2x min_bid, reasonable)
- **RATIONALE**: `bid_step=0.001` provides granular bid increments matching market scale, avoiding artificially inflated bids

#### Scenario: Bid range with reduced bid_step

- **WHEN** `N=81`, `min_bid=0.0702`, `bid_step=0.001`
- **THEN** bid range spans:
  - Max (rank=0): `0.0702 + 80×0.001 = 0.1502` kopecks
  - Min (rank=80): `0.0702 + 0×0.001 = 0.0702` kopecks
- **SPREAD**: 0.08 kopecks (53% increase from min to max)
- **VS OLD** (`bid_step=0.1`): Spread was 8.0 kopecks (114x increase from min to max) - unrealistic

#### Scenario: Configurable bid_step

- **WHEN** operator wants to adjust bid granularity
- **THEN** edit `config/local.yaml`: `simulation.bid_step: 0.001`
- **GUIDANCE**: `bid_step ≈ min_bid / 100` (rule of thumb for 1% granularity)
- **EXAMPLE**: If `min_bid=0.07`, then `bid_step=0.0007` would provide 100 price points

### Requirement: First-Price Auction Winner Selection
The system SHALL select top N winners by effective_bid (which follows pressure ranking) and charge each winner their bid amount.

#### Scenario: Batch of 40 impressions with 100 eligible ads
- **WHEN** 100 ads compete for 40 impression slots
- **THEN** top 40 ads by effective_bid (rank_index 0-39) win

#### Scenario: Fewer ads than slots (proportional historical organic fallback)
- **WHEN** 3 ads available (all with budget=0, i.e., simulated organic) but 300 impression slots need to be filled
- **AND** historical organic impressions (is_paid=false from ClickHouse): Ad A=100, Ad B=50, Ad C=0
- **THEN** distribute 300 slots proportionally with rounding control:
  - Base allocation: Ad A gets int(300*100/150)=200, Ad B gets int(300*50/150)=100, Ad C gets 0
  - Total allocated: 200+100+0=300 (exact match in this example)
  - If remainder exists due to rounding (e.g., 299 allocated, 1 remains), distribute remainder to ads with highest proportions first
- **CONSERVATION CHECK**: Sum of allocated slots MUST equal remaining_slots exactly (300 in this example)
- **RATIONALE**: Preserves total impression conservation by using historical organic distribution (is_paid=false) as proxy for quality/relevance
- **NOTE**: Historical organic (is_paid=false yesterday) is separate from simulated organic (budget=0 today). An ad with budget=0 today may have had paid impressions historically.

#### Scenario: Zero historical organic impressions fallback
- **WHEN** all ads have 0 historical organic impressions (is_paid=false count = 0, e.g., all were purely paid yesterday)
- **AND** slots remain after all budgets exhausted (all ads now simulated organic with budget=0)
- **THEN** distribute remaining slots equally with remainder control:
  - Base allocation: each ad gets floor(remaining_slots / num_ads)
  - Remainder: remaining_slots % num_ads distributed to first N ads (deterministic order by ad_id)
  - Example: 100 slots, 3 ads → each gets 33, remainder 1 goes to first ad → [34, 33, 33]
- **CONSERVATION CHECK**: Sum of allocated slots MUST equal remaining_slots exactly
- **RATIONALE**: Equal distribution is fallback when no quality signal available. Prioritizes conservation and fairness over quality proxy (which is unavailable).
- **HIERARCHY**: Proportional by historical organic (best proxy) → Equal distribution (neutral fallback) → Fail/error (if no ads)
- **NOTE**: This is rare edge case; log warning as it indicates potential data quality issue or category with no organic traffic historically

#### Scenario: Conservation validation after fallback
- **WHEN** organic fallback completes (either proportional or equal)
- **THEN** system MUST validate: SUM(allocated_slots) == remaining_slots (exact equality, no tolerance)
- **MECHANISM**:
  - **Proportional algorithm**:
    1. Calculate proportions: `proportion[i] = organic_historical[i] / sum(organic_historical)`
    2. Base allocation: `base[i] = floor(remaining_slots * proportion[i])` for each ad
    3. Calculate remainder: `remainder = remaining_slots - sum(base)`
    4. Sort ads by proportion descending (deterministic: use ad_id for ties)
    5. Distribute remainder: add 1 slot to first `remainder` ads in sorted order
    6. Result: `final[i] = base[i] + (1 if i < remainder else 0)`
  - **Equal algorithm**:
    1. Base allocation: `base = floor(remaining_slots / num_ads)`
    2. Calculate remainder: `remainder = remaining_slots % num_ads`
    3. Sort ads by ad_id ascending (deterministic)
    4. Distribute: `final[i] = base + (1 if i < remainder else 0)`
  - Both mechanisms mathematically guarantee sum equals remaining_slots
- **IF** validation fails, log critical error and abort simulation (indicates implementation bug)

### Requirement: Budget Deduction and State Update

The system SHALL update **simulated_reach counters** (not impression counters) after each batch.

#### Scenario: Increment reach counter on win

- **WHEN** ad wins auction and receives `allocated_reach` slots
- **THEN**
  - `ad.simulated_reach += allocated_reach` (NEW field name)
  - `ad.remaining_budget -= cost`
  - `ad.actual_spend += cost`
- **PREVIOUS**: `ad.simulated_impressions += count`

#### Scenario: Organic reach fallback

- **WHEN** distributing remaining reach slots among simulated organic ads
- **THEN** use `ad.organic_reach_historical` for proportional distribution
- **PREVIOUS**: `ad.organic_impressions_historical`
- **CONSISTENCY**: All metrics based on reach

---

### Requirement: Dynamic Recomputation per Batch
The system SHALL recompute eligibility, pressure, ranking, and effective_bids for each batch as budgets and time progress change.

#### Scenario: Pressure changes between batches
- **WHEN** ad A had pressure=5000 in batch 1, spends 100, time advances
- **THEN** in batch 2, pressure is recalculated with new remaining_budget and time_left

#### Scenario: Eligibility changes between batches
- **WHEN** ad B becomes ineligible in batch 2 due to pacing gate
- **THEN** ad B is excluded from batch 2 auction, other ads' rank_index shift accordingly

### Requirement: Reach Timestamp Tracking

The system SHALL track when each reach occurred using first-view timestamp.

#### Scenario: Reach assigned to hour of first view

- **WHEN** user views ad multiple times in day
- **THEN** reach timestamp = MIN(timestamp) of all views that day
- **EXAMPLE**:
  - User 33 views ad_id=1 at 09:00, 14:00, 22:00 on 2026-05-15
  - reach_timestamp = 09:00
  - This reach allocated to hour 9 auction batch
- **PURPOSE**: Correct temporal distribution of reach

#### Scenario: Reach counted once per day per user per ad

- **WHEN** same user views same ad on different days
- **THEN** each day generates separate reach count
- **EXAMPLE**:
  - User 33 views ad_id=1 on 2026-05-15 (3 times) → 1 reach
  - User 33 views ad_id=1 on 2026-05-16 (2 times) → 1 reach
  - Total: 2 reach across 2 days (not 1, not 5)

---

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

### Requirement: Exact Conservation in Cumulative Organic Allocation
The system SHALL guarantee exact slot conservation for each cumulative organic fallback event.

#### Scenario: Per-event conservation holds
- **WHEN** fallback is called with `remaining_slots = N`
- **THEN** sum of all allocated slots equals exactly `N`
- **AND** event-level conservation check reports valid

#### Scenario: Residual allocation preserves debt semantics
- **WHEN** residual slots are assigned to ads by carry ranking
- **THEN** each assigned residual slot decrements winner carry by `1.0`
- **AND** carry is allowed to become negative to represent debt
- **AND** no carry clamping to zero is applied in this step

#### Scenario: Multi-batch cumulative allocation has zero drift
- **WHEN** many fallback batches execute sequentially
- **THEN** cumulative allocated slots equal cumulative requested slots exactly
- **AND** no systematic positive or negative drift is introduced

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

