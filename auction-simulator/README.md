# Auction-Based Traffic Distribution Simulator

Offline simulation system to test auction-based ad distribution before production deployment.

## Overview

This simulator validates that an auction-based model (where ads compete with algorithmic bids based on budget urgency) can make the ad distribution system fairer and more predictable.

**Key Features:**
- First-price auction with pressure-based ranking
- Pacing gate to prevent budget dumping
- Total impression conservation (paid + organic)
- Multi-day simulation with daily budget resets
- Comparison reporting (actual vs simulated)

## Installation

### 1. Create Virtual Environment

```bash
cd auction-simulator
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Database Connection

```bash
cp config/config.yaml config/local.yaml
# Edit config/local.yaml with your ClickHouse credentials
```

**Important:** `config/local.yaml` is gitignored. Never commit credentials!

## Usage

### Basic Simulation

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234,5678 \
  --time-from 2024-01-15 \
  --time-to 2024-01-17 \
  --config config/local.yaml
```

### Fresh Run with Cleanup

To start with a clean slate (removes cache and old outputs):

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234,5678 \
  --time-from 2024-01-15 \
  --time-to 2024-01-17 \
  --clean
```

Output:
```
Cleaning up before simulation...
  Cache: 12 files removed (45.3 MB freed)
  Outputs: 18 files removed, 5 most recent kept (23.1 MB freed)
Starting simulation...
```

### Parameters

- `--country`: Country ID (e.g., 13 for Azerbaijan)
- `--categories`: Comma-separated category IDs (e.g., 1234,5678)
- `--time-from`: Start date (YYYY-MM-DD, full day only)
- `--time-to`: End date (YYYY-MM-DD, full day only)
- `--config`: Path to config file (default: config/config.yaml)
- `--no-cache`: Disable local data caching
- `--clean`: Clean cache and old outputs before simulation (keeps last 5 runs)

### Output

Simulation generates CSV reports in `outputs/`:
- `seller_comparison_{date}.csv`: Per-seller metrics (actual vs simulated)
- `ad_comparison_{date}.csv`: Per-ad metrics (actual vs simulated)
- `summary_statistics_{date}.txt`: Overall summary

## How It Works

### 1. Data Extraction
- Pulls historical impressions from `enriched_distributed` (ClickHouse)
- Pulls campaign budgets from `spendings_distributed`
- Calculates `min_bid` per category from historical data
- Caches data locally for repeated runs

### 2. Auction Simulation
For each hour of each day:
1. Calculate **pressure** for each ad: `pressure = remaining_budget / time_left`
2. Apply **pacing gate**: pause ads spending too fast
3. **Rank ads** by pressure (DESC), assign `rank_index`
4. Calculate **effective bid**: `min_bid + (N - 1 - rank_index) * bid_step`
5. Select **top 40 winners** per batch (pagination)
6. **Charge winners**: deduct bid from remaining budget
7. Repeat for next batch (dynamic recomputation)

### 3. Organic Fallback
When all budgets exhausted but slots remain:
- **Proportional distribution** based on historical organic impressions (is_paid=false)
- **Equal distribution** if no organic history (rare edge case)
- Guarantees exact conservation: `SUM(allocated) == remaining_slots`

### 4. Comparison Reporting
- Aggregate metrics per seller and per ad
- Calculate total impressions (should be equal: actual = simulated)
- Calculate paid/organic split (may differ: more paid if more budgets available)
- Export to CSV with metadata headers

## Configuration

Edit `config/config.yaml` or `config/local.yaml`:

```yaml
simulation:
  min_time_left_threshold: 0.001  # Safety net for edge cases (currently not triggered)
  pacing_tolerance: 0.2  # 20% overspend allowed
  bid_step: 0.1  # Kopecks between ranks
  batch_size: 40  # Impressions per batch

database:
  host: "your-clickhouse-host"
  port: 9000
  database: "analytics"
  user: "your-username"
  password: "your-password"
```

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=auction_simulator tests/

# Run specific test file
pytest tests/test_auction_engine.py -v
```

## Key Concepts

### Currency Units
All monetary values use **kopecks** (1/100 currency unit):
- 100 kopecks = 1.00 AZN
- `min_bid = 0.5` means 0.005 AZN per impression
- Budget deduction rounds float bids to integer kopecks

### Two Definitions of "Organic"
1. **Historical organic** (`is_paid=false` in ClickHouse): Used for proportional fallback
2. **Simulated organic** (`budget=0` at auction time): Ads with no budget get `pressure=0`

### Total Impression Conservation
- Extract **total impressions** (paid + organic) from historical data
- Simulation redistributes exact same volume
- Paid/organic split changes based on which ads have budget when they win

## Limitations (MVP)

- **Full days only**: No partial days (time_from/time_to must be YYYY-MM-DD)
- **Hourly granularity**: Time calculated as `hour / 24.0` within day
- **Category feed only**: No search or filtered views
- **Ad-level auction**: Not user-level or seller-level
- **No Reach Profile rotation**: All ads from period always eligible
- **Schema-dependent min_bid**: Requires `spendings_distributed` to have impression counts or join with `enriched_distributed`

## Troubleshooting

### Database Connection Issues
```
Error: Connection timeout
```
**Solution:** Check `config/local.yaml` credentials and network access to ClickHouse.

### Schema Verification Required
```
Warning: min_bid calculation may need join
```
**Solution:** Check if `spendings_distributed` has `impressions_count` field. If not, implement Option B join in `data_extraction.py`.

### Conservation Violated
```
AssertionError: Conservation violated: 299 != 300
```
**Solution:** This indicates a bug in organic fallback logic. Check remainder distribution algorithm.

## Architecture

```
auction_simulator/
├── __init__.py
├── cli.py                 # Command-line interface
├── config.py              # Configuration management
├── data_extraction.py     # ClickHouse queries and caching
├── auction_engine.py      # Core auction logic (pressure, bidding, winners)
├── simulation.py          # Orchestration (multi-day loop, state management)
└── reporting.py           # Aggregation and CSV export
```

## Success Criteria

Simulation is successful if:
- ✅ Runs to completion on 1 day of data for 1 category
- ✅ Produces valid comparison tables (no crashes, no null values)
- ✅ Shows paid impressions going to ads with higher pressure (budget + urgency)
- ✅ Total impressions conserved (total_actual = total_simulated)
- ✅ Total simulated spending ≤ sum of all daily budgets (no budget overruns)
- ✅ Paid/organic split changes as expected (more ads have budget when they win)

## Next Steps

After validation:
1. Present findings to product/business team
2. Analyze fairness improvements vs current system
3. Identify winners/losers under new model
4. Decide on Phase 2: Production preparation

## Support

For questions or issues, see:
- **Proposal**: `openspec/changes/add-auction-simulator/proposal.md`
- **Design**: `openspec/changes/add-auction-simulator/design.md`
- **Specs**: `openspec/changes/add-auction-simulator/specs/`
