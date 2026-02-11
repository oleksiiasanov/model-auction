# Tasks: Fix min_bid Category Filter

## Implementation Tasks

### 1. Update `_calculate_min_bids` query with category filter
- **File**: `src/auction_simulator/data_extraction.py`
- **Location**: Lines 340-348 (category_spending CTE)
- **Action**: Add `AND ad_id GLOBAL IN (subquery)` to filter spending by category-specific ads
- **Details**:
  - Add subquery to extract ad_ids from enriched_distributed with category filter
  - Use GLOBAL IN keyword for distributed tables
  - Match filter conditions with budget query (feed_id='6500', ad_type='1', client!='backend')
- **Verification**:
  - Check query syntax is valid ClickHouse SQL
  - Ensure GLOBAL IN is used (not plain IN)
  - Verify all filter conditions match category_impressions CTE

### 2. Update method docstring
- **File**: `src/auction_simulator/data_extraction.py`
- **Location**: Lines 323-326
- **Action**: Update docstring to clarify category-specific calculation
- **Details**:
  - Add note about GLOBAL IN subquery
  - Mention filtering by category-specific ads
- **Verification**: Docstring accurately describes implementation

### 3. Add debug logging for spending query
- **File**: `src/auction_simulator/data_extraction.py`
- **Location**: After line 370 (after query execution)
- **Action**: Add logger.debug() to log spending/impressions breakdown
- **Details**:
  - Log total_spending, paid_impressions, and calculated min_bid
  - Include category_id in log message
- **Verification**: Logs visible when running with --verbose flag

---

## Validation Tasks

### 4. Test with single category simulation
- **Action**: Run simulation with country=13, category=1361, date=2026-01-22
- **Expected Results**:
  - min_bid between 0.5-1.5 kopecks (not 300+ kopecks)
  - Simulated spending ~70-90 AZN (not 600+ AZN)
  - Logs show category-specific spending values
- **Verification**: Check simulation logs and summary statistics

### 5. Test with multiple categories
- **Action**: Run simulation with country=13, categories=[1361, 8312], date range
- **Expected Results**:
  - Each category has separate min_bid calculation
  - min_bid values are category-specific (different per category)
  - No cross-category contamination in spending totals
- **Verification**: Check min_bid log messages for each category

### 6. Verify spending matches actual
- **Action**: Compare simulated spending to actual spending in summary report
- **Expected Results**:
  - Simulated spending within 50-200% of actual (currently 900%)
  - Ratio improvement: from 9x overspend to <2x variance
- **Verification**: Read summary_statistics_*.txt file

### 7. Test edge cases
- **Action**: Test scenarios with missing/incomplete data
- **Test cases**:
  - Category with 0 spending → uses fallback min_bid
  - Category with 0 paid impressions → uses fallback min_bid
  - Date range with no data → fallback for all categories
- **Verification**: Fallback mechanism works correctly, no crashes

---

## Performance Tasks

### 8. Benchmark query execution time
- **Action**: Measure query execution time for min_bid calculation
- **Expected Results**:
  - Query executes in 200-500ms (similar to budget query)
  - No timeout errors
  - ClickHouse query plan shows subquery evaluated once
- **Verification**: Check logs for query timing

### 9. Verify cache invalidation
- **Action**: Clear cache, run simulation twice
- **Expected Results**:
  - First run: extracts data, calculates min_bid, saves cache
  - Second run: loads from cache, min_bid matches first run
- **Verification**: Cache files contain correct min_bid values

---

## Documentation Tasks

### 10. Update spec with implementation details
- **File**: `openspec/specs/data-extraction/spec.md`
- **Action**: Update "Category min_bid Calculation" requirement
- **Details**:
  - Add GLOBAL IN subquery approach
  - Document category filter requirement explicitly
  - Add example query with expected results
- **Verification**: Spec accurately reflects implementation

### 11. Update CHANGELOG
- **File**: `auction-simulator/CHANGELOG.md` (if exists) or commit message
- **Action**: Document the bugfix
- **Details**:
  - Describe problem (min_bid calculation bug)
  - Explain solution (category filter added)
  - Mention impact (9x spending reduction to realistic values)
- **Verification**: CHANGELOG entry is clear and accurate

---

## Dependencies

- **No blockers**: Can implement immediately
- **Follows**: optimize-budget-query-filtering (uses same GLOBAL IN pattern)
- **Enables**: Realistic simulation results for analysis

## Parallelization Opportunities

- Tasks 1-3 can be done sequentially (implementation)
- Tasks 4-7 can run in parallel (validation tests)
- Tasks 8-9 can run in parallel (performance tests)
- Tasks 10-11 can be done after implementation (documentation)

## Estimated Complexity

- **Implementation**: Simple (add subquery filter)
- **Testing**: Medium (multiple scenarios to validate)
- **Risk**: Low (follows proven pattern from budget query)
