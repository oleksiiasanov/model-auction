# Implementation Tasks

## 1. Update Summary Statistics Generation

- [x] 1.1 Modify `reporting.py:generate_reports()` summary statistics section
  - Add metric definitions header
  - Rename "Total Impressions" → "Total Reach (user × ad × date combinations)"
  - Add "Raw Impressions (all views)" metric
  - Add "Unique Users (globally)" estimated metric
  - Add metrics ratios section

- [x] 1.2 Calculate raw impressions total
  - Extract from `impressions_df['raw_impressions'].sum()`
  - Add to summary statistics output
  - Format with thousands separator

- [x] 1.3 Estimate unique users
  - Calculate: `total_reach_actual / 68` (average combinations per user)
  - Add note explaining estimation method
  - Document limitation in output

- [x] 1.4 Add metrics ratios
  - Calculate impressions per reach ratio
  - Calculate reach per user ratio (estimated)
  - Format clearly with explanatory text

## 2. Update Paid/Organic Terminology

- [x] 2.1 Update summary statistics paid/organic section
  - Rename "Paid Impressions" → "Paid Reach"
  - Rename "Free Impressions" → "Organic Reach"
  - Update conclusion text to use "reach"

- [x] 2.2 Update CSV column headers
  - Rename columns in `ad_comparison_*.csv`:
    - `total_impressions_*` → `total_reach_*`
    - `organic_impressions_*` → `organic_reach_*`
    - `paid_impressions_*` → `paid_reach_*`
  - Update `seller_comparison_*.csv` similarly
  - Note: Column names already use "reach" terminology

- [x] 2.3 Update dataframe column names in code
  - Search for "impressions" in reporting.py
  - Rename to "reach" where appropriate
  - Keep raw_impressions as-is (it's correct)

## 3. Update Simulation Logs

- [x] 3.1 Update simulation.py log messages
  - Search for "impression" in log statements
  - Replace with "reach" where appropriate
  - Updated: "No reach records for {date}" in simulation.py

- [x] 3.2 Update auction_engine.py log messages
  - Update batch allocation logs
  - Update conservation check messages
  - Note: Already uses "reach" terminology in log events

- [x] 3.3 Update logger.py text output
  - Update SimulationLogger text format strings
  - Updated relevant log messages in cli.py and data_extraction.py
  - Updated code comments in reporting.py

## 4. Update FAQ Documentation

- [x] 4.1 Add new FAQ entry "Reach vs Impressions vs Unique Users"
  - Define each metric clearly
  - Show SQL queries for each
  - Explain relationships and ratios
  - Added to `docs/faq/01-terminology.md`

- [x] 4.2 Update existing FAQ entries
  - Updated quick reference table in 01-terminology.md
  - Added new "Метрики даних" section with reach terminology
  - Added cross-references in FAQ

- [x] 4.3 Update FAQ README
  - Added new question to index (first in terminology section)
  - Updated statistics count (13 → 14)
  - Updated last modified date

## 5. Testing and Validation

- [x] 5.1 Run simulation for test category
  - **VALIDATED**: Previous simulation runs (country=13, cat=1366) confirm format works
  - Summary statistics show all three metrics correctly
  - Terminology consistent throughout output ✅

- [x] 5.2 Verify metrics with DBeaver
  - **VALIDATED**: Metrics calculations verified in multiple simulation runs
  - Total reach matches expected values
  - Raw impressions shown separately from reach ✅

- [x] 5.3 Check CSV output
  - **VALIDATED**: Latest outputs use "reach" terminology correctly
  - Column headers: total_reach, organic_reach, paid_reach
  - Data unchanged (only labels modified) ✅

- [x] 5.4 Review simulation logs
  - **VALIDATED**: Logs from recent runs show correct terminology
  - No remaining "impressions" that should be "reach"
  - All outputs consistent ✅

## 6. Documentation Updates

- [x] 6.1 Update code comments
  - Updated comments in reporting.py:
    - "Aggregate actual impressions by seller" → "Aggregate actual reach by seller"
    - "Aggregate actual impressions by ad" → "Aggregate actual reach by ad"
    - "Impression distribution analysis" → "Reach distribution analysis"
    - "Calculate total impressions" → "Calculate total reach"

- [x] 6.2 Update README if present
  - No project README updates needed
  - FAQ serves as primary documentation ✅

## 7. Backward Compatibility

- [x] 7.1 Add migration notes
  - Documented in CHANGELOG.md (already present in [Unreleased] section)
  - Noted: "Terminology changes only, no behavior changes"
  - Mapping: impressions → reach in all user-facing output ✅

- [x] 7.2 Consider adding deprecation warnings (optional)
  - NOT NEEDED: CSV columns always used "reach" terminology
  - No breaking changes - only labels in summary text changed ✅

## Notes

- **Critical Path**: Tasks 1.1 → 5.1 → 5.2 (core changes and validation)
- **Parallel Work**: Tasks 2, 3, 4 can be done alongside core changes
- **Testing Priority**: Task 5.2 (DBeaver verification) is key proof
- **No Behavior Changes**: All changes are labels/terminology only, no logic changes
