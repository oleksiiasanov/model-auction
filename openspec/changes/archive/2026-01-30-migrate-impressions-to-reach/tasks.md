# Implementation Tasks: Migrate Impressions to Reach

**Change ID**: `migrate-impressions-to-reach`

## Overview

Migrate from impression-based counting (all views) to reach-based counting (unique users per day per ad).

**Estimated effort**: 1-2 days
**Risk level**: HIGH (breaking change, core metric shift)

---

## Phase 1: Data Extraction Updates (HIGH PRIORITY)

### Task 1.1: Update fetch_ads_from_clickhouse() to calculate reach

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Line ~240-264

**Changes:**
```python
# BEFORE:
SELECT
    category_id,
    ad_id,
    lister_user_id as seller_id,
    data_chunk_date as date,
    toHour(timestamp) as hour,
    COUNT(*) as total_impressions,  # All events
    SUM(CASE WHEN campaign_show_ad = 'True' THEN 0 ELSE 1 END) as organic_impressions
FROM enriched_distributed
GROUP BY category_id, ad_id, lister_user_id, date, hour

# AFTER:
SELECT
    category_id,
    ad_id,
    lister_user_id as seller_id,
    data_chunk_date as date,
    toHour(timestamp) as hour,
    COUNT(DISTINCT user_id) as reach,  # Unique users
    MIN(timestamp) as reach_timestamp,  # First view time
    COUNT(*) as raw_impressions,  # Keep for comparison
    COUNT(DISTINCT CASE WHEN campaign_show_ad != 'True' THEN user_id END) as organic_reach
FROM enriched_distributed
WHERE user_id IS NOT NULL  # NEW: filter nulls
GROUP BY category_id, ad_id, lister_user_id, date, hour
```

**Key changes:**
1. Add `COUNT(DISTINCT user_id)` as reach
2. Add `MIN(timestamp)` as reach_timestamp
3. Rename `total_impressions` → `raw_impressions`
4. Update organic to `COUNT(DISTINCT ... user_id)`
5. Filter `WHERE user_id IS NOT NULL`

**Validation:** Query compiles and returns data

---

### Task 1.2: Update data structure to use reach fields

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Lines ~270-290 (result processing)

**Changes:**
```python
# BEFORE:
ads_dict[key]['total_impressions'] += row[5]
ads_dict[key]['organic_impressions'] += row[6]

# AFTER:
ads_dict[key]['reach'] += row[5]  # reach count
ads_dict[key]['reach_timestamp'] = min(
    ads_dict[key].get('reach_timestamp', row[6]),
    row[6]  # MIN(timestamp)
)
ads_dict[key]['raw_impressions'] += row[7]  # keep for validation
ads_dict[key]['organic_reach'] += row[8]
```

**Validation:** Data structure matches new schema

---

### Task 1.3: Update calculate_min_bid_per_category() impressions query

**File**: `auction-simulator/src/auction_simulator/data_extraction.py`
**Location**: Line ~490-508

**Changes:**
```python
# Impressions CTE - use reach instead
category_impressions AS (
    SELECT
        COUNT(DISTINCT user_id) as paid_reach  # was: COUNT(*)
    FROM enriched_distributed i
    WHERE
        ...
        AND user_id IS NOT NULL  # NEW
```

**Rationale:** min_bid = spending / reach (not impressions)

**Validation:** min_bid values reasonable

---

## Phase 2: Ad Dataclass Updates

### Task 2.1: Update Ad dataclass fields

**File**: `auction-simulator/src/auction_simulator/auction_engine.py`
**Location**: Line ~15-27

**Changes:**
```python
@dataclass
class Ad:
    ad_id: int
    seller_id: int
    category_id: int
    daily_budget: float
    remaining_budget: float
    actual_spend: float
    simulated_reach: int  # was: simulated_impressions
    simulated_spending: float
    organic_reach_historical: int  # was: organic_impressions_historical

    # NEW: Additional tracking fields
    raw_impressions_historical: int = 0  # For comparison
```

**Validation:** Tests updated to match new fields

---

### Task 2.2: Update Ad initialization

**File**: `auction-simulator/src/auction_simulator/simulation.py`
**Location**: Line ~180-220 (ad loading)

**Changes:**
```python
# BEFORE:
ad = Ad(
    ...,
    simulated_impressions=0,
    organic_impressions_historical=row['organic_impressions']
)

# AFTER:
ad = Ad(
    ...,
    simulated_reach=0,
    organic_reach_historical=row['organic_reach'],
    raw_impressions_historical=row['raw_impressions']  # NEW
)
```

**Validation:** Ads load correctly with new fields

---

## Phase 3: Simulation Engine Updates

### Task 3.1: Update slot allocation to use reach

**File**: `auction-simulator/src/auction_simulator/simulation.py`
**Location**: Line ~250-280 (batch loop)

**Changes:**
```python
# BEFORE:
total_impressions = sum(ad.total_impressions for ad in ads_in_hour)
for batch_num in range(math.ceil(total_impressions / batch_size)):
    ...

# AFTER:
total_reach = sum(ad.reach for ad in ads_in_hour)  # NEW
for batch_num in range(math.ceil(total_reach / batch_size)):
    # Allocate reach slots, not impression slots
    ...
```

**Validation:** Slot counts match reach, not impressions

---

### Task 3.2: Update winner charging to increment reach

**File**: `auction-simulator/src/auction_simulator/auction_engine.py`
**Location**: Line ~220-240 (charge_winners)

**Changes:**
```python
# BEFORE:
ad.simulated_impressions += count

# AFTER:
ad.simulated_reach += count  # Field renamed
```

**Validation:** Reach counters increment correctly

---

### Task 3.3: Update organic fallback to use reach

**File**: `auction-simulator/src/auction_simulator/auction_engine.py`
**Location**: Line ~180-210 (organic fallback)

**Changes:**
```python
# BEFORE:
proportions = {
    ad.ad_id: ad.organic_impressions_historical
    for ad in ads
}

# AFTER:
proportions = {
    ad.ad_id: ad.organic_reach_historical  # Field renamed
    for ad in ads
}
```

**Validation:** Fallback distribution uses organic reach

---

## Phase 4: Reporting Updates

### Task 4.1: Update summary statistics field names

**File**: `auction-simulator/src/auction_simulator/reporting.py`
**Location**: Line ~50-100

**Changes:**
```python
# Update all report outputs:
# "Total Impressions" → "Total Reach"
# "Paid Impressions" → "Paid Reach"
# "Organic Impressions" → "Organic Reach"
# "Simulated Impressions" → "Simulated Reach"
```

**Validation:** Reports display correct terminology

---

### Task 4.2: Add reach/impression comparison

**File**: `auction-simulator/src/auction_simulator/reporting.py`
**Location**: Line ~150-180 (new section)

**Add section:**
```python
# NEW: Reach vs Impressions Comparison
report += "\n## Reach vs Impressions\n"
report += f"Total Raw Impressions: {total_raw_impressions}\n"
report += f"Total Reach: {total_reach}\n"
report += f"Reach/Impression Ratio: {total_reach / total_raw_impressions:.2%}\n"
```

**Validation:** Ratio displayed, typically 40-80%

---

## Phase 5: Validation & Testing

### Task 5.1: Data quality validation

**Action**: Run SQL queries manually

**Checks:**
```sql
-- Check 1: Verify user_id coverage
SELECT
    COUNT(*) as total,
    COUNT(user_id) as with_user_id,
    COUNT(user_id) * 100.0 / COUNT(*) as coverage_pct
FROM enriched_distributed
WHERE data_chunk_date = '2026-01-22'
  AND country_id = 13;
-- Expect: coverage_pct > 95%

-- Check 2: Verify reach < impressions
SELECT
    ad_id,
    COUNT(*) as impressions,
    COUNT(DISTINCT user_id) as reach,
    reach * 100.0 / impressions as reach_ratio
FROM enriched_distributed
WHERE data_chunk_date = '2026-01-22'
GROUP BY ad_id
LIMIT 10;
-- Expect: reach_ratio between 40-80%
```

**Validation:** Data quality acceptable

---

### Task 5.2: Run 1-day simulation with reach

**Command:**
```bash
./venv/bin/python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1361 \
  --time-from 2026-01-22 \
  --time-to 2026-01-22
```

**Check:**
- Simulation completes without errors
- Logs show "reach" terminology
- Allocated slots = reach count (not impression count)

**Evidence:**
```
INFO: Loaded 85 ads with total reach: 12,450
INFO: Hour 0: Allocating 520 reach slots (was: 780 impression slots)
```

---

### Task 5.3: Compare reach vs impression results

**Action**: Run simulation twice (if possible):
1. With reach-based code (new)
2. With impression-based code (old, via git checkout)

**Compare:**
- Slot allocation counts
- Budget spending rates
- N (ads with budget) stability

**Expected**: Reach-based allocates fewer slots, more accurate spending

---

## Phase 6: Documentation

### Task 6.1: Update specs with reach terminology

**Files**:
- `openspec/specs/data-extraction/spec.md`
- `openspec/specs/auction-engine/spec.md`

**Changes**: Search/replace throughout:
- "impression" → "reach" (where appropriate)
- Add reach definition scenarios

**Validation**: Specs consistent with code

---

### Task 6.2: Add FAQ entry: Impression vs Reach

**File**: `auction-simulator/docs/faq/01-terminology.md`

**New entry:**
```markdown
## Impression vs Reach

**🏷️ Теги:** `terminology`, `metrics`, `reach`, `impression`

**❓ Питання:**
Яка різниця між impression і reach?

**💡 Коротка відповідь:**
- **Impression** = всі покази (включно з повторними)
- **Reach** = унікальні user_id в рамках доби по ad_id

**📚 Детальна відповідь:**

### Приклад:
User ID 33 бачить ad_id=1 двічі в день 2026-05-15:
- **Impressions**: 2
- **Reach**: 1 (унікальний user)

**Система працює з REACH**, тому що:
- Бюджети платять за унікальні покази
- Аукціон розподіляє reach slots
- Повторні impressions не генерують додаткову оплату

**💻 Код:**
```sql
-- Impressions (старе):
SELECT COUNT(*) FROM events
-- Reach (нове):
SELECT COUNT(DISTINCT user_id) FROM events
GROUP BY date, ad_id
```
```

**Validation:** FAQ entry clear and helpful

---

## Dependencies

```
Phase 1 (Data Extraction) ──→ Phase 2 (Dataclass) ──→ Phase 3 (Simulation)
                                                          ↓
                                                       Phase 4 (Reporting)
                                                          ↓
                                              Phase 5 (Validation)
                                                          ↓
                                              Phase 6 (Documentation)
```

## Completion Criteria

- ✅ All SQL queries calculate reach (COUNT DISTINCT user_id)
- ✅ Ad dataclass fields renamed (reach, not impressions)
- ✅ Simulation allocates reach slots
- ✅ Reports show reach metrics
- ✅ FAQ documents impression vs reach
- ✅ Validation confirms reach/impression ratio reasonable (40-80%)
- ✅ Test simulation runs successfully
- ✅ Specs updated

## Rollback Plan

If critical issues found:
1. Git revert all changes
2. Restore impression-based queries
3. Re-run simulations
4. Investigate root cause before retry

Keep git commits atomic (one phase per commit) for easy rollback.

## Notes

- **BREAKING CHANGE**: Old simulation results not comparable
- **Data dependency**: Requires user_id field in ClickHouse
- **Performance**: DISTINCT may be slower, but ClickHouse optimized
- **Accuracy**: Critical fix - reach is correct metric, impressions inflate traffic
