# Tasks: Fix Effective Bid Participant Count

## Implementation Tasks

### 1. Update select_winners() to count only ads with budget
**Goal:** Change N calculation to exclude ads with budget=0 from participant count

- [x] Modify `select_winners()` method in `auction_engine.py`
- [x] Add calculation: `ads_with_budget_count = sum(1 for ad, _, _ in ranked_ads if ad.remaining_budget > 0)`
- [x] Replace `N = len(ranked_ads)` with `N = ads_with_budget_count`
- [x] Add safety check: `N = max(N, 1)` to prevent edge case where all ads have budget=0
- [x] Add logging: `logger.debug(f"Effective bid calculation: N={N} ads with budget (out of {len(ranked_ads)} total)")`

**Success criteria:**
- N reflects only ads with remaining_budget > 0
- No errors when all ads have budget=0
- Logging clearly shows N vs total ads

**Files:**
- Modify: `auction-simulator/src/auction_simulator/auction_engine.py:169-200`

**Dependencies:** None

---

### 2. Add validation logging in run_batch_auction
**Goal:** Make it easy to verify N is correct in simulation logs

- [x] Add logging in `run_batch_auction()` after winner selection
- [x] Log total eligible ads, ads with budget, and N used for bids
- [x] Format: `"Batch {batch}: {len(winners)} winners, N={N} (ads_with_budget={ads_with_budget} / total={len(ads)})"`

**Success criteria:**
- Logs show N value for each batch
- Easy to spot if N is inflated (should be < 500 typically)

**Files:**
- Modify: `auction-simulator/src/auction_simulator/auction_engine.py:233-290`

---

### 3. Update spec to document N calculation
**Goal:** Clarify in spec that N counts only ads with budget

- [x] Modify "Requirement: Effective Bid Calculation" in auction-engine spec
- [x] Add scenario: "N counts only ads with remaining_budget > 0"
- [x] Document rationale: ads without budget can't pay, shouldn't inflate competition
- [x] Add example showing N=300 with budget vs 8,391 total ads

**Success criteria:**
- Spec clearly defines N as "ads with remaining_budget > 0"
- Rationale explains why ads with budget=0 are excluded

**Files:**
- Modify: `openspec/changes/fix-effective-bid-participant-count/specs/auction-engine/spec.md`

---

### 4. Run simulation and validate results
**Goal:** Verify fix reduces simulated spending to match actual

- [x] Clear cache: `rm -f auction-simulator/data/cache/*.parquet`
- [x] Run simulation: category 1361, period 2026-01-22 to 2026-01-26
- [x] Check logs for N value (expect N < 500, not ~8,000) - **Result: N=94 ✓**
- [x] Check average effective_bid (expect < 15 kopecks, not 65) - **Result: 2.05 kopecks ✓**
- [x] Check simulated spending (expect ~540 AZN, not 4,855) - **Result: 649 AZN (1.2x actual) ✓**

**Success criteria:**
- N in logs < 500 (typically 100-300)
- Average effective_bid < 15 kopecks
- Simulated spending within 0.5x-2x of actual spending (539 AZN)
- No errors or auction failures

**Files:**
- Run: Simulation command with --no-cache

**Dependencies:** Task 1 must be complete

---

### 5. Add unit test for N calculation
**Goal:** Test that N excludes ads with budget=0

- [ ] Create test `test_effective_bid_excludes_zero_budget_ads()`
- [ ] Setup: 5 ads with budget > 0, 10 ads with budget=0
- [ ] Call `select_winners()` with these 15 ads
- [ ] Assert: N used in effective_bid calculation is 5 (not 15)
- [ ] Assert: Winners' effective_bids are reasonable (not inflated by N=15)

**Success criteria:**
- Test passes with N=5
- Test fails if old code (N=15) is used

**Files:**
- Create: `auction-simulator/tests/test_auction_engine.py` (or add to existing test file)

**Optional:** Can be done after main fix for validation

---

## Task Dependencies

```
Task 1 (Update select_winners)
  ↓
Task 2 (Add logging) - Can be done in parallel with Task 1
  ↓
Task 4 (Run simulation)
  ↓
Task 5 (Unit test) - Independent, can be done anytime

Task 3 (Update spec) - Independent, can be done in parallel
```

**Parallelizable:**
- Tasks 2 and 3 can be done in parallel with Task 1

**Sequential:**
- Task 4 requires Task 1 (need fix before validating)
- Task 5 is independent (can be done before or after)

---

## Validation Checklist

After all tasks complete, verify:

- [x] N in simulation logs < 500 (not ~8,000) - **N=94 ✓**
- [x] Average effective_bid < 15 kopecks (not 65) - **2.05 kopecks ✓**
- [x] Simulated spending < 1,000 AZN (not 4,855) - **649 AZN ✓**
- [x] Spending ratio within 0.5x-2x of actual (not 9x) - **1.2x ✓**
- [x] No regression in organic impression distribution - **313,977 total impressions preserved ✓**
- [x] Logs clearly show N vs total ads for debugging - **"N=94 ads with budget (out of 8391 total)" ✓**
- [ ] Unit test covers N calculation logic - **Optional, can be added later**
- [x] Spec documents N definition and rationale - **Complete ✓**

**Rollback plan:** Revert `select_winners()` change, use `N = len(ranked_ads)` again.

---

## Expected Results

**Before fix:**
```
2026-01-28 16:14:59 - INFO - Batch 1: 40 winners, N=8391 ads
Average effective_bid: 65.3 kopecks
Simulated spending: 4,855.95 AZN
```

**After fix:**
```
2026-01-28 16:20:00 - INFO - Batch 1: 40 winners, N=299 ads with budget (out of 8391 total)
Average effective_bid: ~6.3 kopecks
Simulated spending: ~540 AZN ✓
```
