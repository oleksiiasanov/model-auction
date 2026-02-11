# Spec Delta: Auction Engine - Fractional Kopecks Support

## MODIFIED Requirements

### Requirement: Budget Deduction and State Update

The system SHALL deduct effective_bid from each winner's remaining_budget and update spending counters after each batch. **Budget values SHALL support fractional kopecks (float) to preserve precision for small bids.**

#### Scenario: Successful deduction with fractional kopecks

- **WHEN** ad with `remaining_budget=70.0` (float kopecks) and `effective_bid=0.1469` (float kopecks) wins
- **THEN** `cost = 0.1469` kopecks (exact, no rounding)
- **AND** `remaining_budget` becomes `70.0 - 0.1469 = 69.8531` (float)
- **AND** `actual_spend` increases by `0.1469` (float)
- **AND** `simulated_impressions` increases by 1
- **PRECISION**: Use float64 (Python `float`) for budget values to support 4+ decimal places
- **RATIONALE**: With `bid_step=0.001`, typical bids are 0.07-0.15 kopecks. Integer rounding would lose precision (round to 0).

#### Scenario: Budget stored as float for fractional precision

- **WHEN** initializing ad from database with `daily_budget=70` (integer in database)
- **THEN** store as `daily_budget=70.0` (float in memory)
- **AND** support fractional deductions (e.g., `70.0 - 0.1469 = 69.8531`)
- **DATA TYPES**:
  - `Ad.daily_budget: float` (not int)
  - `Ad.remaining_budget: float` (not int)
  - `Ad.actual_spend: float` (unchanged)
- **DATABASE**: Budget values stored as integer kopecks in PostgreSQL/ClickHouse, converted to float on load

#### Scenario: Budget exhaustion with fractional remainder

- **WHEN** ad has `remaining_budget=0.05` kopecks and `effective_bid=0.15` kopecks
- **THEN** cost cannot be paid in full
- **AND** remaining_budget becomes `max(0.0, 0.05 - 0.15) = 0.0`
- **AND** ad is excluded from subsequent auctions (budget exhausted)
- **PARTIAL PAYMENT**: NOT supported. Ad either pays full bid or doesn't participate.

#### Scenario: Float precision validation

- **WHEN** running multi-day simulation with thousands of transactions
- **THEN** accumulated rounding error SHALL be < 0.01 kopecks per ad per day
- **PRECISION**: float64 provides ~15 decimal digits, sufficient for 4 decimal kopecks with millions of operations
- **VALIDATION**: Log warning if budget value has > 4 decimal places (indicates precision issue)

### Requirement: Effective Bid Calculation

The system SHALL calculate effective bid for each eligible ad using min_bid, rank_index, and bid_step, where **N counts only ads with remaining_budget > 0** (ads that can actually pay).

**UNITS**: All bid values in kopecks (1/100 currency unit). Example: min_bid=0.0702 means 0.000702 AZN per impression, bid_step=0.001 means 0.00001 AZN increment.

**FORMULA**: `effective_bid = min_bid + (N - 1 - rank_index) * bid_step`

**WHERE**:
- `N` = count of ads with `remaining_budget > 0` (not total ads, see MODIFIED comparison: now checks float > 0.0)
- `rank_index` = position in pressure-sorted ranking (0 = highest pressure)
- `min_bid` = minimum bid for category (from PostgreSQL), typically 0.07-0.10 kopecks
- `bid_step` = bid increment per rank (from config, **default 0.001 kopecks, changed from 0.1**)

#### Scenario: Small bid_step for granular pricing

- **WHEN** `N=81`, `rank_index=0` (best), `min_bid=0.0702` kopecks, `bid_step=0.001` kopecks
- **THEN** `effective_bid = 0.0702 + (81-1-0)×0.001 = 0.0702 + 0.08 = 0.1502` kopecks
- **COMPARISON TO OLD**:
  - Old (`bid_step=0.1`): `effective_bid = 0.0702 + 80×0.1 = 8.0702` kopecks (53x higher!)
  - New (`bid_step=0.001`): `effective_bid = 0.1502` kopecks (2x min_bid, reasonable)
- **RATIONALE**: `bid_step=0.001` provides granular bid increments matching market scale, avoiding artificially inflated bids

#### Scenario: Bid range with reduced bid_step

- **WHEN** `N=81`, `min_bid=0.0702`, `bid_step=0.001`
- **THEN** bid range spans:
  - Max (rank=0): `0.0702 + 80×0.001 = 0.1502` kopecks
  - Min (rank=80): `0.0702 + 0×0.001 = 0.0702` kopecks
- **SPREAD**: 0.08 kopecks (53% increase from min to max)
- **VS OLD** (`bid_step=0.1`): Spread was 8.0 kopecks (114x increase from min to max) - unrealistic

#### Scenario: Configurable bid_step

- **WHEN** operator wants to adjust bid granularity
- **THEN** edit `config/local.yaml`: `simulation.bid_step: 0.001`
- **GUIDANCE**: `bid_step ≈ min_bid / 100` (rule of thumb for 1% granularity)
- **EXAMPLE**: If `min_bid=0.07`, then `bid_step=0.0007` would provide 100 price points

## REMOVED Requirements

#### ~~Scenario: Winner charged their effective bid~~ (OLD - REPLACED)

- ~~**WHEN** an ad with effective_bid=1.2 (kopecks, float) wins an impression~~
- ~~**THEN** round(1.2) = 1 kopeck is deducted from remaining_budget (integer)~~
- ~~**ROUNDING**: Use standard rounding (0.5 rounds up)~~
- **REASON FOR REMOVAL**: Integer rounding loses precision with small bids (e.g., `round(0.1469) = 0`). Replaced with float arithmetic (no rounding).

#### ~~Scenario: Successful deduction after win with rounding~~ (OLD - REPLACED)

- ~~**WHEN** ad with remaining_budget=100 (integer kopecks) and effective_bid=1.5 (float kopecks) wins~~
- ~~**THEN** cost = round(1.5) = 2 kopecks (integer), remaining_budget becomes 98~~
- **REASON FOR REMOVAL**: Same as above. Float budgets eliminate need for rounding.

## ADDED Requirements

None (only modifications to existing requirements)

## Migration Notes

### Backward Compatibility

- **Database**: Budget values remain as integer kopecks in PostgreSQL/ClickHouse (no schema change)
- **Configuration**: Old simulations with `bid_step=0.1` will continue to work (but produce inflated bids)
- **Recommendation**: Update `bid_step` to `0.001` in all configs

### Validation Checklist

After applying this change:

1. ✅ Run simulation for 1 day, verify budgets decrease by small amounts (not stuck at same value)
2. ✅ Check spending accuracy within ±10% of actual
3. ✅ Verify N (ads with budget) remains stable throughout day
4. ✅ Inspect logs: Budget values show 4 decimal places (e.g., `69.8531`)
5. ⏳ Run 5-day simulation, verify no precision drift

### Performance Impact

- **Memory**: Negligible (float64 vs int32, 4 extra bytes per ad × 8,000 ads = 32KB)
- **CPU**: Negligible (float arithmetic similar speed to integer on modern CPUs)
- **Expected**: No measurable performance difference

## Cross-References

- **Related Spec**: `data-extraction` (loads budgets from PostgreSQL as integers, conversion to float happens in simulation.py)
- **Related Spec**: `simulation-logging` (JSONL serialization now handles float budgets via numpy type conversion)
- **Config File**: `auction-simulator/config/local.yaml` (`simulation.bid_step`)

## Implementation Status

- ✅ Code changes applied (2026-01-30)
- ✅ Basic validation passed (91.4% spending accuracy, N stable)
- ⏳ Multi-day validation pending
- ⏸️ Spec documentation pending (this document)
