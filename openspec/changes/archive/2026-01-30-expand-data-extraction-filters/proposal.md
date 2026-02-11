# Proposal: Expand Data Extraction Filters

**Change ID**: `expand-data-extraction-filters`
**Status**: Proposed
**Created**: 2026-01-30

## Why

Current data extraction has two restrictive filters that limit simulation accuracy:
1. **Single feed**: `feed_id = '6500'` excludes ads from feed 6002
2. **Single ad type**: `ad_type = '1'` excludes other ad types

Removing these restrictions provides more complete data for accurate auction simulation.

## What Changes

Update SQL queries in `data_extraction.py` to remove restrictive filters:

**Change 1 - Expand feed filter (3 locations):**
- From: `AND feed_id = '6500'`
- To: `AND feed_id IN ('6500', '6002')`

**Change 2 - Remove ad_type filter (4 locations):**
- From: `AND ad_type = '1'`
- To: (line deleted)

**Files affected:**
- `src/auction_simulator/data_extraction.py`

**Query locations:**
1. Line ~259-260: `fetch_ads_from_clickhouse()` - BOTH changes
2. Line ~327-328: `fetch_actual_spending_from_clickhouse()` - BOTH changes
3. Line ~486-487: `calculate_min_bid_per_category()` spending subquery - BOTH changes
4. Line ~506: `calculate_min_bid_per_category()` impressions query - ad_type ONLY (no feed filter by design)

## Problem Statement

### Problem 1: Missing Feed 6002 Ads

Current `feed_id = '6500'` excludes ads from feed 6002:
- Incomplete ad set
- Missing spending data
- Potentially inaccurate min_bid calculations

### Problem 2: Missing Non-Type-1 Ads

Current `ad_type = '1'` excludes other ad types:
- Incomplete ad coverage
- Missing impressions/spending
- Simulation doesn't reflect full ecosystem

## Proposed Solution

Apply two independent filter expansions:

### Change 1: Expand Feed Filter
```sql
-- BEFORE:
WHERE feed_id = '6500'

-- AFTER:
WHERE feed_id IN ('6500', '6002')
```

### Change 2: Remove Ad Type Filter
```sql
-- BEFORE:
AND ad_type = '1'

-- AFTER:
-- (line removed entirely)
```

## Expected Impact

| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Feeds** | 6500 only | 6500 + 6002 | ✅ More complete |
| **Ad types** | Type '1' only | All types | ✅ Full coverage |
| **N (ads)** | X | X+Y+Z | ✅ Larger set |
| **Data quality** | Restricted | Comprehensive | ✅ Better simulation |

Exact impact depends on data volume in feed 6002 and other ad types.

## Scope

### In Scope
- Remove 4 ad_type filters
- Expand 3 feed_id filters
- Add documentation comments

### Out of Scope
- Making filters configurable
- Business logic analysis of ad_type meanings
- Adding feeds beyond 6500/6002

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Invalid data quality | Validate in test simulation |
| Performance degradation | Monitor query times (expected: negligible) |
| Duplicate ads | Existing DISTINCT handles this |
| Type incompatibility | Simulation code is generic |

## Validation Plan

1. Run updated queries on ClickHouse manually
2. Inspect ad counts by feed_id and ad_type
3. Run 1-day simulation, verify no errors
4. Compare metrics to baseline

## Questions for Stakeholders

1. Confirm feed 6002 should be included?
2. Are all ad_type values valid for simulation?
3. Is data quality production-ready?

## Success Criteria

- ✅ 7 filter lines updated (3 feed, 4 ad_type)
- ✅ Queries execute successfully
- ✅ Simulation runs without errors
- ✅ Ad count increases as expected
- ✅ No anomalies in results

## References

- **Code**: [data_extraction.py](../../auction-simulator/src/auction_simulator/data_extraction.py)
- **Lines**: 259-260, 327-328, 486-487, 506
