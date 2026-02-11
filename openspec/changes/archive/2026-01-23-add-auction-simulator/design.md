# Design: Auction Simulator

## Context

We're building an **offline simulator** to test auction-based ad distribution before making production changes. The simulator must:
- Work with real historical data for configurable time ranges and filters
- **Preserve total impression volume** (paid + organic combined) per category per time
- Redistribute impressions: ads with budget get more, ads without budget get less
- Compare outcomes: current system vs auction-based system
- Support runtime parameters: country, categories, time_from, time_to

**Critical Design Principle: Total Impression Conservation**
- We extract **TOTAL impressions** (paid + organic combined) from historical data
- Example: category had 500 total impressions/hour → simulation uses exactly 500 impressions/hour
- **Paid/organic split changes**: if more ads have budget when they win slots → more paid, less organic
- **Two definitions of "organic"**:
  - **Historical organic** (is_paid=false in ClickHouse): used only for proportional fallback distribution when all budgets exhausted
  - **Simulated organic** (budget=0 at auction time): ads compete with pressure=0, rank below ads with budget
- As budgets deplete during day, paid ads dynamically become simulated organic (budget exhausted → pressure=0)

**What we DO simulate**: auction mechanics, pressure ranking, pacing, budget depletion, organic impression distribution (from historical data)
**What we DON'T simulate**: buyer behavior, organic relevance algorithm (Google-style quality scoring), session uniqueness, click-through rates

**Organic Fallback**: If all paid budgets exhausted but slots remain, system distributes remaining slots proportionally based on **historical organic impression counts** (is_paid=false from ClickHouse). This preserves conservation and uses historical data as proxy for quality/relevance. An ad with budget=0 now may have had paid impressions historically - that's fine, we use historical organic counts purely for proportional distribution. If no organic history exists, falls back to equal distribution with warning.

**Key stakeholders**: Product team (fairness validation), sellers (predictability), engineering (implementation complexity)

**Constraints**:
- Must complete simulation within reasonable time (minutes, not hours)
- Must handle categories with 1000+ ads
- All ads from period eligible (MVP simplification: no rotation constraints, but only ads with impressions in period participate)
- Read-only access to production databases

**Runtime Parameters**:
- `country`: integer (e.g., 13 for Azerbaijan)
- `categories`: list of integers (e.g., [1234, 5678])
- `time_from`: date (start of simulation period, inclusive, must be full day: YYYY-MM-DD)
- `time_to`: date (end of simulation period, inclusive, must be full day: YYYY-MM-DD)

**Time Granularity**:
- MVP processes full days only (no partial days)
- Within each day: hourly granularity (24 hours: 0-23)
- `time_progress = hour / 24.0` assumes hour=0 means start of day, hour=23 means last hour
- This simplification is sufficient for validating auction fairness hypothesis

## Goals / Non-Goals

**Goals**:
- ✅ Validate that auction model improves fairness for sellers
- ✅ Identify which sellers gain/lose impressions under new model
- ✅ Test effective bid calculation algorithm
- ✅ Validate pressure-based ranking with pacing gate
- ✅ Generate actionable comparison reports

**Non-Goals**:
- ❌ Simulate buyer behavior or click-through rates
- ❌ Optimize organic ranking
- ❌ Build production-ready auction service
- ❌ Handle real-time bidding or live traffic
- ❌ Support complex search filters (category feed only)

## Decisions

### Decision 1: First-Price Auction with Pressure-Based Ranking

**Choice**: First-price auction where winner pays their effective bid per impression. Bids are calculated based on pressure (urgency to spend) and rank within the auction.

**Why**:
- Simplest to implement and explain
- Fully deterministic (reproducible results)
- Easy to simulate offline
- Aligns with hypothesis: "who needs to spend budget faster gets higher priority"
- Based on Meta auction model (proven at scale)

**Formula Sources**:
- **Pressure formula** inspired by Meta/Facebook auction pacing: budget delivery urgency = remaining_budget / time_left
- **First-price auction** is simplest model, used by many ad platforms (Meta, Twitter, LinkedIn)
- **Effective bid via rank_index** creates deterministic, reproducible auction without real-time bidding complexity
- **min_bid baseline** grounds bids in actual category economics (average historical cost per impression)

**Alternatives considered**:
- Second-price (Vickrey): More complex, requires next-highest bid tracking, harder to explain
- GSP (Google Ads style): Overkill for MVP, adds Quality Score complexity we don't have
- Manual bidding: Not our model - we want algorithmic bids for predictability
- Plan-based urgency (delivery deficit): Too complex, returns to plan/fact model we want to avoid
- Fixed CPM: Doesn't capture urgency, ads would spend budget too early or too late

**Scope Definition**:
- **scope_type** = "ad" (ad-level auction in MVP)
- **scope_id** = ad_id
- Budget tracking: per ad_id (or its campaign)
- Reach Profile: constraint on eligibility, not separate scope level

**Pressure Formula** (urgency to spend):
```python
pressure = remaining_budget / max(time_left, epsilon)
```

Where:
- `remaining_budget` = money left for this scope (ad) for the day
- `time_left` = fraction of day remaining (0..1), calculated as `1 - time_progress`
- `epsilon` = small constant to prevent division by zero (e.g., 0.001)

**Intuition**: If time is running out and budget is high, pressure is high → should show more often now.

**Pacing Gate** (mandatory to prevent budget dump):
```python
expected_spend = daily_budget * time_progress
if actual_spend > expected_spend * (1 + pacing_tolerance):
    # Scope is temporarily ineligible (paused)
```

Where:
- `daily_budget` = plan budget for the day
- `time_progress` = fraction of day elapsed (0..1)
- `actual_spend` = how much already spent
- `pacing_tolerance` = e.g., 0.2 (can spend up to 20% ahead of schedule)

**Effective Bid Formula**:
```python
effective_bid = min_bid + (N - 1 - rank_index) * bid_step
```

Where:
- `min_bid` = avg_price_per_impression_cat from the same simulation period (time_from to time_to) for this category
  - `min_bid = total_spend_paid_cat / total_paid_impressions_cat`
- `N` = number of eligible ads in this auction
- `rank_index` = position of ad in sorted list (0 = best pressure, N-1 = worst)
- `bid_step` = 0.1 (constant, in same currency units as min_bid)

**Ranking Logic** (per auction/batch):
1. All ads participate (budget=0 → pressure=0, treated as organic)
2. Calculate pressure for each ad: `remaining_budget / max(time_left, epsilon)`
3. Apply pacing gate: if overspending → set pressure=0 temporarily
4. Sort by pressure DESC (highest pressure first), secondary sort by ad_id for determinism
5. Assign rank_index = 0..N-1 (top-1 has rank_index=0)
6. Calculate effective_bid for each: `min_bid + (N - 1 - rank_index) * bid_step`
7. Top batch_size (e.g., 40) by effective_bid win impressions
8. Charge each winner: `cost = effective_bid if remaining_budget > 0 else 0`
9. Deduct from remaining_budget, track spending
10. Recompute for next batch (pressure changes dynamically as budgets deplete)

**Why this formula works**:
- Higher pressure → lower rank_index → higher effective_bid → more likely to win
- min_bid grounds bids in real category economics (not arbitrary)
- bid_step creates separation between competitors
- Recomputing each batch ensures fairness as budgets deplete

### Decision 2: Batch-Based Simulation (40 impressions per batch)

**Choice**: Process impressions in batches of 40, matching real category feed pagination behavior

**Why**:
- Matches real system behavior (category feed returns 40 ads per page via infinite scroll/pagination)
- Auction runs for each batch separately (dynamic eligibility, budgets change between batches)
- All ads compete in each batch: ads with budget rank higher, ads without budget rank lower
- Easy to reason about position-based metrics

**How it works**:
1. Group total impressions (paid + organic) by category + day + hour
2. For each batch of 40 impression slots:
   - Run auction among **all ads** (both with and without budget)
   - Calculate pressure for each ad (budget=0 → pressure=0)
   - Sort by pressure DESC → assign rank_index → calculate effective_bid
   - Top 40 by effective_bid win
   - Charge winners who have budget > 0
   - Repeat until all total impressions distributed

**Key insight**: "Paid" vs "organic" impression is determined by whether winning ad has budget at time of auction, not by pre-allocated slots.

### Decision 3: All Ads Always Eligible (MVP Simplification)

**Choice**: All ads from all sellers are always eligible for auction participation. No Reach Profile rotation or eligibility constraints in MVP.

**Why**:
- Simplifies MVP implementation (no rotation logic, no windowing)
- Focuses on core auction mechanics (pressure, pacing, effective bid)
- Avoids complexity of multi-seller rotation state management
- Can be added in future iteration without changing core auction logic
- Sufficient for validating fairness hypothesis: "budget → priority"

**Implementation**:
- All ads that had impressions in historical period participate
- Only constraints: budget (remaining_budget > 0) and pacing gate
- No hourly rotation windows
- No per-seller ad limits

**Future extension**:
- If Reach Profile needed later: add eligibility filter before auction
- Core auction engine remains unchanged

### Decision 4: Language & Data Access

**Choice**: Python for simulation, direct database connections

**Why Python**:
- Fast prototyping for data analysis tasks
- Rich ecosystem (pandas, numpy) for batch processing
- Easy to generate CSV/Excel reports
- Team familiarity (assumed based on data science context)

**Alternatives considered**:
- Go: Faster, but overkill for offline batch processing
- SQL-only: Too limited for complex auction logic
- Node.js: Possible, but Python better for data science

**Data access**:
- ClickHouse: Impressions (ad_id, category_id, timestamp, is_paid, seller_id)
- PostgreSQL: Budgets, ads, sellers, Reach Profile configurations
- Cache extracted data locally to avoid repeated queries during development

### Decision 5: Output Format - Simple Tables First

**Choice**: CSV/Excel with side-by-side comparison columns

**Why**:
- Easy to validate manually
- Compatible with existing business tools (Excel, Google Sheets)
- Can add visualization later without changing core logic
- Supports diff-based analysis

**Schema** (see comparison-reporting spec for full details):
```
seller_id | paid_impressions_actual | paid_impressions_simulated |
total_impressions_actual | total_impressions_simulated |
plan_budget | plan_budget_simulated | spendings_actual | spendings_simulated
```

Same structure for per-ad report.

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Auction Simulator                      │
└─────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │                                     │
         ▼                                     ▼
┌─────────────────┐                  ┌──────────────────┐
│ Data Extraction │                  │ Auction Engine   │
│                 │                  │                  │
│ - ClickHouse    │                  │ - Pressure calc  │
│ - Local cache   │                  │ - Effective bid  │
│                 │                  │ - Winner select  │
└─────────────────┘                  │ - Cost deduct    │
                                     │ - Pacing gate    │
                                     └──────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Comparison       │
                                    │ Reporting        │
                                    │                  │
                                    │ - Seller table   │
                                    │ - Ad table       │
                                    │ - CSV export     │
                                    └──────────────────┘
```

### Data Flow

1. **Extract** (once per simulation run):
   - Pull impressions from ClickHouse (enriched_distributed) for time range
   - Pull campaign budgets from ClickHouse (spendings_distributed) for time range
   - Join on ad_id + data_chunk_date
   - Group by category + day + hour
   - Cache locally

2. **Simulate** (per category per day per hour):
   - Calculate pressure for all ads (including budget=0)
   - Calculate effective bids based on pressure ranking
   - Run batch-based auction (40 impressions per batch)
   - Charge winners (if budget > 0)
   - Deduct costs from remaining_budget
   - Track winners and spending

3. **Compare** (at end):
   - Aggregate actual vs simulated metrics per seller
   - Aggregate actual vs simulated metrics per ad
   - Export to CSV with metadata

### Pseudo-code (Core Loop)

```python
# Configuration
epsilon = 0.001  # time_left minimum for division safety
pacing_tolerance = 0.2  # 20% ahead of schedule allowed
bid_step = 0.1  # kopecks increment between rank positions

# Currency: all monetary values in kopecks (1/100 of currency unit)
# Example: 100 kopecks = 1.00 AZN, 1000 kopecks = 10.00 AZN

# Pre-compute min_bid per category from historical data
# Note: Uses spendings_distributed as single source of truth
# Schema-dependent: requires impressions count field or join with enriched_distributed
min_bid_per_category = {
    cat_id: get_total_spending(cat_id, time_from, time_to) / get_paid_impressions_count(cat_id, time_from, time_to)
    for cat_id in categories
}

# Extract date range into list of days
days = get_days_between(time_from, time_to)  # e.g., [2024-01-15, 2024-01-16, 2024-01-17]

for day in days:
    # Load daily budgets from campaign MS for this specific day
    daily_budgets = get_daily_budgets_for_date(day)

    for category in categories:
        min_bid = min_bid_per_category[category]

        # Get all ads for category
        all_ads = get_ads_for_category(category)

        # Initialize daily state
        for ad in all_ads:
            ad.daily_budget = daily_budgets.get(ad.id, 0)  # 0 if no campaign
            ad.remaining_budget = ad.daily_budget
            ad.actual_spend = 0
            ad.simulated_impressions = 0
            ad.simulated_spending = 0
            ad.organic_impressions_historical = get_organic_impression_count(ad.id, day)  # is_paid=false historically, for fallback

        for hour in range(24):
            time_progress = hour / 24.0  # Within this day
            time_left = 1.0 - time_progress

            # Get TOTAL impressions this hour (not just paid!)
            total_impressions_this_hour = get_total_impression_count(category, day, hour)

            # Process in batches of 40
            for batch_idx in range(0, total_impressions_this_hour, 40):
                batch_size = min(40, total_impressions_this_hour - batch_idx)

                # Filter eligible + calculate pressure for ALL ads (including budget=0)
                ads_with_pressure = []
                for ad in all_ads:
                    # Pacing gate (only for ads with budget > 0)
                    if ad.remaining_budget > 0:
                        expected_spend = ad.daily_budget * time_progress
                        if ad.actual_spend > expected_spend * (1 + pacing_tolerance):
                            ad.pressure = 0  # Paused due to pacing
                        else:
                            # Calculate pressure
                            ad.pressure = ad.remaining_budget / max(time_left, epsilon)
                    else:
                        # No budget = simulated organic, pressure = 0
                        ad.pressure = 0

                    ads_with_pressure.append(ad)

                # Sort by pressure DESC (ads with budget=0 go to bottom)
                ads_with_pressure.sort(key=lambda a: (a.pressure, a.id), reverse=True)

                # Assign rank_index and calculate effective_bid
                N = len(ads_with_pressure)
                for rank_index, ad in enumerate(ads_with_pressure):
                    ad.rank_index = rank_index
                    ad.effective_bid = min_bid + (N - 1 - rank_index) * bid_step

                # Select winners (top batch_size by effective_bid)
                winners = ads_with_pressure[:batch_size]

                # Organic fallback: if not enough ads with pressure > 0
                if len(winners) < batch_size:
                    remaining_slots = batch_size - len(winners)
                    organic_ads = [a for a in ads_with_pressure if a.pressure == 0 and a not in winners]

                    # Distribute remaining slots proportionally to historical organic impressions (is_paid=false)
                    total_organic_historical = sum(a.organic_impressions_historical for a in organic_ads)
                    if total_organic_historical > 0:
                        # Integer allocation with remainder distribution (guarantees exact conservation)
                        allocated_slots = []
                        for ad in organic_ads:
                            proportion = ad.organic_impressions_historical / total_organic_historical
                            base_slots = int(remaining_slots * proportion)
                            allocated_slots.append((ad, base_slots, proportion))

                        # Calculate remainder and distribute to top ads by proportion
                        total_allocated = sum(slots for _, slots, _ in allocated_slots)
                        remainder = remaining_slots - total_allocated
                        # Sort by proportion descending for remainder allocation
                        allocated_slots.sort(key=lambda x: x[2], reverse=True)
                        for i in range(remainder):
                            allocated_slots[i] = (allocated_slots[i][0], allocated_slots[i][1] + 1, allocated_slots[i][2])

                        # CONSERVATION GUARANTEE: sum(final_slots) == remaining_slots exactly
                        # Proof: base_slots sum <= remaining_slots (floor), remainder adds exactly (remaining_slots - sum)
                        total_final = sum(slots for _, slots, _ in allocated_slots)
                        assert total_final == remaining_slots, f"Conservation violated: {total_final} != {remaining_slots}"

                        for ad, final_slots, _ in allocated_slots:
                            if final_slots > 0:
                                ad.extra_organic_slots = final_slots
                                winners.append((ad, final_slots))
                    else:
                        # Fallback: equal distribution if no organic history
                        base_slots = remaining_slots // len(organic_ads) if organic_ads else 0
                        remainder = remaining_slots % len(organic_ads) if organic_ads else 0

                        # CONSERVATION GUARANTEE: base_slots * len + remainder == remaining_slots exactly
                        # Proof: floor division gives base, modulo gives remainder, sum always equals total
                        allocated_sum = 0
                        for i, ad in enumerate(organic_ads):
                            ad.extra_organic_slots = base_slots + (1 if i < remainder else 0)
                            allocated_sum += ad.extra_organic_slots
                            winners.append((ad, ad.extra_organic_slots))

                        assert allocated_sum == remaining_slots, f"Conservation violated: {allocated_sum} != {remaining_slots}"
                        log_warning(f"No historical organic impressions for fallback distribution")

                # Charge winners (only if they have budget)
                for winner in winners:
                    impressions_count = winner[1] if isinstance(winner, tuple) else 1
                    ad = winner[0] if isinstance(winner, tuple) else winner

                    # Cost calculation: round float effective_bid to integer kopecks for budget deduction
                    if ad.remaining_budget > 0:
                        cost_float = ad.effective_bid
                        cost_integer = round(cost_float)  # standard rounding: 0.5 → 1
                        ad.remaining_budget = max(0, ad.remaining_budget - cost_integer)
                        ad.actual_spend += cost_float  # track exact spend (float) for reporting
                    else:
                        cost_float = 0
                        cost_integer = 0

                    ad.simulated_impressions += impressions_count
                    ad.simulated_spending += cost_float * impressions_count
```

**Key differences from initial version:**
1. **Multi-day loop**: Each day has separate budget from campaign MS
2. **Total impressions**: Use `total_impressions_this_hour`, not `paid_impressions_this_hour`
3. **Organic handling**: All ads participate, ads with budget=0 get pressure=0
4. **Pacing**: Calculated per day (resets daily)
5. **Charging**: Only charge if ad has remaining_budget > 0

## Risks / Trade-offs

### Risk 1: Pressure Formula Tuning
**Risk**: Pressure formula might not distribute budget evenly throughout the day, or might favor certain seller patterns unfairly

**Mitigation**:
- Formula is simple and explainable: `pressure = remaining_budget / time_left`
- Pacing gate prevents budget dumping in first hours
- `pacing_tolerance` parameter is configurable (test with 0.1, 0.2, 0.3)
- Test on multiple categories with different traffic patterns
- Visualize spending curves: should be roughly linear throughout day
- Compare with actual spending patterns from current system

### Risk 2: Simulation Runtime
**Risk**: Processing millions of impressions could be slow

**Mitigation**:
- Pre-aggregate impressions by category/hour
- Use vectorized operations (pandas/numpy)
- Cache database extracts locally
- Limit initial test to 1-2 high-traffic categories

**Target**: < 5 minutes for 1 day of 1 category

### Risk 3: All Ads Competing May Favor Large Sellers
**Risk**: Without Reach Profile limits, sellers with 100+ ads may dominate impressions even with same budget as small seller

**Mitigation**:
- This is EXPECTED behavior in MVP (validates current problem)
- Report will show this clearly in seller comparison table
- Future iteration can add eligibility constraints if needed
- Comparison report will help decide if limits are necessary

### Risk 4: Data Freshness
**Risk**: Yesterday's data may not represent today's behavior

**Mitigation**:
- Run simulation on multiple historical days
- Compare trends over time
- Document any known anomalies (e.g., holidays, system outages)
- Use weekday data for baseline comparisons

### Risk 5: False Positives in Fairness
**Risk**: Simulation shows "improvement" but doesn't account for relevance degradation

**Mitigation**:
- Non-goal for MVP: we're NOT optimizing buyer experience
- Document that fairness is ONE dimension (not only one)
- Follow-up work: add relevance scoring to auction

## Migration Plan

**Phase 1 (this proposal)**: Offline simulation
- Build simulator
- Run on historical data
- Generate comparison reports
- Present findings to stakeholders

**Phase 2 (future)**: Production preparation
- Refactor auction engine for real-time use
- Add monitoring and alerting
- Build A/B testing framework
- Gradual rollout (e.g., 1 category first)

**Phase 3 (future)**: Full rollout
- Migrate all categories
- Deprecate old PPV/Reach Profile logic
- Optimize performance at scale

**No rollback needed for Phase 1** (offline only).

## Open Questions

1. **Pacing tolerance value**: Is 0.2 (20% ahead) the right balance? Too strict might underdeliver, too loose might dump budget early. → Test with 0.1, 0.2, 0.3 and compare spending curves

2. **Epsilon value**: Is 0.001 small enough? Should it be relative to typical budgets? → Test edge cases when time_left approaches 0

3. **min_bid calculation**: Use same simulation period (time_from to time_to) for min_bid calculation → Simple, self-contained, no external dependencies

4. **Tie-breaking**: What if two ads have identical pressure? → Use secondary sort key (e.g., ad_id) for determinism

5. **Zero-budget handling**: What happens when all budgets depleted mid-hour? → Remaining slots go unpaid (organic impressions)

6. **Time granularity**: Should time_progress be hour-based or more granular (e.g., 15-min buckets)? → Start with hourly, can refine later

7. **Large seller advantage**: Should we limit how many ads per seller compete? → NOT in MVP; report will show if this is a problem

## Success Criteria

Simulation is successful if:
- ✅ Runs to completion on 1 day of data for 1 category
- ✅ Produces valid comparison tables (no crashes, no null values)
- ✅ Shows paid impressions going to ads with higher pressure (budget + urgency)
- ✅ Total impressions conserved (total_actual = total_simulated) using proportional organic fallback when needed
- ✅ Total simulated spending ≤ sum of all daily budgets (no budget overruns)
- ✅ Paid/organic split changes as expected (more ads have budget when they win)

**Next step**: Present findings to product/business team to decide on Phase 2.
