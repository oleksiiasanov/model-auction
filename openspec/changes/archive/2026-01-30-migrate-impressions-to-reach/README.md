# Change: Migrate Impressions to Reach

**Status**: Proposed
**Created**: 2026-01-30
**Type**: Breaking Change
**Risk**: HIGH

## Overview

Migrate the auction simulator from counting **impressions** (all ad view events) to **reach** (unique users viewing ads per day). This is a fundamental fix to align the simulation with real-world advertising metrics.

## Problem

Currently, the system counts every ad view as an impression, leading to inflated metrics:
- User viewing same ad 3 times in a day = 3 impressions
- Should be: 1 reach (unique user per day)

**Example from real data:**
- user_id=33 views ad_id=1 eight times across 2 days
- Current: 8 impressions
- Correct: 5 reach (deduplicated by day)

## Solution

### Data Extraction Changes
- SQL: `COUNT(DISTINCT user_id)` grouped by (date, seller_id, ad_id, hour)
- Track `reach_timestamp = MIN(timestamp)` for temporal distribution
- Filter `WHERE user_id IS NOT NULL`
- Preserve `raw_impressions` for comparison

### Auction Engine Changes
- Rename `simulated_impressions` → `simulated_reach`
- Rename `organic_impressions_historical` → `organic_reach_historical`
- Update slot allocation: `total_slots = total_reach` (not total_impressions)
- Update pacing calculations to use reach metrics

## Impact

**Expected Traffic Reduction**: 40-60% (reach < impressions due to deduplication)

**Breaking Changes**:
- Ad dataclass field names changed
- SQL query structure modified
- Simulation batch sizing changes
- All existing output metrics change meaning

**Benefits**:
- Accurate simulation of real advertising behavior
- Proper unique user tracking
- Correct temporal distribution of ad views

## Affected Components

- ✅ data-extraction (spec delta created)
- ✅ auction-engine (spec delta created)

## Implementation Phases

1. **Data Extraction** - Update SQL queries with COUNT(DISTINCT user_id)
2. **Dataclass** - Rename fields in Ad class
3. **Simulation** - Update slot allocation and batch calculations
4. **Reporting** - Update output columns and documentation
5. **Validation** - Add reach ratio checks and tests
6. **Documentation** - Update all references to impressions → reach

## Validation

Before merging:
- [ ] All tests pass with reach calculations
- [ ] Reach ≤ raw_impressions for all ads
- [ ] Reach ratio (reach/impressions) is 30-95%
- [ ] Temporal distribution matches MIN(timestamp) logic
- [ ] Output metrics reflect reach, not impressions

## References

- **Proposal**: [proposal.md](./proposal.md)
- **Tasks**: [tasks.md](./tasks.md)
- **Spec Deltas**:
  - [data-extraction](./specs/data-extraction/spec.md)
  - [auction-engine](./specs/auction-engine/spec.md)
