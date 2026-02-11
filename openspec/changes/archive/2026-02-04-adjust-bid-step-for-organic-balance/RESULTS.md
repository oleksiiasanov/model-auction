# Validation Results: bid_step = 0.003

**Date**: 2026-02-02
**Status**: ❌ **FAILED** - Organic fallback still not working
**Config**: bid_step changed from 0.001 to 0.003 (3x increase)

## Summary

The bid_step increase from 0.001 to 0.003 did **NOT** fix the organic fallback problem. The paid auction still fills 100% of available slots.

## Key Metrics

| Metric | Baseline (0.001) | Proposed (0.003) | Change | Target |
|--------|-----------------|------------------|---------|---------|
| **Paid reach** | 233,806 (100%) | 233,806 (100%) | 0% | 81,152 (35%) ❌ |
| **Organic reach** | 0 (0%) | 0 (0%) | 0% | 152,654 (65%) ❌ |
| **Organic ads with reach** | 39 (0.5%) | 39 (0.5%) | 0% | 6,795 (100%) ❌ |
| **Total spending** | 154.58 AZN | 195.57 AZN | +27% | 190 AZN ✅ |
| **Avg cost per slot** | 0.066 kopecks | 0.084 kopecks | +27% | 0.234 kopecks ❌ |
| **Budget exhaustions** | N/A | 2 events | - | Many ❌ |

## What Happened

### Bid Configuration
✅ **bid_step = 0.003 was correctly applied**
- Confirmed in config files
- Verified in auction logs (bid differences = 0.003 between ranks)

### Auction Behavior
❌ **Paid auction filled ALL slots before organic fallback triggered**

From simulation logs:
```
Hour 0: total_allocated=49,806, paid_slots=49,806, organic_slots=0
Hour 5: total_allocated=7,563, paid_slots=7,563, organic_slots=0
Hour 10: total_allocated=4,743, paid_slots=4,743, organic_slots=0
...
Hour 23: total_allocated=1,405, paid_slots=1,405, organic_slots=0

Total: 233,806 paid slots, 0 organic slots
```

### Why It Failed

**Root cause: Dynamic auction effects dominate static bid calculation**

The proposal's analysis assumed:
- Static N = 113 throughout simulation
- Fixed bids per ad
- Average bid = 0.238 kopecks → budget buys 96,662 slots → 59% left for organic

**Reality:**
- Actual avg cost per slot: 0.084 kopecks (not 0.238!)
- Why so low?
  1. **Pressure decay**: As ads win reach, pressure drops → bids drop in next batch
  2. **Pacing gate**: Blocks high-pressure ads → reduces competition
  3. **Few exhaustions**: Only 2 ads exhausted budget → N stayed high → but bids stayed low
  4. **Dynamic N**: N ranged from 78-114 (avg 96.2) but effective competition much lower

**Result:**
- 195.57 AZN @ 0.084 kopecks/slot → can buy 232,738 slots (99% of total!)
- Budget exhausts just before filling all slots → no room for organic

## Detailed Analysis

### Budget Dynamics
```
Total budget available: 230.25 AZN (23,025 kopecks)
Actual spending: 195.57 AZN (19,557 kopecks) - 84.9% utilization
Reach allocated: 233,806 slots

Theoretical avg bid (N=96, bid_step=0.003):
  avg_bid = min_bid + (N-1) × bid_step / 2
  avg_bid = 0.0662 + 95 × 0.0015 = 0.209 kopecks

Actual avg cost:
  avg_cost = 19,557 / 233,806 = 0.084 kopecks (40% of theoretical!)
```

### Bid Values Observed
From auction logs:
```
Hour 0, Batch 1:
  Rank 0: bid = 0.300 kopecks (top)
  Rank 1: bid = 0.297 kopecks
  Rank 2: bid = 0.294 kopecks
  Step: 0.003 ✅

Hour 23, Batch 1:
  Top bids still: 0.297-0.300 kopecks
  (High bids persist, but not enough ads exhaust)
```

**Observation:** Top bids are high (~0.30 kopecks), but:
- Only top-ranked ads pay high bids
- Lower-ranked winners pay much less
- Many batches have reduced competition (N effective < N nominal)
- Average across all winners is LOW

### Organic Fallback Trigger

**Condition:** `if paid_slots < total_slots` then distribute organic
**Result:** Condition NEVER true (paid always fills 100%)

**Why?**
Auction loop runs until:
1. `slots_allocated >= total_slots` ← THIS happens first
2. OR `ads_with_budget == 0` ← Only 2 ads exhausted
3. OR `couldn't fill batch` ← Didn't happen

## Why Proposal's Math Was Wrong

**Proposal assumed:**
```
N = 113 fixed throughout
avg_bid = 0.238 kopecks
Budget of 190 AZN can buy: 190 × 100 / 0.238 = 79,811 slots (34%)
→ Organic gets 154,995 slots (66%)
```

**Reality:**
```
N = 78-114 (avg 96.2) but effective competition lower
avg_cost = 0.084 kopecks (due to pressure decay + pacing)
Budget of 195.57 AZN can buy: 195.57 × 100 / 0.084 = 232,738 slots (99.5%)
→ Organic gets 0 slots (0%)
```

**The gap:** Pressure-based bidding with pacing creates much lower effective costs than the static formula predicts.

## Comparison with Baseline

| Aspect | Baseline (0.001) | This Test (0.003) | Change |
|--------|-----------------|-------------------|--------|
| bid_step | 0.001 | 0.003 | 3x |
| Top bids | ~0.14 kop | ~0.30 kop | 2.1x |
| Avg cost/slot | 0.066 kop | 0.084 kop | +27% |
| Spending | 154.58 AZN | 195.57 AZN | +27% |
| Paid reach | 100% | 100% | No change |
| Organic reach | 0% | 0% | No change |
| Organic ads | 39 | 39 | No change |

**Conclusion:** bid_step=0.003 increased spending by 27% but did NOT change paid/organic split.

## Next Steps

### Option 1: Much Higher bid_step (0.01-0.05)
**Pros:**
- Forces budget exhaustion through high bids
- May work if pressure decay effect can be overcome

**Cons:**
- Will overpay significantly (2-10x actual cost)
- Spending accuracy will be poor
- May not match production behavior

**Recommendation:** Test bid_step=0.01 (10x baseline) to see if organic fallback triggers

### Option 2: Cap Total Paid Reach (New Mechanic)
**Approach:**
- Add config: `max_paid_reach_pct: 0.40` (40% of slots)
- Force auction to stop when paid_slots >= max_paid_reach_pct × total_slots
- Trigger organic fallback for remainder

**Pros:**
- Direct control over paid/organic split
- Matches actual behavior (production has implicit cap)
- Doesn't rely on bid mechanics

**Cons:**
- New logic to implement
- May not reflect actual auction dynamics
- Artificial constraint

**Recommendation:** Prototype this approach if bid_step alone fails

### Option 3: Revise Pressure Calculation
**Approach:**
- Penalize pressure decay more aggressively
- Force ads to maintain high pressure even after winning reach
- Example: `pressure = remaining_budget / max(time_left, 0.1)` (higher minimum)

**Pros:**
- Maintains high competition throughout day
- May lead to faster budget exhaustion

**Cons:**
- Changes core auction mechanic
- May not match production behavior
- Unclear if it will work

### Option 4: Accept Current Behavior
**Approach:**
- Accept that simulation fills all slots with paid
- Focus on other metrics (spending accuracy, bid dynamics)

**Pros:**
- No code changes needed
- Spending accuracy improved (195 AZN vs 190 actual)

**Cons:**
- Organic reach simulation is broken
- Can't validate organic fallback mechanism
- 99.5% of organic ads get zero reach

## Recommendation

**Try Option 1 first: bid_step = 0.01 (10x baseline)**

**Rationale:**
- Simple config change (no code changes)
- Will definitively test if bid_step alone can work
- Expected result: Spending ~500+ AZN, paid reach ~50k (21%), organic ~183k (79%)
- If this works, can tune down to find optimal value (e.g., 0.007)

**If Option 1 fails (organic still 0%):**
- Move to Option 2: Implement max_paid_reach_pct cap
- This gives direct control and guaranteed organic fallback

## Files Modified

- `auction-simulator/config/config.yaml:19` - bid_step: 0.001 → 0.003
- `auction-simulator/config/local.yaml:20` - bid_step: 0.001 → 0.003

## Test Command

```bash
cd auction-simulator
python -m auction_simulator.cli simulate \
  --country 13 --categories 1361 \
  --time-from 2026-01-31 --time-to 2026-02-01 \
  --no-cache
```

## Logs

- Simulation log: `outputs/simulation_log_20260202_170011.jsonl`
- Ad comparison: `outputs/ad_comparison_20260202_170057.csv`
- Summary: `outputs/summary_statistics_20260202_170057.txt`
