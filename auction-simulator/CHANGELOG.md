# Changelog

All notable changes to the Auction Simulator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **CRITICAL: Zero-budget ads winning paid auction slots**: Fixed ads without budget participating in paid auction
  - Changed `run_batch_auction()` to receive only `ads_with_budget` instead of all ads
  - **Impact**: Organic ads coverage improved from 3% → 54% (17.8x)
  - **Impact**: Organic fallback slots increased from 0.3% → 78% (280x)
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-1-zero-budget-ads-winning-paid-auction-slots)

- **CRITICAL: Batch auction early termination bug**: Fixed premature auction exit when paid ads < batch_size
  - Removed `if allocated < current_batch: break` that stopped auction after first batch
  - Now continues processing batches until all slots allocated OR budget exhausted
  - Each batch: paid auction first, organic fallback fills remaining slots
  - **Impact**: Budget utilization improved from 3.3% → 46.9% (+1,318%)
  - **Impact**: Paid reach increased from ~16 → 1,878 (+117x)
  - **Impact**: Organic reach decreased from ~10,400 → 8,531 (more realistic)
  - **Impact**: Paid ads now participate in 5-10 batches per hour (was 1)
  - See [openspec/changes/fix-batch-auction-early-termination](../../openspec/changes/fix-batch-auction-early-termination/)

- **CRITICAL: Pacing gate hour zero blocking**: Fixed all paid ads blocked at hour 0
  - Added `min_time_progress_threshold: 0.042` to prevent `max_allowed=0` at hour 0
  - **Impact**: Paid impressions corrected from 98.5% → ~3.6% (27x reduction)
  - **Impact**: Organic impressions corrected from 1.5% → ~96.4% (64x increase)
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-4-pacing-gate-hour-zero-blocking)
  - See [openspec/changes/fix-pacing-gate-hour-zero](../../openspec/changes/archive/2026-01-30-fix-pacing-gate-hour-zero/)

- **Fractional kopecks rounding**: Fixed budgets not decreasing due to integer rounding
  - Changed `daily_budget` and `remaining_budget` from `int` to `float`
  - Removed rounding in cost deduction
  - **Impact**: Budgets now decrease correctly, N decreases naturally throughout day
  - **Impact**: Spending accuracy improved from broken → 91-94% accurate
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-5-fractional-kopecks-rounding)
  - See [openspec/changes/fix-fractional-kopecks-bid-step](../../openspec/changes/archive/2026-02-04-fix-fractional-kopecks-bid-step/)

- **Organic fallback allocation**: Changed from `organic_reach_historical` to `total_reach_historical` for proportional distribution
  - Fixes 1,471 promoted-without-budget ads that received 0 simulated reach (now 100% receive reach)
  - Fixes 3,156 low-reach organic ads with floored proportions (improved coverage from 44% to 99.3%)
  - Ads popular when promoted now receive organic reach when slots available
  - Better reflects overall ad popularity rather than just organic-only views
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-3-organic-fallback-used-wrong-historical-metric)
  - See [openspec/changes/use-total-reach-for-organic-fallback](../../openspec/changes/archive/2026-02-04-use-total-reach-for-organic-fallback/)

### Changed
- **Batch auction loop**: Organic fallback now called per-batch instead of once at end
- **`run_hour_auction()` return type**: Changed from `int` → `dict` with keys `batch_count`, `paid_slots`, `organic_slots`
- Ad model field renamed: `organic_reach_historical` → `total_reach_historical`
- Data extraction now aggregates `total_reach` instead of `organic_reach` for fallback proportions
- Updated organic fallback docstrings and comments to reflect new allocation basis
- Added `daily_budget_azn` column to `ad_comparison.csv` output for budget analysis
- **Organic fallback pool split**: Added 80%/20% split between free ads and paid-exhausted ads
  - Free ads receive 80% of organic slots
  - Paid-exhausted ads receive 20% of organic slots
  - Configurable via `organic_fallback.free_share` in config.yaml
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-2-batch-auction-early-termination) for context
- **Cumulative allocator**: Added carry-over mechanism for organic fallback
  - Preserves fractional allocations across batches
  - Significantly improves coverage for long-tail ads (ads with small historical reach)
  - Uses two carry states: `carry_free` and `carry_paid_exhausted`
  - Enabled by default (`use_cumulative_allocator: true`)
- **Bid step reduced**: Changed from 0.1 to 0.003 kopecks
  - Better matches actual market prices
  - Improved spending accuracy from 120% → 91-94%
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-5-fractional-kopecks-rounding) for context
  - See [openspec/changes/fix-fractional-kopecks-bid-step](../../openspec/changes/archive/2026-02-04-fix-fractional-kopecks-bid-step/)
- **Pacing gate hour zero fix**: Added `min_time_progress_threshold: 0.042` configuration
  - Prevents zero-value edge case at hour 0
  - Symmetric to existing `min_time_left_threshold` pattern
  - See [CRITICAL_BUGS.md](CRITICAL_BUGS.md#bug-4-pacing-gate-hour-zero-blocking) for details

## [0.1.0] - 2024-01-23

### Added
- Initial implementation of auction-based traffic distribution simulator
- Pressure-based auction engine with first-price bidding
- Pacing gate to prevent budget dumping
- Multi-day simulation with daily budget resets
- Total impression conservation with organic fallback
- Proportional organic distribution using historical data
- Equal organic distribution fallback
- Data extraction from ClickHouse (enriched_distributed, spendings_distributed)
- Local caching with configurable TTL
- Comparison reporting (seller-level, ad-level, summary statistics)
- CLI interface with comprehensive options
- Unit tests for core auction logic
- Configuration management with YAML files
- README with installation and usage instructions
- QUICKSTART guide for new users

### Features
- **Auction Engine**:
  - Pressure calculation: `pressure = remaining_budget / time_left`
  - Effective bid: `min_bid + (N - 1 - rank_index) * bid_step`
  - Batch processing (default 40 impressions per batch)
  - Dynamic recomputation per batch

- **Pacing Gate**:
  - Formula: `expected_spend = daily_budget * time_progress`
  - 20% tolerance (configurable)
  - Automatic resume when time catches up

- **Conservation**:
  - Total impressions conserved exactly
  - Proportional organic fallback with remainder distribution
  - Mathematical guarantees with assertions

- **Data Handling**:
  - Full day granularity (YYYY-MM-DD)
  - Hourly time steps (24 hours per day)
  - Multi-category support
  - Currency in kopecks (1/100 currency unit)
  - Automatic JOIN deduplication for campaigns

### Configuration
- Epsilon: 0.001 (division by zero prevention)
- Pacing tolerance: 0.2 (20%)
- Min time progress threshold: 0.042 (prevents hour 0 blocking)
- Bid step: 0.003 kopecks (reduced from 0.1 for better accuracy)
- Batch size: 40 impressions
- Min bid fallback: 100 kopecks
- Cache TTL: 24 hours
- Organic fallback free share: 0.8 (80% free, 20% paid-exhausted)
- Cumulative allocator: Enabled by default

### Known Limitations (MVP)
- Full days only (no partial days)
- Hourly granularity (not minute-level)
- Category feed only (feed_id='6500')
- Ad-level auction (not user-level or seller-level)
- No Reach Profile rotation (all ads always eligible)
- Schema-dependent min_bid calculation (may require JOIN)

### Technical Details
- Python 3.8+ required
- Dependencies: pandas, clickhouse-driver, click, pyyaml, pytest
- Tested on: macOS, Linux (Windows compatibility expected but untested)
- Performance: ~1-5 minutes for data extraction, ~30s-2min for simulation

### Documentation
- README.md: Comprehensive installation and usage guide
- QUICKSTART.md: Quick start guide for new users
- OpenSpec proposal: ../openspec/changes/add-auction-simulator/proposal.md
- OpenSpec design: ../openspec/changes/add-auction-simulator/design.md
- Detailed specs in ../openspec/changes/add-auction-simulator/specs/

## [Unreleased]

### Planned for Future Versions
- User-level auction (session-based uniqueness)
- Reach Profile rotation support
- Minute-level granularity
- Search and filtered view support
- Real-time simulation mode
- Web UI for visualization
- Export to Excel with charts
- Sensitivity analysis tools
- Multi-country batch simulation
- Performance optimizations for large datasets
