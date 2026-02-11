# Spec Delta: Migrate Impressions to Reach (Auction Engine)

**Capability**: auction-engine
**Change**: migrate-impressions-to-reach

---

## MODIFIED Requirements

### Requirement: First-Price Auction Winner Selection

The system SHALL select top N winners by effective_bid and allocate **REACH slots**, not impression slots.

**TERMINOLOGY CHANGE:**
- **OLD**: "impression slots" = any ad view
- **NEW**: "reach slots" = unique user viewing ad

**RATIONALE**: Auction operates on reach (unique users), not impressions (repeat views).

#### Scenario: Allocate reach slots in auction

- **WHEN** running auction batch
- **THEN** total_slots = total_reach (not total_impressions)
- **EXAMPLE**:
  - Ad A: 300 reach, 450 impressions
  - Ad B: 200 reach, 350 impressions
  - Total auction slots = 500 reach (not 800 impressions)
- **IMPACT**: Correct slot allocation matches real-world behavior

#### Scenario: Winner receives reach count

- **WHEN** ad wins auction
- **THEN** ad.simulated_reach increments by allocated_reach_count
- **PREVIOUS**: `ad.simulated_impressions` (incorrect metric)
- **NEW**: `ad.simulated_reach` (correct metric)

#### Scenario: Batch size operates on reach

- **WHEN** calculating batches per hour
- **THEN** `num_batches = ceil(total_reach / batch_size)`
- **EXAMPLE**:
  - total_reach = 520
  - batch_size = 40
  - num_batches = ceil(520/40) = 13 batches
- **PREVIOUS**: Used total_impressions (inflated)

---

## MODIFIED Requirements

### Requirement: All Ads from Period Participate in Single Auction

The system SHALL include all ads with **reach** data (not just impression data) in auction.

#### Scenario: Ad eligibility based on reach

- **WHEN** ad has reach > 0 in simulation period
- **THEN** ad participates in auction
- **PREVIOUS**: Based on impressions > 0
- **CONSISTENCY**: Metric alignment across system

---

## MODIFIED Requirements

### Requirement: Budget Deduction and State Update

The system SHALL update **simulated_reach counters** (not impression counters) after each batch.

#### Scenario: Increment reach counter on win

- **WHEN** ad wins auction and receives `allocated_reach` slots
- **THEN**
  - `ad.simulated_reach += allocated_reach` (NEW field name)
  - `ad.remaining_budget -= cost`
  - `ad.actual_spend += cost`
- **PREVIOUS**: `ad.simulated_impressions += count`

#### Scenario: Organic reach fallback

- **WHEN** distributing remaining reach slots among simulated organic ads
- **THEN** use `ad.organic_reach_historical` for proportional distribution
- **PREVIOUS**: `ad.organic_impressions_historical`
- **CONSISTENCY**: All metrics based on reach

---

## ADDED Requirements

### Requirement: Reach Timestamp Tracking

The system SHALL track when each reach occurred using first-view timestamp.

#### Scenario: Reach assigned to hour of first view

- **WHEN** user views ad multiple times in day
- **THEN** reach timestamp = MIN(timestamp) of all views that day
- **EXAMPLE**:
  - User 33 views ad_id=1 at 09:00, 14:00, 22:00 on 2026-05-15
  - reach_timestamp = 09:00
  - This reach allocated to hour 9 auction batch
- **PURPOSE**: Correct temporal distribution of reach

#### Scenario: Reach counted once per day per user per ad

- **WHEN** same user views same ad on different days
- **THEN** each day generates separate reach count
- **EXAMPLE**:
  - User 33 views ad_id=1 on 2026-05-15 (3 times) → 1 reach
  - User 33 views ad_id=1 on 2026-05-16 (2 times) → 1 reach
  - Total: 2 reach across 2 days (not 1, not 5)

---

## Implementation Notes

### Ad Dataclass Changes

**File**: `src/auction_simulator/auction_engine.py`

**BEFORE:**
```python
@dataclass
class Ad:
    ...
    simulated_impressions: int
    organic_impressions_historical: int
```

**AFTER:**
```python
@dataclass
class Ad:
    ...
    simulated_reach: int  # RENAMED
    organic_reach_historical: int  # RENAMED
    raw_impressions_historical: int = 0  # NEW: for comparison
```

### Simulation Changes

**File**: `src/auction_simulator/simulation.py`

**Slot allocation:**
```python
# BEFORE:
total_impressions = sum(ad.total_impressions for ad in ads_hour)
num_batches = math.ceil(total_impressions / batch_size)

# AFTER:
total_reach = sum(ad.reach for ad in ads_hour)
num_batches = math.ceil(total_reach / batch_size)
```

**Winner charging:**
```python
# BEFORE:
ad.simulated_impressions += count

# AFTER:
ad.simulated_reach += count
```

### Validation

**Check 1: Reach < Impressions**
```python
assert ad.reach <= ad.raw_impressions, \
    f"Ad {ad.ad_id}: reach ({ad.reach}) > impressions ({ad.raw_impressions})"
```

**Check 2: Reach ratio reasonable**
```python
ratio = ad.reach / ad.raw_impressions
assert 0.3 <= ratio <= 0.95, \
    f"Ad {ad.ad_id}: unusual reach ratio {ratio:.1%}"
```

---

## Cross-References

- **Related spec delta**: `data-extraction` spec (SQL changes)
- **FAQ entry**: "Impression vs Reach" in terminology section

---

## Revision History

- **2026-01-30**: Initial spec delta (migrate-impressions-to-reach)
