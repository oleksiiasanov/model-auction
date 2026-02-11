# auction-engine Spec Delta

**Change ID**: `adjust-bid-step-for-organic-balance`

## MODIFIED Requirements

### Requirement: Effective Bid Calculation Parameters

The system SHALL use bid_step parameter to control bid increments and indirectly influence paid/organic reach distribution.

#### Scenario: bid_step controls budget exhaustion rate

- **WHEN** bid_step is set to a higher value (e.g., 0.01 kopecks vs 0.001)
- **THEN** average effective_bid increases proportionally
- **AND** budget exhausts faster (fewer reach slots purchased per AZN)
- **AND** paid auction stops earlier leaving slots for organic fallback
- **RATIONALE**: Higher bids = expensive reach = budget runs out sooner = more organic reach

#### Scenario: bid_step = 0.003 enables optimal balance

- **GIVEN** total available reach = 233,806 slots
- **AND** total budget = 230.25 AZN
- **AND** N = 113 ads with budget
- **WHEN** bid_step = 0.003 kopecks
- **THEN** avg_bid = 0.0662 + (113-1) × 0.003 / 2 ≈ 0.238 kopecks
- **AND** max reach purchasable = (230.25 × 100) / 0.238 ≈ 96,662 slots
- **AND** paid auction allocates ~79,811 slots @ 190 AZN (34% of total)
- **AND** organic fallback allocates ~137,144 slots (59% of total)
- **AND** organic_slots > 0 in hour_complete events
- **AND** spending accuracy = 102% (193 AZN needed for 81k reach vs actual 190 AZN)
- **VALIDATION**: ~5,000 organic ads receive reach (vs 39 with bid_step=0.001)
- **OPTIMAL**: Balances spending accuracy (102%) and organic coverage (59%)

#### Scenario: bid_step = 0.001 prevents organic fallback (current bug)

- **GIVEN** same conditions (total_reach=233,806, budget=230.25 AZN, N=113)
- **WHEN** bid_step = 0.001 kopecks
- **THEN** avg_bid = 0.0662 + (113-1) × 0.001 / 2 ≈ 0.126 kopecks
- **AND** max reach purchasable = (230.25 × 100) / 0.126 ≈ 182,448 slots
- **BUT** actual paid allocation = 233,806 slots (100% of total!)
- **BECAUSE** pacing gate blocks ads → N decreases → bids drop further → budget stretches
- **AND** organic_slots = 0 in all hour_complete events
- **RESULT**: 6,756 organic ads receive zero reach (99.5% loss)
- **BUG**: Organic fallback mechanism never triggers

#### Scenario: Trade-off between spending accuracy and organic coverage

- **WHEN** optimizing bid_step value
- **THEN** must balance two competing goals:
  1. **Spending accuracy**: Match actual cost per reach (0.234 kopecks) → needs bid_step ≈ 0.003
  2. **Organic coverage**: Ensure organic fallback works (60-70% organic reach)
- **TRADE-OFF EXAMPLES**:
  - bid_step = 0.001: Excellent spending tracking BUT organic fallback broken
  - bid_step = 0.003: Good spending accuracy (102%) AND balanced organic (59%)
  - bid_step = 0.01: Poor spending accuracy (269%) BUT strong organic coverage (84%)
- **CHOICE DEPENDS ON**: Business priority (accuracy vs coverage)

#### Scenario: bid_step affects paid/organic distribution

- **WHEN** budget is fixed (230.25 AZN) and total reach is fixed (233,806 slots)
- **THEN** paid_reach_pct = (budget × 100) / (avg_bid × total_reach)
- **AND** organic_reach_pct = 1 - paid_reach_pct
- **EXAMPLES** (N=113):

| bid_step | avg_bid | Paid % | Organic % | Spending Acc | Match Actual (35% paid)? |
|----------|---------|--------|-----------|--------------|--------------------------|
| 0.001    | 0.126   | 100%*  | 0%*       | 54%          | ❌ No organic            |
| 0.003    | 0.238   | 41%    | 59%       | **102%**     | ✅ **OPTIMAL**           |
| 0.005    | 0.350   | 28%    | 72%       | 138%         | ⚠️ Under paid            |
| 0.01     | 0.630   | 16%    | 84%       | 269%         | ❌ Too little paid       |

*Note: 0.001 theoretically allows 78% paid, but actually allocates 100% due to pacing effects

**Recommendation:** bid_step = 0.003 for production (optimal balance)

#### Scenario: Configuration must be tunable

- **WHEN** deploying to production or different environments
- **THEN** bid_step SHALL be configurable via YAML
- **AND** default value SHALL be documented with rationale
- **AND** value SHALL be easily adjustable without code changes
- **LOCATION**: `config/local.yaml` → `simulation.bid_step`
- **UNITS**: kopecks (qəpik)
- **VALIDATION**: Must be positive float > 0.0001

#### Scenario: Effect on max bid range

- **WHEN** bid_step changes
- **THEN** max_bid range also changes proportionally:
  - max_bid = min_bid + (N-1) × bid_step
  - For N=113, min_bid=0.0662:
    - bid_step=0.001 → max_bid=0.178 kopecks (2.7x min)
    - bid_step=0.01 → max_bid=1.190 kopecks (18x min)
- **IMPACT**: Higher max_bid → stronger competition signal → faster budget exhaust for high-pressure ads
