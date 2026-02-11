# Implementation Tasks: Expand Data Extraction Filters

**Change ID**: `expand-data-extraction-filters`

## Overview

Remove two restrictive filters from data extraction queries:
1. Expand `feed_id = '6500'` → `feed_id IN ('6500', '6002')` (3 locations)
2. Remove `AND ad_type = '1'` entirely (4 locations)

**Estimated effort**: 45 minutes
**Risk level**: Low (filter removal/expansion)

---

## Phase 1: Code Changes

### Task 1.1: Update fetch_ads_from_clickhouse() - both filters

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Lines ~259-260

**Changes**:
```python
# BEFORE:
            AND feed_id = '6500'
            AND ad_type = '1'

# AFTER:
            AND feed_id IN ('6500', '6002')
            # ad_type filter removed - include all ad types
```

**Validation**: Query compiles

---

### Task 1.2: Update fetch_actual_spending_from_clickhouse() - both filters

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Lines ~327-328

**Changes**:
```python
# BEFORE:
                    AND feed_id = '6500'
                    AND ad_type = '1'

# AFTER:
                    AND feed_id IN ('6500', '6002')
                    # ad_type filter removed - include all ad types
```

**Validation**: Query compiles

---

### Task 1.3: Update calculate_min_bid() spending subquery - both filters

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Lines ~486-487

**Changes**:
```python
# BEFORE:
                            AND feed_id = '6500'
                            AND ad_type = '1'

# AFTER:
                            AND feed_id IN ('6500', '6002')
                            # ad_type filter removed - include all ad types
```

**Validation**: Query compiles

---

### Task 1.4: Update calculate_min_bid() impressions query - ad_type only

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Line ~506

**Changes**:
```python
# BEFORE:
                    AND ad_type = '1'

# AFTER:
                    # ad_type filter removed - include all ad types
                    # (no feed_id filter here by design - counts ALL impressions)
```

**Note**: This query already has NO feed_id filter (intentional design)

**Validation**: Query compiles

---

### Task 1.5: Add documentation comments

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Near line ~259 (first occurrence)

**Add comment**:
```python
# Filter expansions for comprehensive data:
#   - feed_id IN ('6500', '6002'): Include both category feed and additional feed
#   - No ad_type filter: Include all ad types for complete simulation
```

**Validation**: Comment is clear

---

## Phase 2: Validation

### Task 2.1: Manual query testing

**Action**: Run queries directly on ClickHouse

**Test 1 - Feed expansion**:
```sql
-- Count ads by feed
SELECT
    feed_id,
    COUNT(DISTINCT ad_id) as ad_count
FROM enriched_distributed
WHERE
    data_chunk_date = '2026-01-22'
    AND country_id = 13
    AND category_id = 1361
    AND feed_id IN ('6500', '6002')
GROUP BY feed_id;
```

**Expected**: See breakdown of ads per feed

**Test 2 - Ad type expansion**:
```sql
-- Count ads by ad_type
SELECT
    ad_type,
    COUNT(DISTINCT ad_id) as ad_count
FROM enriched_distributed
WHERE
    data_chunk_date = '2026-01-22'
    AND country_id = 13
    AND category_id = 1361
    AND feed_id IN ('6500', '6002')
GROUP BY ad_type;
```

**Expected**: See distribution across ad_type values

---

### Task 2.2: Run 1-day simulation

**Command**:
```bash
./venv/bin/python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1361 \
  --time-from 2026-01-22 \
  --time-to 2026-01-22
```

**Check**:
- Simulation completes without errors
- Compare N (ads with budget) to previous baseline
- Verify no unexpected behavior

**Expected evidence**:
```
INFO: Loaded X ads with budget (before: 81)
INFO: Loaded Y ads without budget (before: 33)
```

(X should be ≥ 81 if feed 6002 or other ad_types have ads with budget)

---

### Task 2.3: Inspect results

**Check**: `summary_statistics_*.txt`

**Metrics to compare**:
- Total ads loaded: Should increase (or stay same if new sources empty)
- Spending totals: May change if new data has different patterns
- min_bid values: Recalculated with broader base

**Validation**:
- No 10x+ unexpected changes
- Metrics reasonable and explainable

---

### Task 2.4: Data quality check

**Inspect logs**: Check for warnings/errors about:
- Invalid ad data
- Missing required fields
- Unusual spending patterns

**Action if issues found**:
- Investigate which feed/ad_type causes issue
- May need to add back selective filters

---

## Phase 3: Documentation

### Task 3.1: Update spec (if needed)

**File**: `openspec/specs/data-extraction/spec.md`

**Action**: Check if spec mentions these filters explicitly
- If yes: Update to reflect new behavior
- If no: No action (implementation detail)

---

### Task 3.2: Add FAQ entry (if significant impact)

**Condition**: If ad count changes by 20%+

**File**: `auction-simulator/docs/faq/`

**Content**: Explain why filters were removed/expanded

**Otherwise**: Skip (too minor for FAQ)

---

## Dependencies

```
Task 1.1 ──→ Task 1.2 ──→ Task 1.3 ──→ Task 1.4 ──→ Task 1.5
                                                       ↓
                                                    Task 2.1
                                                       ↓
                                                    Task 2.2
                                                       ↓
                                        Task 2.3 ←────┴────→ Task 2.4
```

## Completion Criteria

- ✅ 3 feed_id filters expanded to IN clause
- ✅ 4 ad_type filters removed
- ✅ Documentation comments added
- ✅ Manual queries run successfully
- ✅ 1-day simulation completes
- ✅ Results inspected, no anomalies

## Rollback Plan

If issues found after deployment:
1. Revert to single feed: `feed_id = '6500'`
2. Re-add ad_type filter: `AND ad_type = '1'`
3. Investigate root cause before retry

## Notes

- **Low risk**: Standard SQL filter changes
- **Backward compatible**: If new data sources empty, behaves like before
- **Independent changes**: Can apply feed expansion without ad_type removal (or vice versa)
- **No config needed**: Hardcoded values acceptable for this use case
