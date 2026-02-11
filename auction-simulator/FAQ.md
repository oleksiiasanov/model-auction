# Auction Simulator - Frequently Asked Questions

## General Questions

### What is the Auction Simulator?

The Auction Simulator recreates the ad auction mechanism to predict reach distribution and spending for advertising campaigns. It uses historical data (reach, budgets, spending) to simulate how ads would perform under different auction parameters.

### Why simulate instead of using actual production data?

Simulation allows us to:
- Test different bid step values before deploying to production
- Understand how parameter changes affect reach distribution and spending
- Validate auction mechanics before implementation
- Compare simulated vs actual to identify discrepancies

### What does "reach" mean in this context?

**Reach** = COUNT(DISTINCT user_id) per ad per day

This is different from:
- **Impressions**: COUNT(*) of all views including repeats
- **Unique Users**: COUNT(DISTINCT user_id) globally across all ads

Example: If user123 sees ad_A three times, that's 3 impressions but 1 reach.

---

## Simulation Mechanics

### How does the auction work?

**Paid Auction** (for ads with budget > 0):
1. Calculate pressure: `remaining_budget / time_left`
2. Apply pacing gate: Block ads spending too fast
3. Rank by pressure (highest first)
4. Calculate effective bid: `min_bid + (N-1-rank) × bid_step`
5. Select top N winners for available slots
6. Charge winners, update budgets

**Organic Fallback** (when paid can't fill batch):
1. Paid auction runs first within each batch (40 slots)
2. If paid ads fill < 40 slots, remaining slots filled via organic fallback
3. Process continues for all batches until hour complete
4. Distribute organically using **pool split** (80% free ads, 20% paid-exhausted ads) with **cumulative allocator** for proportional distribution based on historical total reach (paid + organic)

### What is the "organic fallback"?

**IMPORTANT**: Organic fallback is **simulation-only**. In production, organic reach happens naturally through user behavior, not algorithmically.

In simulation, when paid auction can't fill all available reach slots (budget exhausted), remaining slots are distributed using a **pool split** mechanism:

1. **Pool Split**: Slots are divided between two pools:
   - **80% slots** → Free ads (`daily_budget=0`)
   - **20% slots** → Paid-exhausted ads (`daily_budget>0` but `remaining_budget=0`)

2. **Cumulative Allocator**: Each pool uses a cumulative carry-over allocator that:
   - Distributes proportionally based on **historical total reach (paid + organic)**
   - Preserves fractional allocations across batches (carry-over state)
   - Significantly improves coverage for long-tail ads (ads with small historical reach)

3. **Reassignment**: If one pool is empty, its slots are reassigned to the other pool to guarantee conservation.

This ensures ads that were popular when promoted also receive organic reach when budget exhausts, reflecting overall ad popularity rather than only historical organic views.

**Example** (simplified, without cumulative carry-over):
```
Remaining slots: 18
Pool split: 14 free slots (80%), 4 paid-exhausted slots (20%)

Free ads (historical total reach):
- ad_1: 420
- ad_2: 210
- ad_3: 630
Total: 1260

Free allocation:
- ad_1: 14 × (420/1260) = 4.67 → 4 (floor) + carry 0.67
- ad_2: 14 × (210/1260) = 2.33 → 2 (floor) + carry 0.33
- ad_3: 14 × (630/1260) = 7.00 → 7 (floor) + carry 0.00

Paid-exhausted ads: Similar proportional allocation for 4 slots
```

### What is bid_step and why does it matter?

`bid_step` controls the bid increment between rank positions:
```
effective_bid = min_bid + (N - 1 - rank) × bid_step
```

**Impact**:
- **Low bid_step (0.001)**: Cheap bids → budget lasts long → paid fills all slots → no organic
- **High bid_step (0.01)**: Expensive bids → budget exhausts fast → organic gets slots
- **Current (0.003)**: Balanced spending + organic coverage (recommended range: 0.003-0.005)

### What is the pacing gate?

Pacing gate prevents ads from spending budget too quickly:
```
expected_spend = daily_budget × time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)

if actual_spend > max_allowed:
    pressure = 0  # Block from auction
```

**Purpose**: Spread spending throughout the day, not exhaust in first hour

**Hour 0 Fix**: At hour 0, `time_progress=0` would cause `max_allowed=0`, blocking all ads. The simulator uses `min_time_progress_threshold=0.042` (1 hour) to prevent this edge case.

### Why do paid ads participate in multiple batches per hour?

**Question**: If there are only 4 paid ads but batch_size is 40, shouldn't the auction stop after 1 batch?

**Answer**: No! The auction continues processing batches until all hourly slots are allocated OR all paid ads exhaust their budget.

**How it works**:
```
Hour 10: 132 total slots, batch_size=40, 4 paid ads with budget

Batch 1:
  - Paid auction: 4 ads buy 1 reach each = 4 slots
  - Organic fallback: Fills remaining 36 slots
  - Total: 40 slots allocated

Batch 2: (CONTINUES!)
  - Paid auction: Same 4 ads buy 1 reach each = 4 slots
  - Organic fallback: Fills remaining 36 slots
  - Total: 80 slots allocated

Batch 3:
  - Paid auction: 4 slots
  - Organic fallback: 36 slots
  - Total: 120 slots allocated

Batch 4:
  - Paid auction: 4 slots
  - Organic fallback: 8 slots (only 12 remain)
  - Total: 132 slots allocated ✓

Result: 4 batches × 4 paid reach = 16 paid reach per hour
```

**Why this matters**:
- Without this, paid ads would only participate in 1 batch per hour
- Budget utilization would drop to ~3% (only 16 reach instead of thousands)
- Organic reach would be inflated (10,400 instead of 8,500)
- Ads with budget would still have unused funds

**Fixed in**: [fix-batch-auction-early-termination](../../openspec/changes/fix-batch-auction-early-termination/)

### How does organic pool split work?

**Pool Split Mechanism**:
- **80% slots** → Free ads (`daily_budget=0`)
- **20% slots** → Paid-exhausted ads (`daily_budget>0` but `remaining_budget=0`)
- Configurable via `organic_fallback.free_share` in config.yaml

**Cumulative Allocator**:
- Preserves fractional allocations across batches using carry-over state
- Improves coverage for long-tail ads (ads with small historical reach)
- Uses two carry states: `carry_free` and `carry_paid_exhausted`
- Algorithm: `carry[ad_id] += slots × proportion`, then `floor(carry[ad_id])` for allocation

**Reassignment Logic**:
- If free pool is empty → reassign slots to paid-exhausted pool
- If paid-exhausted pool is empty → reassign slots to free pool
- Guarantees conservation (all slots allocated)

**Why Pool Split?**
- Paid-exhausted ads (previously promoted) deserve some organic reach
- Free ads get majority share (80%) as they have no paid history
- Better reflects production behavior where promoted ads retain some visibility

---

## Data and Configuration

### What data does the simulator use?

**Input Data** (from ClickHouse + PostgreSQL):
- Historical reach per ad per hour (`total_reach`, `organic_reach`)
- Budget data per ad per day (`daily_budget`, `actual_spend`)
- Min bid per category (calculated from production data)

**Configuration**:
- `bid_step`: Kopecks increment between ranks
- `pacing_tolerance`: % allowed above expected spend (default 0.2 = 20%)
- `batch_size`: Slots allocated per auction batch (default 40)

### What are "kopecks"?

Kopecks = 1/100 of a currency unit (like cents to dollars)
- 1 AZN = 100 kopecks
- All internal calculations in kopecks (fractional kopecks supported)
- Converted to AZN only for reports

Example: `bid_step=0.003` = 0.003 kopecks = 0.00003 AZN

**Note**: Budgets support fractional kopecks (stored as `float`) to prevent rounding errors with small bid steps.

### How is min_bid calculated?

From production data:
```sql
price_per_day::float / fact_impression AS min_bid_kopecks
```

This represents the minimum cost per reach based on historical spending patterns.

---

## Results and Metrics

### What metrics are in the summary report?

**Reach Metrics**:
- Total Reach: All reach allocated (should equal actual)
- Paid Reach: Reach won through auction
- Organic Reach: Reach distributed through organic fallback

**Spending Metrics**:
- Total Spending: Sum of all ad spending
- Budget Utilization: % of planned budget spent
- Cost per Reach: Spending / Reach

**Coverage Metrics**:
- Ads with Reach: How many ads received any reach
- Organic ads coverage: % of free ads that got reach

**Per-Ad Statistics (NEW)**:
- Mean reach per ad (paid vs organic)
- Median reach per ad (paid vs organic)

### What is a good simulation result?

**Target Metrics**:
- ✅ Spending: 80-95% of planned budget
- ✅ Paid reach: 30-40% of total (close to actual 35%)
- ✅ Organic reach: 60-70% of total (close to actual 65%)
- ✅ Organic ads coverage: 50%+ receive reach
- ✅ Organic fallback: Active in 90%+ of hours

**Warning Signs**:
- ⚠️ Paid fills 100% of slots → bid_step too low
- ⚠️ Paid <20% of slots → bid_step too high
- ⚠️ Spending <70% → too conservative
- ⚠️ Spending >110% → too aggressive

### Why doesn't simulated match actual exactly?

**Expected Differences**:
- Auction is probabilistic (tie-breaking, rounding)
- Pacing gate is approximate (not exact production logic)
- Historical organic reach is a proxy for production behavior
- Production has additional factors not in simulation (user engagement, ad quality, etc.)

**Goal**: Get **directionally correct** (within 10-20%), not exact match.

---

## Troubleshooting

### "Organic ads have reach but spending=0"

✅ **This is correct!** Organic reach is free. Ads receive reach through organic fallback mechanism without paying.

### "Zero-budget ads winning auction slots"

🔴 **This was Bug #1!** Fixed in commit [date].

**Symptom**: Ads with `simulated_spending=0` have large `simulated_reach` values.

**Cause**: `run_batch_auction()` received all ads instead of only `ads_with_budget`.

**Fix**: Changed `simulation.py:387` to pass `ads_with_budget` instead of `ads`.

See [CRITICAL_BUGS.md](CRITICAL_BUGS.md) for full details.

### "Organic fallback never triggers"

**Possible Causes**:
1. `bid_step` too low → paid auction fills all slots
   - **Solution**: Increase bid_step (try 0.005 or 0.01)

2. Budget too high → ads never exhaust
   - **Solution**: Check actual budget utilization (~82%), adjust if needed

3. Pacing gate too loose → ads spend too fast in first hours
   - **Solution**: Decrease `pacing_tolerance` (try 0.1 instead of 0.2)

### "Spending accuracy is off"

**If spending too high (>110%)**:
- Decrease `bid_step` (e.g., 0.003 → 0.002)
- Increase `pacing_tolerance` (e.g., 0.2 → 0.3)

**If spending too low (<70%)**:
- Increase `bid_step` (e.g., 0.003 → 0.005)
- Decrease `pacing_tolerance` (e.g., 0.2 → 0.15)

### "Simulation is slow"

**Optimization Tips**:
- Use `--cache` flag to cache data extraction (only re-extracts if params change)
- Reduce `batch_size` for faster processing (trade-off: less accurate)
- Filter to specific categories instead of all (`--categories 1361`)
- Use date range of 1-2 days instead of weeks

---

## Known Issues and Limitations

### 1. Organic Fallback is Simulation-Only

**Limitation**: In simulation, organic reach is distributed algorithmically by historical proportions. In production, organic reach happens naturally through user behavior.

**Impact**: Simulated organic distribution may not exactly match production patterns.

**Mitigation**: Use historical total reach (paid + organic) as the basis for proportions, which reflects overall ad popularity. Pool split (80%/20%) ensures paid-exhausted ads also receive organic reach.

### 2. Pacing Gate Approximation

**Limitation**: Simulator uses simplified pacing logic. Production may have more sophisticated pacing algorithms.

**Impact**: Spending patterns may differ slightly from production.

**Mitigation**: Tune `pacing_tolerance` parameter to match observed production behavior.

### 3. No User Engagement Modeling

**Limitation**: Simulator doesn't model user engagement, ad quality scores, or other factors affecting reach.

**Impact**: Reach distribution is based on historical patterns, not predicted user behavior.

**Mitigation**: Historical data inherently includes engagement patterns, so simulation reflects realistic distributions.

---

## Critical Bugs Reference

For detailed information about critical bugs discovered and fixed during development, see [CRITICAL_BUGS.md](CRITICAL_BUGS.md).

**Summary of Fixed Bugs**:

### Bug #1: Zero-Budget Ads Winning Paid Auction (Fixed 2026-02-04)
- **Impact**: 78% of reach incorrectly distributed
- **Cause**: Passed all ads to auction instead of only ads_with_budget
- **Fix**: Changed simulation.py:387
- **Improvement**: 17.8x more organic ads coverage, 280x more organic fallback slots

### Bug #2: Batch Auction Early Termination (Fixed 2026-02-04)
- **Impact**: Budget utilization only 3.3% (should be 46.9%+)
- **Cause**: Early break when paid ads < batch_size
- **Fix**: Removed early break, organic fallback now per-batch
- **Improvement**: Budget utilization 3.3% → 46.9% (+1,318%)

### Bug #3: Organic Fallback Used Wrong Metric (Fixed 2026-02-04)
- **Impact**: 1,471 promoted-without-budget ads received 0 reach
- **Cause**: Used `organic_reach_historical` instead of `total_reach_historical`
- **Fix**: Changed to `total_reach_historical` for proportional distribution
- **Improvement**: 1,471 ads now receive reach (100% coverage)

### Bug #4: Pacing Gate Hour Zero Blocking (Fixed 2026-01-30)
- **Impact**: 98.5% paid vs 3.6% actual (27x inflation)
- **Cause**: `time_progress=0` at hour 0 caused `max_allowed=0`
- **Fix**: Added `min_time_progress_threshold=0.042`
- **Improvement**: Paid impressions corrected from 98.5% → ~3.6%

### Bug #5: Fractional Kopecks Rounding (Fixed 2026-01-30)
- **Impact**: Budgets not decreasing (rounding to 0 kopecks)
- **Cause**: Integer rounding with small bid_step values
- **Fix**: Changed `daily_budget` and `remaining_budget` from `int` to `float`
- **Improvement**: Budgets now decrease correctly, N decreases naturally

[View full bug details →](CRITICAL_BUGS.md)

---

## Contact and Support

For questions, issues, or feature requests:
- GitHub Issues: [repository link]
- Documentation: See project README and OpenSpec docs
- Code Comments: Inline documentation in source files

---

**Last Updated**: 2026-02-05
