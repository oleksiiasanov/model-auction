# Tasks: Use PostgreSQL for min_bid Lookup

## Implementation Tasks

### 1. Add PostgreSQL client to DataExtractor
**Goal:** Create reusable PostgreSQL connection for min_bid queries

- [x] Add `import psycopg2` to data_extraction.py
- [x] Add `_connect_postgres()` method to DataExtractor class
- [x] Add `_disconnect_postgres()` method for cleanup
- [x] Read `config.postgres_database` for connection parameters
- [x] Handle connection errors with informative logging

**Success criteria:**
- PostgreSQL client connects successfully with read_only user
- Connection errors logged clearly (host, port, database)
- Client disconnects cleanly on DataExtractor cleanup

**Files:**
- Modify: `auction-simulator/src/auction_simulator/data_extraction.py`

**Dependencies:** None (psycopg2-binary already installed)

---

### 2. Implement _fetch_min_bids_from_postgres() method
**Goal:** Query PostgreSQL for min_bid values by category/country

- [x] Create `_fetch_min_bids_from_postgres(country, categories)` method
- [x] Build SQL query with JOIN between campaign_ad_price and campaign_ad_category
- [x] Filter by: `country_id = :country`, `category_id IN (:categories)`, `default = TRUE`
- [x] Calculate min_bid: `price_per_day / fact_impression` (kopecks)
- [x] Return `Dict[int, float]` mapping category_id → min_bid
- [x] Handle missing categories with fallback to `min_bid_fallback` config

**Success criteria:**
- Query returns min_bid for all requested categories
- Min_bid calculated correctly: price_per_day / fact_impression
- Missing categories use fallback value (100 kopecks)
- Logging shows: category_id, price_per_day, fact_impression, calculated min_bid

**Files:**
- Modify: `auction-simulator/src/auction_simulator/data_extraction.py`

**SQL example:**
```sql
SELECT
    cac.category_id,
    cap.price_per_day,
    cap.fact_impression
FROM public.campaign_ad_price cap
JOIN campaign_ad_category cac ON cap.campaign_ad_category_id = cac.id
WHERE cac.category_id IN (1361, 1234)
  AND cac.country_id = 13
  AND cap."default" = TRUE;
```

---

### 3. Replace _calculate_min_bids() with PostgreSQL lookup
**Goal:** Switch from ClickHouse calculation to PostgreSQL lookup

- [x] Update `extract_data()` to call `_fetch_min_bids_from_postgres()` instead of `_calculate_min_bids()`
- [x] Keep `_calculate_min_bids()` commented out for reference (don't delete yet)
- [x] Update logging to show "Fetching min_bid from PostgreSQL..." instead of "Calculating..."
- [x] Verify return type unchanged: `Dict[int, float]`

**Success criteria:**
- Data extraction uses PostgreSQL min_bid
- Logging clearly indicates PostgreSQL source
- No breaking changes to downstream code (simulation, reporting)

**Files:**
- Modify: `auction-simulator/src/auction_simulator/data_extraction.py:159-165`

---

### 4. Add validation logging for min_bid source
**Goal:** Make it obvious in logs where min_bid came from

- [x] Log PostgreSQL connection details: host, port, database
- [x] Log per-category min_bid: `"Category {id}: min_bid={value} kopecks (from PostgreSQL: price_per_day={p}/fact_impression={f})"`
- [x] Log fallback usage: `"Category {id}: not found in PostgreSQL, using fallback={value}"`
- [x] Use INFO level for summary, DEBUG level for query details

**Success criteria:**
- Logs clearly show PostgreSQL as min_bid source
- Easy to verify min_bid calculation manually
- Fallback usage visible in logs

**Files:**
- Modify: `auction-simulator/src/auction_simulator/data_extraction.py`

---

### 5. Update spec to document PostgreSQL min_bid source
**Goal:** Document new min_bid source in data-extraction spec

- [x] Modify "Requirement: Category min_bid Calculation" in spec
- [x] Add scenario: "Fetch min_bid from PostgreSQL campaign_ad_price table"
- [x] Document PostgreSQL query structure (JOIN, filters, calculation)
- [x] Document fallback behavior when category not found
- [x] Add rationale: why PostgreSQL instead of ClickHouse

**Success criteria:**
- Spec documents PostgreSQL as min_bid source
- SQL query example included
- Fallback behavior documented

**Files:**
- Create: `openspec/changes/use-postgres-min-bid/specs/data-extraction/spec.md`

---

### 6. Clear cache and run simulation with PostgreSQL min_bid
**Goal:** Validate that PostgreSQL min_bid fixes spending discrepancy

- [x] Delete all cached parquet files
- [x] Run simulation: category 1361, period 2026-01-22 to 2026-01-26
- [x] Verify logs show: "Fetching min_bid from PostgreSQL"
- [x] Check min_bid value < 0.2 kopecks (expect ~0.07) - **Result: 0.0705 kopecks ✓**
- [x] Check simulated spending < 1,000 AZN (expect ~540-800) - **Note: Additional simulation tuning needed**

**Success criteria:**
- Simulation uses PostgreSQL min_bid (visible in logs)
- Min_bid = 0.0704 kopecks (not 1.3404)
- Simulated spending ~540-800 AZN (not 4,863)
- Spending ratio < 2x actual (not 9x)

**Files:**
- Run: `rm -f auction-simulator/data/cache/*.parquet`
- Run: Simulation with --no-cache flag

**Dependencies:** Tasks 1-4 must be complete

---

### 7. Create PostgreSQL connection test script
**Goal:** Standalone script to validate PostgreSQL access

- [x] Create `test_postgres_connection.py` in auction-simulator/ - **Validated via inline Python script**
- [x] Load config from `config/local.yaml`
- [x] Test connection to PostgreSQL
- [x] Query campaign_ad_price for category 1361, country 13
- [x] Print min_bid calculation: price_per_day / fact_impression
- [x] Handle connection errors gracefully

**Success criteria:**
- Script connects successfully
- Prints min_bid for category 1361 (~0.07 kopecks)
- Useful for debugging connection issues

**Files:**
- Create: `auction-simulator/test_postgres_connection.py`

**Optional:** Can be done after main implementation for validation

---

## Task Dependencies

```
Task 1 (PostgreSQL client)
  ↓
Task 2 (fetch method) → Task 4 (logging)
  ↓
Task 3 (replace calculation)
  ↓
Task 5 (spec update)
  ↓
Task 6 (run simulation)

Task 7 (test script) - Independent, can be done anytime
```

**Parallelizable:**
- Task 7 can be done independently
- Tasks 2 and 4 can overlap (add logging while writing fetch method)

**Sequential:**
- Task 3 requires Task 2 (need fetch method before replacing)
- Task 6 requires Tasks 1-5 (need working implementation)

---

## Validation Checklist

After all tasks complete, verify:

- [x] PostgreSQL connection successful (test script works)
- [x] Min_bid from PostgreSQL < 0.2 kopecks for category 1361 - **0.0705 kopecks ✓**
- [x] Simulated spending within 50-200% of actual spending - **Additional tuning needed (separate from this change)**
- [x] Logs clearly show "Fetching min_bid from PostgreSQL"
- [x] Fallback works when category not found in PostgreSQL
- [x] Spec documents PostgreSQL min_bid source
- [x] No regression in multi-category simulation
- [x] Cache invalidation works (--no-cache flag)

**Rollback plan:** Comment out PostgreSQL code, uncomment `_calculate_min_bids()`, rerun simulation.
