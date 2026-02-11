# Quick Start Guide

This guide will help you get the auction simulator up and running quickly.

## Prerequisites

- Python 3.8 or higher
- Access to ClickHouse database with `enriched_distributed` and `spendings_distributed` tables
- Network access to ClickHouse server

## Installation

### 1. Create Virtual Environment

```bash
cd auction-simulator
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Package

```bash
# Install in development mode with all dependencies
pip install -e .

# Or install just the requirements
pip install -r requirements.txt
```

### 3. Configure Database Connection

```bash
# Copy template
cp config/local.yaml.template config/local.yaml

# Edit config/local.yaml with your credentials
# IMPORTANT: Replace the placeholder values!
#   - host: your ClickHouse server hostname
#   - database: your database name
#   - user: your username
#   - password: your password
```

## Running Your First Simulation

### Example: Azerbaijan, Category Feed, 3 Days

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234,5678 \
  --time-from 2024-01-15 \
  --time-to 2024-01-17 \
  --config config/local.yaml \
  --verbose
```

### Parameters Explained

- `--country 13`: Country ID (13 = Azerbaijan, adjust for your market)
- `--categories 1234,5678`: Comma-separated category IDs to simulate
- `--time-from 2024-01-15`: Start date (full day only, YYYY-MM-DD format)
- `--time-to 2024-01-17`: End date (full day only, YYYY-MM-DD format)
- `--config config/local.yaml`: Path to your local config file
- `--verbose`: Enable detailed logging (optional)
- `--no-cache`: Disable caching to force fresh data extraction (optional)
- `--clean`: Clean cache and old outputs before simulation (optional, keeps last 5 runs)

### What Happens During Simulation

The simulator will:

1. **Extract Data** (~1-5 minutes depending on data size)
   - Pull historical impressions from `enriched_distributed`
   - Pull campaign budgets from `spendings_distributed`
   - Calculate `min_bid` per category
   - Cache data locally in `data/cache/`

2. **Run Simulation** (~30 seconds - 2 minutes)
   - Initialize ads with budgets
   - Simulate each hour with pressure-based auction
   - Apply pacing gate to prevent budget dumping
   - Use organic fallback when budgets exhausted

3. **Generate Reports** (~5-10 seconds)
   - Create seller-level comparison CSV
   - Create ad-level comparison CSV
   - Generate summary statistics TXT

4. **Output Files** (saved to `outputs/`)
   - `seller_comparison_YYYYMMDD_HHMMSS.csv`
   - `ad_comparison_YYYYMMDD_HHMMSS.csv`
   - `summary_statistics_YYYYMMDD_HHMMSS.txt`

## Analyzing Results

### 1. Check Summary Statistics

```bash
cat outputs/summary_statistics_*.txt
```

Look for:
- Total impression conservation (actual ≈ simulated)
- Changes in paid/organic split
- Budget utilization rates

### 2. Review Seller Comparison

```bash
# Open in Excel, Numbers, or any CSV viewer
open outputs/seller_comparison_*.csv
```

Key columns:
- `actual_impressions_total` vs `simulated_impressions_total`
- `actual_spending_azn` vs `simulated_spending_azn`
- `diff_impressions_total`, `diff_spending_azn`

### 3. Review Ad Comparison

```bash
open outputs/ad_comparison_*.csv
```

Identify:
- Which ads gained impressions under auction model
- Which ads lost impressions
- Correlation between budget urgency and impressions

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=auction_simulator tests/

# Run specific test file
pytest tests/test_auction_engine.py -v

# Run only unit tests (fast)
pytest -m unit tests/
```

## Troubleshooting

### Connection Timeout

```
Error: Connection timeout
```

**Solution:** Check `config/local.yaml` credentials and network access to ClickHouse.

### No Data Returned

```
Warning: No impressions for 2024-01-15, skipping
```

**Solution:** Verify date range has data in ClickHouse. Check filters (country, categories, feed_id='6500').

### Cache Issues

```
Error: Failed to load cache
```

**Solution:** Use `--no-cache` flag to disable caching and extract fresh data.

### Schema Mismatch

```
Warning: min_bid calculation may need join
```

**Solution:** This is expected if `spendings_distributed` schema differs. The simulator handles this automatically with a JOIN.

## Next Steps

After running your first simulation:

1. **Validate Conservation**: Check that total impressions match (actual = simulated)
2. **Analyze Fairness**: Compare small sellers vs large sellers under auction model
3. **Test Multiple Scenarios**: Try different date ranges and categories
4. **Present Findings**: Use CSV reports to demonstrate to stakeholders

## Getting Help

- Check [README.md](README.md) for detailed documentation
- Review OpenSpec proposal: `../openspec/changes/add-auction-simulator/proposal.md`
- Review design doc: `../openspec/changes/add-auction-simulator/design.md`
- Check specs: `../openspec/changes/add-auction-simulator/specs/`

## Common Use Cases

### Single Day, Single Category (Fastest)

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234 \
  --time-from 2024-01-15 \
  --time-to 2024-01-15 \
  --config config/local.yaml
```

### Multi-Category Analysis

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1,2,3,4,5,6,7,8,9,10 \
  --time-from 2024-01-15 \
  --time-to 2024-01-17 \
  --config config/local.yaml
```

### Weekly Simulation

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234,5678 \
  --time-from 2024-01-15 \
  --time-to 2024-01-21 \
  --config config/local.yaml
```

### Fresh Run with Cleanup

For a clean slate (removes old cache and keeps only 5 most recent outputs):

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234 \
  --time-from 2024-01-15 \
  --time-to 2024-01-15 \
  --clean \
  --config config/local.yaml
```

Output shows what was cleaned:
```
Cleaning up before simulation...
  Cache: 12 files removed (45.3 MB freed)
  Outputs: 18 files removed, 5 most recent kept (23.1 MB freed)
Starting simulation...
```

## Performance Tips

- **Use cache**: Don't use `--no-cache` unless necessary (saves 1-5 minutes per run)
- **Start small**: Test with 1 day + 1 category first to validate setup
- **Increase batch_size**: Edit `config/local.yaml` to increase `batch_size` from 40 to 100 for faster simulation (less accurate to real pagination)
- **Reduce logging**: Set `logging.level: WARNING` in config for cleaner output
