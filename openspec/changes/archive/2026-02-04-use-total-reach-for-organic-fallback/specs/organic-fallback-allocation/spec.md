# organic-fallback-allocation Specification Delta

**Change ID**: `use-total-reach-for-organic-fallback`
**Applies to**: `auction-engine` spec

## MODIFIED Requirements

### Requirement: Budget Deduction and State Update

The system SHALL update **simulated_reach counters** (not impression counters) after each batch.

#### Scenario: Increment reach counter on win

- **WHEN** ad wins auction and receives `allocated_reach` slots
- **THEN**
  - `ad.simulated_reach += allocated_reach`
  - `ad.remaining_budget -= cost`
  - `ad.actual_spend += cost`

#### Scenario: Organic reach fallback (MODIFIED)

- **WHEN** distributing remaining reach slots among simulated organic ads
- **THEN** use `ad.total_reach_historical` for proportional distribution
- **PREVIOUS**: Used `ad.organic_reach_historical` (only views with `campaign_show_ad != 'True'`)
- **RATIONALE**:
  - Ads popular when promoted should also receive organic reach when budget exhausts
  - Fixes 1,471 promoted-without-budget ads that had `organic_reach_historical=0`
  - Fixes 3,156 low-reach ads with floored proportions
  - Better reflects simulation goal: optimize reach distribution based on overall popularity
- **CONSISTENCY**: Proportional allocation based on total historical popularity
- **EXAMPLE**:
  - Ad A: `total_reach_historical=100`, `organic_reach_historical=0` (all promoted)
  - Ad B: `total_reach_historical=100`, `organic_reach_historical=100` (all organic)
  - Both receive equal proportions in organic fallback (fair distribution)

---

## ADDED Requirements

### Requirement: Total Reach Historical Tracking

The system SHALL track total historical reach (paid + organic) per ad for organic fallback allocation.

#### Scenario: Extract total reach from data

- **WHEN** initializing ads from `impressions_df`
- **THEN** system SHALL calculate `total_reach_historical = SUM(total_reach)` per ad
- **SOURCE**: `impressions_df` column `total_reach` (COUNT DISTINCT user_id per day)
- **USAGE**: Used as proportional allocation basis in organic fallback
- **STORAGE**: Stored in `Ad.total_reach_historical` field

#### Scenario: Promoted ads without budget records

- **WHEN** ad has views with `campaign_show_ad='True'` but NO budget in `budgets_df`
- **THEN**
  - Ad is classified as organic (`is_paid_actual=False`)
  - `total_reach_historical > 0` (has reach)
  - `organic_reach_historical = 0` (all views promoted)
  - Ad is eligible for organic fallback proportional to `total_reach_historical`
- **BEFORE FIX**: These 1,471 ads received 0 simulated reach (proportion=0)
- **AFTER FIX**: These ads receive ~27,248 reach proportionally distributed
- **RATIONALE**: Ads were popular when promoted, should receive organic reach when slots available

#### Scenario: Low-reach ads allocation

- **WHEN** ad has small `total_reach_historical` (e.g., 1-8 reach)
- **THEN**
  - Proportion = `total_reach_historical / sum(all_ads.total_reach_historical)`
  - Base allocation = `floor(remaining_slots × proportion)`
  - May still be 0 if proportion very small, but threshold higher than with `organic_reach_historical`
- **BEFORE FIX**: 3,156 ads with `organic_reach_historical` 1-8 got 0 reach
- **AFTER FIX**: More ads receive >0 allocation due to larger proportional base
- **EXAMPLE**:
  - `organic_reach_historical=3`, total=150,000 → proportion=0.00002 → floor(40×0.00002)=0
  - `total_reach_historical=10`, total=230,000 → proportion=0.000043 → floor(40×0.000043)=0
  - Still may be 0, but more likely to get remainder allocation

#### Scenario: Proportional distribution fairness

- **WHEN** calculating proportions for organic fallback
- **THEN** system SHALL use total popularity (paid + organic) as fairness metric
- **RATIONALE**:
  - Organic fallback represents **available slots when paid can't fill**
  - Should reflect **overall ad popularity**, not just historical organic segment
  - Paid ads with exhausted budgets deserve organic reach if they were popular
- **TRADE-OFF**: Pure-organic ads may receive slightly less reach (shared with more ads)
- **BENEFIT**: More accurate simulation of reach redistribution dynamics

---

## REMOVED Requirements

None. This change extends existing requirement, does not remove any.

---

## Implementation Notes

### Data Flow Changes

**Before:**
```
impressions_df['organic_reach']
  ↓ SUM per ad_id
organic_by_ad dict
  ↓
Ad.organic_reach_historical
  ↓
Organic fallback proportions
```

**After:**
```
impressions_df['total_reach']
  ↓ SUM per ad_id
total_reach_by_ad dict
  ↓
Ad.total_reach_historical
  ↓
Organic fallback proportions
```

### Field Semantics

**Old field**: `organic_reach_historical`
- Meaning: Historical reach with `campaign_show_ad != 'True'`
- Used for: Organic fallback proportions
- Problem: Excludes promoted ads, even if popular

**New field**: `total_reach_historical`
- Meaning: Historical reach (paid + organic), total popularity
- Used for: Organic fallback proportions
- Benefit: Includes all popular ads regardless of promotion status

### Conservation Property Preserved

- Organic fallback still guarantees `sum(allocations) == remaining_slots`
- Conservation holds regardless of proportion basis
- Algorithm unchanged, only input metric changes

### Backward Compatibility

**Breaking change**: Yes
- Field name changed: `organic_reach_historical` → `total_reach_historical`
- Organic distribution pattern changes (more ads participate)
- Simulation results will differ (expected improvement)

**Migration**: None needed (no persisted state, field internal to simulation)

---

## Testing Requirements

### Unit Tests

1. **Test: Promoted-without-budget ads receive allocation**
   - Setup: Ad with `total_reach_historical=100`, no budget
   - Run: Organic fallback with `remaining_slots=40`
   - Assert: Ad receives >0 allocation proportional to 100

2. **Test: Low-reach ads receive better allocation**
   - Setup: Ads with `total_reach_historical=[1,2,3,5,8]`
   - Run: Organic fallback with `remaining_slots=100`
   - Assert: More ads receive >0 than with `organic_reach_historical` basis

3. **Test: Proportional distribution respects total reach**
   - Setup: Ad A `total_reach=200`, Ad B `total_reach=100`
   - Run: Organic fallback with `remaining_slots=30`
   - Assert: Ad A receives ~20, Ad B receives ~10

4. **Test: Conservation holds with new metric**
   - Setup: Various `total_reach_historical` distributions
   - Run: Organic fallback with varying `remaining_slots`
   - Assert: `sum(allocations) == remaining_slots` always

### Integration Tests

1. **Test: Full simulation shows improvement**
   - Run: Simulation on 2026-01-31 to 2026-02-01
   - Assert:
     - Organic ads with reach: >7,000 (was 3,639)
     - Ads with zero reach: <1,500 (was 4,627)
     - Conservation: `total_simulated == total_actual`

2. **Test: Promoted-without-budget pattern fixed**
   - Query: Ads with `is_paid_actual=False AND actual_reach_organic=0`
   - Assert: `simulated_reach_total > 0` for majority
   - Expected: ~27,248 total reach allocated

---

## Validation Criteria

### Functional Validation

- [ ] Organic fallback uses `total_reach_historical` field
- [ ] Data extraction calculates `total_reach_historical` correctly
- [ ] Ad model has `total_reach_historical` field
- [ ] All references to `organic_reach_historical` removed or updated

### Performance Validation

- [ ] Simulation runtime unchanged (<5% variance)
- [ ] Memory usage unchanged
- [ ] No new performance bottlenecks

### Accuracy Validation

- [ ] Organic ads with simulated reach increases by >3,000
- [ ] Promoted-without-budget ads (1,471) receive reach
- [ ] Conservation property holds across all simulations
- [ ] No regressions in paid reach accuracy

---

## References

- **Related spec**: [auction-engine](../../../../specs/auction-engine/spec.md)
- **Implementation**:
  - [simulation.py:52](../../../../../auction-simulator/src/auction_simulator/simulation.py#L52)
  - [auction_engine.py:379-473](../../../../../auction-simulator/src/auction_simulator/auction_engine.py#L379-L473)
  - [models/ad.py](../../../../../auction-simulator/src/auction_simulator/models/ad.py)
- **Related change**: [adjust-bid-step-for-organic-balance](../../../adjust-bid-step-for-organic-balance/)
