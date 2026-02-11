# Expand Data Extraction Filters

**Status**: ✅ Proposed (Awaiting Approval)
**Change ID**: `expand-data-extraction-filters`
**Created**: 2026-01-30

## Quick Summary

Remove two restrictive filters from data extraction to provide more comprehensive simulation data:

1. **Expand feed filter**: `feed_id = '6500'` → `feed_id IN ('6500', '6002')`
2. **Remove ad_type filter**: Delete `AND ad_type = '1'` lines

**Problem**: Current filters exclude feed 6002 ads and non-type-1 ads

**Solution**: Update 4 SQL queries to include all relevant data

**Impact**:
- ✅ Complete ad set (both feeds, all types)
- ✅ Accurate spending/impression data
- ✅ Better simulation fidelity

## Files

- **[proposal.md](./proposal.md)**: Problem statement, rationale
- **[tasks.md](./tasks.md)**: Implementation steps
- **[specs/data-extraction/spec.md](./specs/data-extraction/spec.md)**: Spec delta

## Implementation Complexity

- **Risk**: 🟢 Low (filter removal/expansion)
- **Effort**: 45 minutes
- **Breaking**: No (backward compatible if new sources empty)

## Changes Required

**File**: `data_extraction.py`

**7 filter changes:**
1. Line ~259: Expand feed + remove ad_type
2. Line ~327: Expand feed + remove ad_type
3. Line ~486: Expand feed + remove ad_type
4. Line ~506: Remove ad_type only

**Summary:**
- 3× `feed_id = '6500'` → `feed_id IN ('6500', '6002')`
- 4× `AND ad_type = '1'` → (deleted)

## Validation Plan

1. Manual ClickHouse queries (test data quality)
2. 1-day simulation (verify no errors)
3. Results inspection (check metrics reasonable)

## Next Steps

1. **Review**: Approve changes
2. **Implement**: Update queries + documentation
3. **Test**: Run validation simulation
4. **Archive**: Mark complete

---

**Related Changes**: None (independent)
