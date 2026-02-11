# Tasks: Fix min_bid Calculation to Include All Feed Impressions

## Implementation Tasks

### 1. Create DBeaver validation query to measure current inflation
**Goal:** Quantify the min_bid inflation caused by feed_id filter

- [x] Write SQL query comparing min_bid with and without feed_id filter
- [x] Query should show:
  - Paid impressions with feed_id='6500' (current)
  - Paid impressions ALL feeds (proposed)
  - Inflation ratio (old / new)
- [ ] Run query in DBeaver for category 1361, period 2026-01-22 to 2026-01-26 *(requires database access)*
- [ ] Document actual inflation ratio in validation results *(pending query execution)*

**Success criteria:**
- ✅ Query created and ready to run
- ⏳ Inflation ratio > 1.0 confirms the problem exists *(pending execution)*
- ✅ Query saved to `/tmp/min_bid_all_feeds_validation.sql`

**Files:**
- ✅ Created: `/tmp/min_bid_all_feeds_validation.sql`

---

### 2. Update _calculate_min_bids() to remove feed_id filter from impression count
**Goal:** Fix min_bid calculation to use all-feeds impressions

- [x] Modify `category_impressions` CTE in `_calculate_min_bids()`
- [x] Remove `AND feed_id = '6500'` line from paid impressions query
- [x] Keep all other impression filters (component, screen, element, action)
- [x] Update docstring to explain dual query approach
- [x] Add debug logging showing impression counts with/without feed filter

**Success criteria:**
- ✅ Code compiles without errors
- ✅ Docstring clearly explains why feed_id filter removed (lines 330-342)
- ✅ Debug logs show impression counts for validation (lines 399, 405-406, 411-412)

**Files:**
- ✅ Modified: `auction-simulator/src/auction_simulator/data_extraction.py:323-422`

---

### 3. Add validation logging to track impression counts
**Goal:** Make debugging easier by logging both impression counts

- [x] Add log statement before min_bid calculation showing:
  - `paid_impressions_all_feeds` (from modified query)
  - spending in AZN format for readability
- [x] Log total_spending and calculated min_bid
- [x] Add category_id to all log messages for multi-category debugging

**Success criteria:**
- ✅ Logs show impression counts clearly with "impressions_all_feeds" label
- ✅ Easy to validate min_bid calculation manually
- ✅ Log level appropriate (INFO for summary, DEBUG for details)

**Files:**
- ✅ Modified: `auction-simulator/src/auction_simulator/data_extraction.py:323-422`

---

### 4. Update spec to document dual query approach
**Goal:** Document why min_bid and simulation use different feed filters

- [x] Modify "Requirement: Category min_bid Calculation" in spec
- [x] Add new scenario explaining dual query approach:
  - Min_bid uses all feeds (reflects actual cost)
  - Simulation uses feed_id='6500' (scopes simulation)
- [x] Update SQL example to remove feed_id from category_impressions CTE
- [x] Add rationale explaining feed_id filter inflation issue

**Success criteria:**
- ✅ Spec clearly explains why two different queries needed
- ✅ SQL example matches implementation (no feed_id filter in category_impressions)
- ✅ Rationale section explains inflation problem and dual query approach

**Files:**
- ✅ Created: `openspec/changes/fix-min-bid-all-feeds-calculation/specs/data-extraction/spec.md`

---

### 5. Clear parquet cache and re-run simulation
**Goal:** Validate that new min_bid fixes spending discrepancy

- [x] Delete all cached parquet files in `auction-simulator/data/cache/`
- [ ] Run simulation for category 1361, period 2026-01-22 to 2026-01-26 *(requires ClickHouse access)*
- [ ] Check summary statistics output: *(pending simulation run)*
  - Simulated spending should be closer to actual (539.23 AZN)
  - Target: within 50-200% of actual (not 900%)
  - Min_bid should match actual CPI

**Success criteria:**
- ✅ Cache cleared successfully
- ⏳ Simulated spending < 1,000 AZN (currently 4,888 AZN) *(pending execution)*
- ⏳ Spending ratio < 3x (currently 9x) *(pending execution)*
- ✅ Code ready to log min_bid value during extraction

**Files:**
- ✅ Cleared: `auction-simulator/data/cache/*.parquet`
- ⏳ Ready to run: Simulation with parameters (country=13, category=1361, time=2026-01-22 to 2026-01-26)

**Note:** ClickHouse connection not available locally. Simulation ready to run when database access is available.

---

### 6. Run DBeaver validation query with new code
**Goal:** Confirm min_bid calculation matches spec

- [ ] Run validation query from Task 1 *(requires ClickHouse access)*
- [ ] Compare results with baseline: *(pending query execution)*
  - Impression counts should match new implementation
  - Min_bid should be LOWER than before (less inflation)
- [ ] Verify simulation logs match DBeaver results *(pending both executions)*

**Success criteria:**
- ⏳ DBeaver min_bid matches simulation logs *(pending execution)*
- ⏳ Inflation ratio = 1.0 (no more feed_id filter bias) *(pending execution)*
- ⏳ All impression counts consistent across queries and code *(pending execution)*

**Files:**
- ✅ Ready: `/tmp/min_bid_all_feeds_validation.sql`

**Note:** Validation query ready to run when database access is available.

---

## Task Dependencies

```
Task 1 (validation query)
  ↓
Task 2 (code changes) → Task 3 (logging)
  ↓
Task 4 (spec update)
  ↓
Task 5 (run simulation)
  ↓
Task 6 (validate results)
```

**Parallelizable:**
- Task 1 can run independently (baseline measurement)
- Tasks 2, 3, 4 can be done together (all part of same code change)

**Sequential:**
- Task 5 must wait for Tasks 2-4 (needs code changes)
- Task 6 must wait for Task 5 (needs new simulation results)

---

## Validation Checklist

After all tasks complete, verify:

- [x] Min_bid calculation uses all-feeds impressions (no feed_id filter) ✅
- [x] Simulation extraction uses feed_id='6500' impressions (unchanged) ✅
- [ ] Simulated spending within 50-200% of actual spending ⏳ *(requires database access)*
- [ ] Min_bid ≈ Actual CPI (both calculated from same paid impression count) ⏳ *(requires database access)*
- [x] Logs clearly show impression counts for debugging ✅
- [x] Spec documents dual query approach with rationale ✅
- [ ] DBeaver validation confirms implementation correctness ⏳ *(requires database access)*

**Implementation Status:** ✅ Code changes complete and ready for testing
**Testing Status:** ⏳ Requires ClickHouse database access to run simulation and validation queries
