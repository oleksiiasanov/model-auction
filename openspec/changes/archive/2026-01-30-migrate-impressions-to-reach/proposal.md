# Proposal: Migrate Impressions to Reach

**Change ID**: `migrate-impressions-to-reach`
**Status**: Proposed
**Created**: 2026-01-30

## Why

**The system currently counts all impression events, but the real-world auction operates on REACH (unique users per day per ad).** This fundamental mismatch causes simulation inaccuracy because:
- Same user viewing same ad multiple times = 1 reach, counted as N impressions
- Budgets are calculated per reach, not per impression
- Simulation over-allocates traffic by counting duplicate views

**Example impact:** Ad with 100 impressions from 50 unique users should generate 50 auction slots (reach), not 100 (impressions). Current system inflates traffic by 2x in this example.

## What Changes

**Conceptual shift:** Change core metric from **impressions** (all ad views) to **reach** (unique user_id views per day per ad).

**Data extraction (MAJOR):**
- Add `COUNT(DISTINCT user_id)` as reach metric
- Group by `(date, seller_id, ad_id, hour)` to deduplicate users
- Track reach timestamp as `MIN(timestamp)` (first view in day)

**Simulation (MEDIUM):**
- Allocate reach slots in auction, not impression slots
- Update terminology: `impressions` → `reach` throughout

**Reporting (MEDIUM):**
- Display reach metrics instead of impressions
- Update field names and labels

**Specs (MAJOR):**
- Rewrite requirements with reach terminology
- Document impression vs reach distinction

## Problem Statement

### Current Behavior (WRONG)

```sql
-- Counts ALL events, including duplicates from same user
SELECT COUNT(*) as impressions
FROM enriched_distributed
WHERE date = '2026-05-15'
  AND seller_id = 123
  AND ad_id = 1
-- Result: 100 impressions (may include 50 duplicate views from 50 users)
```

**Simulation allocates 100 auction slots** → WRONG

### Desired Behavior (CORRECT)

```sql
-- Counts UNIQUE users per ad per day
SELECT COUNT(DISTINCT user_id) as reach
FROM enriched_distributed
WHERE date = '2026-05-15'
  AND seller_id = 123
  AND ad_id = 1
-- Result: 50 reach (50 unique users, regardless of repeat views)
```

**Simulation allocates 50 auction slots** → CORRECT

### Real Example

User `user_id=33`, Seller `seller_id=123`:

**Day 2026-05-15:**
| Event | ad_id | user_id | Time |
|-------|-------|---------|------|
| impression_1 | 1 | 33 | 09:00 |
| impression_2 | 1 | 33 | 14:00 |
| impression_3 | 2 | 33 | 18:00 |

- **Impressions**: 3
- **Reach**: 2 (ad_id=1: first at 09:00, ad_id=2: first at 18:00)

**Day 2026-05-16:**
| Event | ad_id | user_id | Time |
|-------|-------|---------|------|
| impression_4 | 1 | 33 | 08:00 |
| impression_5 | 1 | 33 | 10:00 |
| impression_6 | 2 | 33 | 15:00 |
| impression_7 | 3 | 33 | 20:00 |
| impression_8 | 1 | 33 | 22:00 |

- **Impressions**: 5
- **Reach**: 3 (ad_id=1: first at 08:00, ad_id=2: first at 15:00, ad_id=3: first at 20:00)

**Total:** 8 impressions → **5 reach** ✅

## Proposed Solution

### Change 1: Data Extraction - Add Reach Calculation

```sql
-- NEW: Deduplicate users per ad per day per hour
SELECT
    date,
    hour,
    seller_id,
    ad_id,
    COUNT(DISTINCT user_id) as reach,           -- NEW: unique users
    MIN(timestamp) as reach_timestamp,           -- NEW: first view time
    COUNT(*) as total_impressions,               -- Keep for comparison
    SUM(CASE WHEN is_paid THEN 0 ELSE 1 END) as organic_reach  -- NEW
FROM enriched_distributed
WHERE [filters]
GROUP BY date, hour, seller_id, ad_id           -- NEW: group by ad+hour
```

**Key changes:**
1. `COUNT(DISTINCT user_id)` = reach
2. `MIN(timestamp)` = when reach occurred (first view)
3. `GROUP BY` includes seller_id + ad_id to deduplicate per ad
4. Keep `total_impressions` for validation/comparison

### Change 2: Simulation - Allocate Reach Slots

```python
# BEFORE:
total_impressions = sum(ad.impressions for ad in ads)  # Wrong
auction_slots = total_impressions

# AFTER:
total_reach = sum(ad.reach for ad in ads)              # Correct
auction_slots = total_reach
```

### Change 3: Update Terminology

**Field renames:**
- `impressions` → `reach`
- `total_impressions` → `reach_count`
- `simulated_impressions` → `simulated_reach`
- `organic_impressions` → `organic_reach`

**Preserve for comparison:**
- Add `raw_impressions` field (old COUNT(*)) for validation

## Expected Impact

### Metrics Changes

| Metric | Before (Impressions) | After (Reach) | Change |
|--------|---------------------|---------------|---------|
| **Traffic volume** | Higher (duplicates) | Lower (unique) | ⬇️ More accurate |
| **Auction slots** | Inflated | Correct | ⬇️ Matches reality |
| **Budget efficiency** | Overspend | Accurate | ✅ Correct calculation |

### Example Scenario

**Ad with:**
- 1000 raw impressions
- 600 unique users (reach)

**Before (WRONG):** Auction runs for 1000 slots
**After (CORRECT):** Auction runs for 600 slots

**Impact:** 40% reduction in allocated slots = **more accurate simulation**

## Scope

### In Scope

**Data Extraction (HIGH PRIORITY):**
- Update SQL queries to calculate reach
- Add user_id deduplication
- Group by (date, hour, seller_id, ad_id)
- Track reach timestamp (MIN)

**Simulation Engine (HIGH PRIORITY):**
- Use reach instead of impressions for slot allocation
- Update Ad dataclass fields
- Update batch processing logic

**Reporting (MEDIUM PRIORITY):**
- Rename fields in reports
- Update summary statistics
- Show reach metrics

**Specs & Documentation (HIGH PRIORITY):**
- Update all requirements with reach terminology
- Add FAQ explaining impression vs reach
- Document migration rationale

### Out of Scope

- Historical data migration (only affects new simulations)
- UI changes (no UI in MVP)
- Real-time reach tracking (simulation only)

## Dependencies

- **Blocks**: None (standalone change)
- **Blocked by**: None
- **Relates to**: All extraction/simulation changes use new reach metric

## Risks and Mitigations

### Risk 1: Breaking change - old simulations incompatible

- **Severity**: HIGH
- **Mitigation**:
  - Keep raw_impressions field for comparison
  - Add migration flag in config
  - Document breaking change clearly
- **Rollback**: Revert to impression-based queries

### Risk 2: Performance impact (GROUP BY + DISTINCT)

- **Severity**: MEDIUM
- **Mitigation**:
  - ClickHouse optimized for these queries
  - Test on large dataset before deployment
  - Add query execution time monitoring
- **Expected**: Minimal impact (standard aggregation)

### Risk 3: Data quality - missing user_id values

- **Severity**: MEDIUM
- **Mitigation**:
  - Validate user_id coverage in data
  - Handle NULL user_id (exclude from reach)
  - Log warnings if >5% NULL rate
- **Fallback**: Filter `WHERE user_id IS NOT NULL`

### Risk 4: Confusion between impression and reach terminology

- **Severity**: LOW
- **Mitigation**:
  - Clear documentation in FAQ
  - Consistent naming throughout
  - Add comments in code explaining distinction

## Validation Plan

### Phase 1: Data Validation

1. **Query testing:** Run new reach queries on historical data
2. **Ratio check:** Validate reach/impression ratio reasonable (e.g., 0.4-0.8)
3. **NULL check:** Verify user_id coverage >95%

### Phase 2: Simulation Testing

1. **1-day test:** Run simulation with reach metrics
2. **Compare:** Reach-based vs impression-based results
3. **Validate:** Slot counts match reach, not impressions

### Phase 3: Metrics Validation

1. **Reports:** Verify all metrics use reach terminology
2. **Totals:** Check conservation (allocated reach = total reach)
3. **Accuracy:** Compare to real-world data

## Questions for Stakeholders

1. **Urgency:** Is this blocking production launch? (Likely YES - accuracy critical)
2. **Data quality:** Confirmed user_id field is reliable in ClickHouse?
3. **Terminology:** Prefer "reach" or "unique impressions" or other term?
4. **Migration:** Need to re-run old simulations with new metric?

## Success Criteria

- ✅ All queries calculate reach (COUNT DISTINCT user_id)
- ✅ Simulation allocates reach slots, not impression slots
- ✅ Reports display reach metrics
- ✅ Field names updated throughout codebase
- ✅ FAQ documents impression vs reach
- ✅ Validation shows reasonable reach/impression ratios
- ✅ Test simulation runs successfully
- ✅ Specs updated with reach requirements

## References

- **User example:** 8 impressions → 5 reach (documented above)
- **Current code:** [data_extraction.py](../../auction-simulator/src/auction_simulator/data_extraction.py)
- **Simulation:** [simulation.py](../../auction-simulator/src/auction_simulator/simulation.py)
