# Change: Add Detailed Logging and Paid Status Flags

## Why

**Problem 1: Missing Paid Status Classification**

Current reports lack clear indication of whether users/ads are paid or organic:
- Cannot distinguish paying sellers from non-paying sellers
- Cannot see if simulation changed paid/organic status
- Difficult to analyze impact on different user segments
- Business needs to understand "who are the winners/losers among paying customers"

**Problem 2: No Step-by-Step Simulation Visibility**

Current implementation only outputs final results, with no insight into simulation process:
- Cannot verify auction algorithm correctness at each step
- Cannot debug unexpected results (why did Ad X get Y impressions?)
- Cannot trace pressure changes over time
- Cannot see batch-by-batch winner selection
- Cannot understand why ads were paused or excluded
- Difficult to explain results to stakeholders

**Impact:**
- Cannot validate simulation correctness
- Cannot trust results without visibility
- Cannot debug edge cases
- Cannot present clear audit trail to business

## What Changes

Add two major enhancements to auction simulator:

### 1. Paid Status Flags in Reports

**Seller-level reports** (`seller_comparison_*.csv`):
- `is_paid_actual` (boolean): TRUE if seller had at least one paid campaign in actual data
- `is_paid_simulated` (boolean): TRUE if seller spent any budget in simulation

**Ad-level reports** (`ad_comparison_*.csv`):
- `is_paid_actual` (boolean): TRUE if ad had paid campaign (daily_budget > 0) in actual data
- `is_paid_simulated` (boolean): TRUE if ad spent any budget (simulated_spending > 0) in simulation

**Logic:**
```python
# For sellers
is_paid_actual = any(ad.daily_budget > 0 for ad in seller.ads) from budgets_df
is_paid_simulated = seller.simulated_spending > 0

# For ads
is_paid_actual = ad.daily_budget > 0 on any day from budgets_df
is_paid_simulated = ad.simulated_spending > 0
```

**Use cases:**
- Filter reports to show only paying customers
- Identify status changes (organic → paid, or paid → organic)
- Segment analysis (paid vs organic performance)

### 2. Detailed Simulation Logging

**Dual-format logging:**

**File 1: `outputs/simulation_log_TIMESTAMP.jsonl`** (structured)
- Machine-readable JSON Lines format
- Every event logged with timestamp
- Full auction details for programmatic analysis

**File 2: `outputs/simulation_summary_TIMESTAMP.txt`** (human-readable)
- Readable text format with hierarchy
- Top-10 winners per batch
- Summary statistics per hour
- Quick visual scanning

**Events logged:**

1. **Day start/end** - Budget resets, ad counts
2. **Hour start/end** - Category, total impressions, summary
3. **Batch auction** - Eligible ads, top-10 winners with pressure/bid/rank
4. **Pressure changes** - Between batches (Ad X: 10,000 → 9,998)
5. **Pacing exclusions** - Ads paused by pacing gate
6. **Budget exhaustion** - When ads run out of budget mid-simulation
7. **Organic fallback** - Method used, allocations
8. **Conservation checks** - Verify total impressions match

**Example log entry (JSONL):**
```json
{"timestamp": "2024-01-15T10:00:05", "event": "batch_auction", "batch": 1, "category": 1234, "hour": 10, "eligible_ads": 100, "ads_with_budget": 40, "slots": 40, "top_winners": [{"ad_id": 777, "pressure": 13793.5, "rank": 0, "bid": 1.4, "remaining_budget": 9998}, ...]}
```

**Configuration:**
```yaml
logging:
  simulation_log_enabled: true
  log_format: "both"  # jsonl, text, both
  log_top_n_winners: 10  # per batch
  log_pressure_changes: true
  log_pacing_events: true
  log_budget_events: true
```

## Impact

- **Affected files**:
  - `src/auction_simulator/reporting.py` (add is_paid columns)
  - `src/auction_simulator/simulation.py` (add logging calls)
  - `src/auction_simulator/auction_engine.py` (add logging calls)
  - `config/config.yaml` (add logging configuration)

- **Affected systems**: None (internal enhancement only)

- **Data requirements**: None (uses existing data)

- **Business value**:
  - Transparent simulation process
  - Audit trail for results
  - Debug capability for edge cases
  - Clear paid/organic segmentation
  - Stakeholder confidence in results

- **Risk**: Low (additive, backward compatible)

- **Performance**:
  - Logging adds ~5-10% overhead (mostly I/O)
  - JSONL file size: ~1-5MB per simulation day
  - TXT file size: ~500KB-2MB per simulation day
  - Can disable logging if performance critical

- **Testing**:
  - Validate is_paid flags match actual data
  - Verify logging captures all events
  - Check conservation assertions in logs
  - Test logging can be disabled

## Success Criteria

1. ✅ CSV reports include `is_paid_actual` and `is_paid_simulated` columns
2. ✅ Flags correctly identify paid vs organic status
3. ✅ JSONL log contains all auction events with structured data
4. ✅ TXT summary log is human-readable and scannable
5. ✅ Pressure changes between batches are tracked
6. ✅ Pacing exclusions and budget exhaustions are logged
7. ✅ Logs enable step-by-step validation of simulation
8. ✅ Logging can be configured or disabled
9. ✅ Performance impact is acceptable (<15% overhead)
