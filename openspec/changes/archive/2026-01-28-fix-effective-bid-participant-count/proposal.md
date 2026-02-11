# Proposal: Fix Effective Bid Participant Count

## Why

**Problem:** The effective_bid calculation includes ALL ads (including those with budget=0) in the participant count N, causing artificially inflated bids and simulated spending 9-10x higher than actual.

**Current behavior:**
```python
# auction_engine.py:186
N = len(ranked_ads)  # N = ALL ads (~8,391)
effective_bid = min_bid + (N - 1 - rank_index) * bid_step
```

When N includes ads without budget:
- For min_bid=0.0705 kopecks, bid_step=0.1, N=8,391 ads
- Top rank ad pays: `0.0705 + (8,391 - 1 - 0) × 0.1 = 839 kopecks`
- Average bid: ~**65.3 kopecks** per impression

**Expected behavior:**
N should only count ads **with remaining_budget > 0** (eligible to pay):
- For N=300 ads with budget:
- Top rank ad pays: `0.0705 + (300 - 1 - 0) × 0.1 = 30 kopecks`
- Average bid: ~**6.3 kopecks** per impression ✓

**Impact:**
- Simulated spending: 4,855 AZN (762% of budget)
- Actual spending: 539 AZN (85% of budget)
- **Ratio: 9x overspending**

**Root cause:** The effective_bid formula was designed for competitive auctions where all participants can pay. Including ads with budget=0 (simulated organic) inflates the competitive pressure artificially.

## What Changes

**Change the effective_bid calculation to count only ads with budget:**

```python
# Count only ads with remaining_budget > 0
ads_with_budget = [ad for ad, pressure, rank_index in ranked_ads if ad.remaining_budget > 0]
N = len(ads_with_budget)

# Calculate effective_bid using only paying participants
for i, (ad, pressure, rank_index) in enumerate(ranked_ads):
    if i >= slots:
        break

    # Use N based on ads with budget, not all ads
    effective_bid = min_bid + (N - 1 - rank_index) * bid_step
```

**Benefits:**
- ✅ Realistic bid amounts (~6 kopecks vs 65 kopecks)
- ✅ Simulated spending matches actual (~540 AZN vs 4,855 AZN)
- ✅ Preserves auction logic (higher pressure = higher bid)
- ✅ No impact on organic ads (they still win slots with pressure=0, pay nothing)

**No breaking changes:**
- Auction ranking remains unchanged (pressure-based)
- Organic ads still participate and win slots
- Budget deduction logic unchanged
- Only the bid amount calculation changes

## Solution

### Implementation

**File:** `auction-simulator/src/auction_simulator/auction_engine.py`

**Change location:** `select_winners()` method (lines 169-200)

**Current code:**
```python
def select_winners(self, ranked_ads, min_bid, slots):
    N = len(ranked_ads)  # ❌ Includes ads with budget=0
    winners = []

    for i, (ad, pressure, rank_index) in enumerate(ranked_ads):
        if i >= slots:
            break
        effective_bid = min_bid + (N - 1 - rank_index) * bid_step
        winners.append((ad, effective_bid, 1))

    return winners
```

**Fixed code:**
```python
def select_winners(self, ranked_ads, min_bid, slots):
    # Count only ads that can actually pay (budget > 0)
    ads_with_budget_count = sum(1 for ad, _, _ in ranked_ads if ad.remaining_budget > 0)
    N = ads_with_budget_count  # ✓ Only paying participants

    winners = []

    for i, (ad, pressure, rank_index) in enumerate(ranked_ads):
        if i >= slots:
            break
        effective_bid = min_bid + (N - 1 - rank_index) * bid_step
        winners.append((ad, effective_bid, 1))

    return winners
```

### Alternative Considered

**Use rank among paying ads:**
```python
# Calculate rank_index only among ads with budget
paying_ads_before = sum(1 for ad, _, r in ranked_ads[:i] if ad.remaining_budget > 0)
effective_bid = min_bid + (N - 1 - paying_ads_before) * bid_step
```

**Why rejected:** More complex, same result in most cases. The simplified solution (count all paying ads for N) is sufficient since ranking already puts high-pressure (paying) ads first.

## Expected Results

**Before (current):**
```
Ads with budget: 299
Total ads in auction: 8,391
N used for effective_bid: 8,391 ❌
Average effective_bid: 65.3 kopecks
Simulated spending: 4,855 AZN (9x actual)
```

**After (fixed):**
```
Ads with budget: 299
Total ads in auction: 8,391
N used for effective_bid: 299 ✓
Average effective_bid: ~6.3 kopecks
Simulated spending: ~540 AZN (1x actual) ✓
```

**Success criteria:**
- N in effective_bid calculation ≤ 500 (reasonable for category auctions)
- Average effective_bid < 15 kopecks (vs current 65 kopecks)
- Simulated spending within 0.5x-2x of actual spending
- No regression in auction ranking or organic distribution

## Dependencies

**None.** This is a self-contained bug fix in the auction engine.

**Prerequisites:**
- PostgreSQL min_bid integration (completed: 0.0705 kopecks)
- Current auction_engine.py with select_winners() method

## Risks

**Low-risk change:**
- ✅ Isolated to one method (select_winners)
- ✅ No API changes or external dependencies
- ✅ Easy to validate (check N in logs vs actual ads_with_budget)
- ✅ Reversible (simple revert if needed)

**Potential issues:**
1. **Edge case: All ads have budget=0**
   - N=0 would cause issues
   - Mitigation: Use `max(N, 1)` to prevent division by zero in edge cases

2. **Performance:** Counting ads with budget adds O(n) operation
   - Impact: Negligible (already iterating through ranked_ads)

3. **Bid drops to min_bid when N=1**
   - This is correct behavior: no competition = minimum bid

## Testing Strategy

1. **Unit test:** Verify N calculation with mixed ads (budget=0 and >0)
2. **Integration test:** Run simulation, check logs for N value
3. **Validation:** Compare simulated spending before/after fix
4. **Regression:** Ensure organic distribution still works

**Acceptance criteria:**
- Simulated spending < 1,000 AZN (currently 4,855 AZN)
- Average effective_bid < 15 kopecks (currently 65 kopecks)
- Logs show N ≈ number of ads with budget (not total ads)
