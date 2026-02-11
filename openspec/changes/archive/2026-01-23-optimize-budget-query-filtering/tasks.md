# Tasks: Optimize Budget Query Filtering

## Implementation Tasks

### 1. Update _extract_budgets query (Core Change)
- **File**: `src/auction_simulator/data_extraction.py`
- **Action**: Modify `_extract_budgets` method to add WHERE ad_id IN (subquery)
- **Details**:
  - Add `categories` parameter to method signature
  - Build subquery: SELECT DISTINCT ad_id FROM enriched_distributed with category filters
  - Add AND ad_id IN (subquery) to main WHERE clause
  - Pass `categories` parameter from `extract_data` method
- **Verification**: Run method and verify SQL query structure

### 2. Update method signature
- **File**: `src/auction_simulator/data_extraction.py`
- **Action**: Change `_extract_budgets(country, time_from, time_to)` → `_extract_budgets(country, categories, time_from, time_to)`
- **Details**: Update all call sites (currently only one: `extract_data` method)
- **Verification**: Check that method is called with correct parameters

### 3. Add query logging
- **File**: `src/auction_simulator/data_extraction.py`
- **Action**: Add logger.debug() to log full SQL query before execution
- **Details**: Log query for debugging and verification during testing
- **Verification**: Run extraction and check logs show new query structure

### 4. Test with existing data
- **File**: Manual testing / Python REPL
- **Action**: Run extraction with same parameters as before and compare results
- **Details**:
  - Extract with categories=[1234, 5678], country=13
  - Compare DataFrame shapes (rows, columns)
  - Compare sample records (ad_id, daily_budget values)
  - Verify no missing ads
- **Verification**: DataFrames match exactly

### 5. Benchmark performance
- **File**: Manual testing / Python script
- **Action**: Measure query execution time before and after optimization
- **Details**:
  - Run old query (without subquery): measure time
  - Run new query (with subquery): measure time
  - Calculate improvement ratio
  - Measure DataFrame memory usage (sys.getsizeof)
- **Verification**: At least 5x speedup, 10x memory reduction

### 6. Verify cache file size
- **File**: Check `cache/` directory
- **Action**: Compare parquet file sizes before and after
- **Details**:
  - Clear cache
  - Run extraction with new code
  - Check `<cache_key>_budgets.parquet` file size
  - Compare to previous file size (if available)
- **Verification**: At least 10x size reduction

### 7. Test edge cases
- **File**: Manual testing / Unit tests
- **Action**: Test with various parameter combinations
- **Details**:
  - Single category vs multiple categories
  - Small date range (1 day) vs large (30 days)
  - Category with 0 ads vs category with many ads
  - Country with few ads vs country with many ads
- **Verification**: All cases return correct results

### 8. Update docstring
- **File**: `src/auction_simulator/data_extraction.py`
- **Action**: Update `_extract_budgets` docstring to reflect optimization
- **Details**: Mention that method filters by category-specific ad_ids
- **Verification**: Docstring accurately describes new behavior

## Validation Tasks

### 9. Run full simulation
- **Action**: Run complete simulation with optimized extraction
- **Details**: Use config/local.yaml with test parameters
- **Verification**: Simulation completes successfully, outputs match expected format

### 10. Compare simulation outputs
- **Action**: Compare results with previous implementation (if baseline exists)
- **Details**:
  - Run simulation with old code → save outputs
  - Run simulation with new code → save outputs
  - Compare seller_comparison.csv and ad_comparison.csv
  - Check that metrics (impressions, spending) are identical
- **Verification**: Outputs are identical (or explain any differences)

## Documentation Tasks

### 11. Update CHANGELOG
- **File**: `CHANGELOG.md` (if exists) or create it
- **Action**: Document optimization in changelog
- **Details**: Add entry: "Optimized budget query to filter by category-specific ads (50x data reduction)"
- **Verification**: Entry is clear and accurate

## Estimated Time
- Implementation: 1-2 hours
- Testing: 1 hour
- Documentation: 15 minutes
- **Total**: 2-3 hours
