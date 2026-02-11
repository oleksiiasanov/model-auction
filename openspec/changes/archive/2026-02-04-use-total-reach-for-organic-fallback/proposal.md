# Proposal: Use total_reach_historical for Organic Fallback Allocation

**Change ID**: `use-total-reach-for-organic-fallback`
**Status**: Implemented
**Created**: 2026-02-04
**Implemented**: 2026-02-04
**Type**: Enhancement / Bug Fix

## Why

Current organic fallback mechanism uses `organic_reach_historical` (views with `campaign_show_ad != 'True'`) for proportional allocation, causing 4,627 ads (56% of organic ads) to receive zero simulated reach.

**Data inconsistency discovered:**
- **1,471 ads** promoted (`campaign_show_ad='True'`) but have NO budget records
  - These have `organic_reach_historical = 0` → proportion = 0 → receive 0 simulated reach
  - Total missed reach: 27,248 (11.6% of total)
  - Average reach per ad: 18.5

- **3,156 low-reach organic ads** with `organic_reach_historical` too small (mean=3.8, median=3)
  - Proportions like 3/150,000 = 0.00002
  - floor(40 × 0.00002) = 0 → receive 0 simulated reach
  - Total missed reach: 12,145

**Total impact:** 4,627 ads (56% of organic) get zero simulated reach despite having actual reach.

## Problem Analysis

### Current Implementation

**Data extraction** ([simulation.py:52](../../auction-simulator/src/auction_simulator/simulation.py#L52)):
```python
organic_by_ad = impressions_df.groupby('ad_id')['organic_reach'].sum().to_dict()
```

**Organic fallback** ([auction_engine.py:411](../../auction-simulator/src/auction_simulator/auction_engine.py#L411)):
```python
total_organic = sum(ad.organic_reach_historical for ad in ads)
proportion = ad.organic_reach_historical / total_organic
base = math.floor(remaining_slots * proportion)
```

### Root Causes

1. **Promoted ads without budget records:**
   - 1,471 ads have all views with `campaign_show_ad='True'`
   - But NO records in `spendings_distributed` table
   - Classified as organic ads (`is_paid_actual=False`)
   - But `organic_reach_historical=0` because all views were promoted
   - **Result:** Excluded from organic fallback distribution

2. **Low-reach ads get floored to zero:**
   - 3,156 ads with small `organic_reach_historical` (1-8)
   - Proportional allocation: `floor(40 × 0.00002) = 0`
   - **Result:** Never allocated any slots despite having actual reach

3. **Conceptual mismatch:**
   - Organic fallback represents **slots available when paid auction can't fill**
   - Should distribute based on **overall popularity** (`total_reach_historical`)
   - Not based on **historical organic-only reach** (`organic_reach_historical`)
   - Ads popular when promoted should also get organic reach when budget exhausts

### Evidence from Latest Simulation

**Organic ads without simulated reach (4,627 ads):**

| Pattern | Count | Total Actual Reach | Reason |
|---------|-------|-------------------|---------|
| Promoted without budget | 1,471 | 27,248 | `organic_reach_historical=0` |
| Low-reach organic | 3,156 | 12,145 | Proportion too small |
| **Total** | **4,627** | **39,393** | **16.8% of total reach** |

**Distribution comparison:**

| Metric | Current (organic_reach) | Proposed (total_reach) |
|--------|------------------------|------------------------|
| Ads receiving organic reach | 3,639 (44%) | ~7,000+ (85%+) |
| Ads with zero simulated reach | 4,627 (56%) | ~1,200 (15%) |
| Reach allocated to promoted-without-budget | 0 | ~27,248 |
| Reach allocated to low-reach ads | ~0 | ~12,000+ |

## What Changes

**Use `total_reach_historical` instead of `organic_reach_historical` for organic fallback proportional allocation.**

### Code Changes

**1. Data extraction** (`simulation.py`):
```python
# OLD:
organic_by_ad = impressions_df.groupby('ad_id')['organic_reach'].sum().to_dict()

# NEW:
total_reach_by_ad = impressions_df.groupby('ad_id')['total_reach'].sum().to_dict()
```

**2. Ad initialization** (`simulation.py`):
```python
# OLD:
organic_reach_historical=organic_by_ad.get(ad_id, 0),

# NEW:
total_reach_historical=total_reach_by_ad.get(ad_id, 0),
```

**3. Ad class** (`models/ad.py`):
```python
# OLD:
organic_reach_historical: int = 0

# NEW:
total_reach_historical: int = 0  # Used for organic fallback proportions
```

**4. Organic fallback** (`auction_engine.py`):
```python
# OLD:
total_organic = sum(ad.organic_reach_historical for ad in ads)
proportion = ad.organic_reach_historical / total_organic

# NEW:
total_reach_sum = sum(ad.total_reach_historical for ad in ads)
proportion = ad.total_reach_historical / total_reach_sum
```

### Affected Files

- `auction-simulator/src/auction_simulator/simulation.py` (2 changes)
- `auction-simulator/src/auction_simulator/models/ad.py` (1 field rename)
- `auction-simulator/src/auction_simulator/auction_engine.py` (2 changes)

## Expected Impact

### Positive Outcomes

1. **1,471 promoted-without-budget ads now get reach:**
   - Previously: 0 simulated reach
   - After fix: ~27,248 reach distributed proportionally
   - These ads were popular when promoted → deserve organic reach when slots available

2. **3,156 low-reach ads get better allocation:**
   - Previously: floor(40 × 0.00002) = 0
   - After fix: Proportions based on larger `total_reach` values
   - Still may get 0 if proportion too small, but threshold is higher

3. **Organic fallback more accurate:**
   - Reflects overall ad popularity, not just organic-only popularity
   - Better alignment with simulation goal: optimize reach distribution

4. **Coverage improvement:**
   - Organic ads with simulated reach: 3,639 (44%) → ~7,000+ (85%+)
   - Reduction in zero-reach ads: 4,627 (56%) → ~1,200 (15%)

### Trade-offs

**⚠️ Changes organic distribution pattern:**
- Previously: Only ads with historical organic views participate
- After fix: All ads with any historical reach participate
- **Rationale:** This better reflects production behavior where popular paid ads can also receive organic reach when budget exhausts

**⚠️ May slightly reduce organic reach for pure-organic ads:**
- Total slots remain same (conservation guarantee)
- Adding 1,471 promoted ads to distribution → shares slots among more ads
- Pure-organic ads may get slightly less reach
- **Rationale:** This is fairer - promoted ads were popular and deserve organic reach when budget gone

## Alternatives Considered

### Alt 1: Keep organic_reach, add min_proportion threshold
- **Idea:** If `proportion < threshold`, round up to `min_proportion`
- **Advantages:** Ensures low-reach ads get some allocation
- **Disadvantages:**
  - Doesn't fix promoted-without-budget issue
  - Violates conservation (need to adjust other proportions)
  - Arbitrary threshold selection
- **Why not chosen:** Doesn't address root cause

### Alt 2: Use equal distribution instead of proportional
- **Idea:** Distribute remaining slots equally: `remaining_slots / num_ads`
- **Advantages:** Every ad gets some reach
- **Disadvantages:**
  - Loses historical popularity signal
  - Popular ads get same as unpopular ads (unrealistic)
  - Already exists as fallback for `total_organic=0` case
- **Why not chosen:** Proportional distribution is more realistic

### Alt 3: Two-tier fallback (organic_reach, then total_reach)
- **Idea:**
  1. First distribute to ads with `organic_reach > 0` using `organic_reach_historical`
  2. If slots remain, distribute to promoted-without-budget using `total_reach_historical`
- **Advantages:** Preserves priority for pure-organic ads
- **Disadvantages:**
  - Complex implementation (two allocation passes)
  - Doesn't fix low-reach flooring issue
  - Promotes ads only get "leftover" slots (less fair)
- **Why not chosen:** Adds complexity without clear benefit

### Alt 4: Investigate and fix data inconsistency
- **Idea:** Understand why 1,471 ads promoted without budget records, fix data extraction
- **Advantages:** Addresses data quality issue at source
- **Disadvantages:**
  - May be legitimate (free promotions, expired campaigns, data lag)
  - Doesn't fix low-reach flooring issue
  - Still need proportional allocation fix
- **Why not chosen:** Not mutually exclusive, can do both

## Validation Strategy

### Test 1: Run simulation with fix
```bash
cd auction-simulator
python -m auction_simulator.cli simulate \
  --country 16 --categories 1361 \
  --time-from 2026-01-31 --time-to 2026-02-01 \
  --no-cache
```

**Verify:**
- ✅ Organic ads with reach: ~7,000+ (was 3,639)
- ✅ Ads with zero reach: ~1,200 (was 4,627)
- ✅ Conservation: `sum(simulated_reach) == sum(actual_reach_total)`

### Test 2: Check promoted-without-budget ads
```python
import pandas as pd
df = pd.read_csv('outputs/ad_comparison_*.csv', comment='#')

# Ads promoted without budget
promoted_no_budget = df[
    (df['is_paid_actual'] == False) &
    (df['actual_reach_organic'] == 0) &
    (df['actual_reach_total'] > 0)
]

print(f"Ads: {len(promoted_no_budget)}")
print(f"Simulated reach: {promoted_no_budget['simulated_reach_total'].sum()}")
# Should be > 0 (was 0)
```

### Test 3: Check low-reach ads
```python
# Low-reach organic ads (1-8 reach)
low_reach = df[
    (df['is_paid_actual'] == False) &
    (df['actual_reach_organic'].between(1, 8))
]

print(f"Ads with simulated reach: {(low_reach['simulated_reach_total'] > 0).sum()}")
# Should be higher than before
```

### Test 4: Validate conservation
```python
total_actual = df['actual_reach_total'].sum()
total_simulated = df['simulated_reach_total'].sum()
assert total_actual == total_simulated, "Conservation violated!"
```

## Risk Assessment

**Risk Level:** Low

**Risks:**

1. **Changes organic distribution pattern**
   - **Impact:** Organic ads may receive different reach amounts
   - **Mitigation:** This is intended behavior - better reflects reality
   - **Severity:** Low (improves accuracy)

2. **Pure-organic ads may get slightly less reach**
   - **Impact:** 6,795 pure-organic ads now share slots with 1,471 promoted ads
   - **Mitigation:** Total organic slots unchanged, just redistributed more fairly
   - **Severity:** Low (minor redistribution)

3. **Implementation error risk**
   - **Impact:** If `total_reach_historical` not calculated correctly, could break fallback
   - **Mitigation:** Add validation tests, check conservation property
   - **Severity:** Medium (caught by tests)

**Rollback:** Simple (revert 5 lines across 3 files)

## Recommendation

**Proceed with this change.** ✅

**Rationale:**
- Fixes critical issue where 4,627 ads (56%) get zero reach
- More accurate simulation of organic reach distribution
- Conceptually correct: popular ads deserve organic reach regardless of budget
- Low risk, easy rollback
- Aligns with simulation goal: optimize reach distribution, not just match historical

**No alternatives needed:** This is the straightforward fix for the root cause.

## References

- Issue discovered: 2026-02-04 during organic reach analysis
- Related: [adjust-bid-step-for-organic-balance](../adjust-bid-step-for-organic-balance/)
- Data extraction: [simulation.py:52](../../auction-simulator/src/auction_simulator/simulation.py#L52)
- Organic fallback: [auction_engine.py:379-473](../../auction-simulator/src/auction_simulator/auction_engine.py#L379-L473)
- Ad model: [models/ad.py](../../auction-simulator/src/auction_simulator/models/ad.py)
