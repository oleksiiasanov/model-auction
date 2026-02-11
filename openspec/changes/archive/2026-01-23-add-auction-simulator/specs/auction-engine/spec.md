## ADDED Requirements

### Requirement: Pressure Calculation for Ad Prioritization
The system SHALL calculate pressure for each ad based on remaining budget and time left in the day to determine urgency to spend.

#### Scenario: Standard pressure calculation with budget
- **WHEN** an ad has remaining_budget=1000 and time_left=0.5 (12 hours remaining)
- **THEN** pressure is calculated as 1000 / max(0.5, epsilon) = 2000

#### Scenario: High pressure near end of day
- **WHEN** an ad has remaining_budget=500 and time_left=0.05 (approximately 1 hour remaining)
- **THEN** pressure is calculated as 500 / 0.05 = 10000 (high urgency)

#### Scenario: Low pressure with low budget
- **WHEN** an ad has remaining_budget=10 and time_left=0.8 (19 hours remaining)
- **THEN** pressure is calculated as 10 / 0.8 = 12.5 (low urgency)

#### Scenario: Zero pressure for simulated organic ads
- **WHEN** an ad has remaining_budget=0 (no campaign, or budget exhausted)
- **THEN** pressure is set to 0 (simulated organic ad, ranks below all ads with budget)

#### Scenario: Division by zero prevention
- **WHEN** time_left approaches 0 (e.g., 0.0001)
- **THEN** pressure is calculated using max(time_left, epsilon) where epsilon=0.001 to prevent division errors

### Requirement: Pacing Gate for Budget Distribution
The system SHALL enforce a pacing gate to prevent ads from spending their entire budget early in the day, ensuring even distribution.

#### Scenario: Ad within pacing limits
- **WHEN** time_progress=0.25 (6 hours elapsed), daily_budget=1000, actual_spend=200, pacing_tolerance=0.2
- **THEN** expected_spend = daily_budget * time_progress = 1000 * 0.25 = 250, actual is 200 < 300 (250 * 1.2), ad remains eligible

#### Scenario: Ad exceeding pacing limits
- **WHEN** time_progress=0.25, daily_budget=1000, actual_spend=350, pacing_tolerance=0.2
- **THEN** expected_spend = daily_budget * time_progress = 1000 * 0.25 = 250, actual is 350 > 300 (250 * 1.2), ad is paused (pressure set to 0)

#### Scenario: Ad resumes after pacing pause
- **WHEN** ad was paused at hour 6 due to overspending
- **THEN** ad becomes eligible again when time catches up to spending rate (e.g., hour 12 if spent 50%)

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
The system SHALL calculate effective bid for each eligible ad using min_bid, rank_index, and bid_step.

**UNITS**: All bid values in kopecks (1/100 currency unit). Example: min_bid=0.5 means 0.005 AZN per impression, bid_step=0.1 means 0.001 AZN increment.

#### Scenario: Top-ranked ad gets highest bid
- **WHEN** N=10 eligible ads, rank_index=0 (best), min_bid=0.5 kopecks, bid_step=0.1 kopecks
- **THEN** effective_bid = 0.5 + (10-1-0)*0.1 = 0.5 + 0.9 = 1.4 kopecks (0.014 AZN per impression)

#### Scenario: Middle-ranked ad
- **WHEN** N=10, rank_index=5, min_bid=0.5, bid_step=0.1
- **THEN** effective_bid = 0.5 + (10-1-5)*0.1 = 0.5 + 0.4 = 0.9

#### Scenario: Lowest-ranked ad gets min_bid
- **WHEN** N=10, rank_index=9 (worst), min_bid=0.5, bid_step=0.1
- **THEN** effective_bid = 0.5 + (10-1-9)*0.1 = 0.5 + 0 = 0.5

#### Scenario: min_bid per category from same period
- **WHEN** calculating min_bid for category_id=1234 during simulation of period 2024-01-15 to 2024-01-17
- **THEN** min_bid = total_spending_cat / total_paid_impressions_cat from the same period (2024-01-15 to 2024-01-17)
- **DATA SOURCE**: Use spendings_distributed as single source of truth for both spending and paid impression counts
- **NOTE**: Schema verification required - see data-extraction/spec.md for implementation details (may require join with enriched_distributed if spendings_distributed lacks impression counts)

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

#### Scenario: Winner charged their effective bid
- **WHEN** an ad with effective_bid=1.2 (kopecks, float) wins an impression
- **THEN** round(1.2) = 1 kopeck is deducted from remaining_budget (integer) and added to actual_spend (integer)
- **ROUNDING**: Use standard rounding (0.5 rounds up) when converting float bid to integer budget deduction
- **CURRENCY**: All values in kopecks (1/100 of currency unit). Example: effective_bid=1.2 means 0.012 AZN per impression

### Requirement: Budget Deduction and State Update
The system SHALL deduct effective_bid from each winner's remaining_budget and update spending counters after each batch.

#### Scenario: Successful deduction after win with rounding
- **WHEN** ad with remaining_budget=100 (integer kopecks) and effective_bid=1.5 (float kopecks) wins
- **THEN** cost = round(1.5) = 2 kopecks (integer), remaining_budget becomes 98 (integer), actual_spend increases by 2 (integer), simulated_impressions increases by 1
- **ROUNDING**: effective_bid (float) rounded to nearest integer kopeck before deduction using standard rounding (0.5 → 1)
- **ALTERNATIVE**: Store actual_spend as float to preserve exact costs, but remaining_budget must be integer (cannot spend fractional kopecks)

#### Scenario: Budget exhaustion mid-simulation
- **WHEN** ad's remaining_budget reaches 0 during a batch
- **THEN** ad becomes ineligible for all subsequent auctions in the day

### Requirement: Dynamic Recomputation per Batch
The system SHALL recompute eligibility, pressure, ranking, and effective_bids for each batch as budgets and time progress change.

#### Scenario: Pressure changes between batches
- **WHEN** ad A had pressure=5000 in batch 1, spends 100, time advances
- **THEN** in batch 2, pressure is recalculated with new remaining_budget and time_left

#### Scenario: Eligibility changes between batches
- **WHEN** ad B becomes ineligible in batch 2 due to pacing gate
- **THEN** ad B is excluded from batch 2 auction, other ads' rank_index shift accordingly
