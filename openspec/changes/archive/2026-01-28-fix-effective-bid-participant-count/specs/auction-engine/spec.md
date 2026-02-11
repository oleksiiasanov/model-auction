# auction-engine Specification Changes

## MODIFIED Requirements

### Requirement: Effective Bid Calculation

The system SHALL calculate effective bid for each eligible ad using min_bid, rank_index, and bid_step, where **N counts only ads with remaining_budget > 0** (ads that can actually pay).

**UNITS**: All bid values in kopecks (1/100 currency unit). Example: min_bid=0.5 means 0.005 AZN per impression, bid_step=0.1 means 0.001 AZN increment.

**FORMULA**: `effective_bid = min_bid + (N - 1 - rank_index) * bid_step`

**WHERE**:
- `N` = count of ads with `remaining_budget > 0` (not total ads)
- `rank_index` = position in pressure-sorted ranking (0 = highest pressure)
- `min_bid` = minimum bid for category (from PostgreSQL)
- `bid_step` = bid increment per rank (from config, default 0.1 kopecks)

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

## Rationale for Change

**Previous behavior (bug):**
- N included ALL ads (with and without budget)
- Example: N=8,391 for category with 300 paying ads
- Result: effective_bid inflated 28x, simulated spending 9x actual

**Fixed behavior:**
- N counts only ads with remaining_budget > 0
- Example: N=300 for same category
- Result: effective_bid realistic, simulated spending matches actual

**Why this is correct:**
- Auction bids should reflect actual competition among paying participants
- Ads without budget are "spectators" (simulated organic), not competitors
- Formula `min_bid + (N-1-rank) * bid_step` models competitive bidding:
  - Higher rank → higher bid (to outcompete others)
  - More competitors (N) → higher bids (to win against more ads)
  - Organic ads (budget=0) don't compete for paid slots, shouldn't inflate N

**Backward compatibility:**
- No breaking changes to auction logic or API
- Organic ads still participate and win slots (when paying ads are exhausted)
- Only the bid amount calculation changes (more accurate)
