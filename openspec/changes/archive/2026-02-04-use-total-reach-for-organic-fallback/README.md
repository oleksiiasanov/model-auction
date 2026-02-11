# Use total_reach_historical for Organic Fallback Allocation

**Status**: Proposed ⏳
**Type**: Enhancement / Bug Fix
**Priority**: High
**Complexity**: Medium

## Summary

Fix organic fallback allocation to use `total_reach_historical` (paid + organic reach) instead of `organic_reach_historical` (organic-only reach) for proportional distribution. This fixes 4,627 ads (56% of organic ads) receiving zero simulated reach.

## Problem

Current implementation uses `organic_reach_historical` which:
1. Excludes 1,471 ads promoted without budget records (27,248 missed reach)
2. Floors 3,156 low-reach ads to zero allocation (12,145 missed reach)
3. Doesn't reflect simulation goal: optimize based on overall popularity

## Solution

Change proportional allocation basis from `organic_reach_historical` to `total_reach_historical`:
- Ads popular when promoted also get organic reach when slots available
- Better represents overall ad popularity, not just historical organic segment
- Reduces zero-reach ads from 4,627 (56%) to ~1,200 (15%)

## Impact

**Positive:**
- ✅ 1,471 promoted-without-budget ads now receive ~27,248 reach
- ✅ Better allocation for 3,156 low-reach ads
- ✅ Organic coverage: 3,639 (44%) → ~7,000+ (85%+)
- ✅ More accurate simulation of reach optimization

**Trade-offs:**
- ⚠️ Pure-organic ads may get slightly less reach (shared with more ads)
- ⚠️ Changes organic distribution pattern (intended improvement)

## Files Changed

- `src/auction_simulator/models/ad.py` - Rename field
- `src/auction_simulator/simulation.py` - Update data extraction
- `src/auction_simulator/auction_engine.py` - Update organic fallback logic

## Next Steps

1. Review and approve proposal
2. Implement code changes (7 tasks)
3. Run validation tests
4. Run full simulation and verify improvements
5. Update documentation

## Quick Links

- [Full Proposal](proposal.md)
- [Task List](tasks.md)
- [Spec Delta](specs/organic-fallback-allocation/spec.md)
