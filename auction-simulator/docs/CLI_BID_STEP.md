# CLI Parameter: --bid-step

## Overview

The `--bid-step` parameter allows you to override the `bid_step` value from the configuration file directly via command line when running simulations.

This is useful for:
- Testing different bid_step values without modifying config files
- Running parameter sweeps / A/B tests
- Quick experiments

## Usage

### Basic Syntax

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 6282 \
  --time-from 2026-01-31 \
  --time-to 2026-02-01 \
  --config config/local.yaml \
  --bid-step 0.01
```

### Parameters

- **`--bid-step FLOAT`**: Override bid_step from config
  - Optional parameter
  - If not provided, uses value from config file
  - Example values: `0.003`, `0.005`, `0.0075`, `0.01`

### Examples

#### Example 1: Single test with custom bid_step

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 6282 \
  --time-from 2026-01-31 \
  --time-to 2026-02-01 \
  --config config/local.yaml \
  --bid-step 0.015 \
  --clean \
  --no-cache
```

**Output in logs:**

```
================================================================================
BID_STEP OVERRIDE
================================================================================
Original (from config): 0.003
Override (from --bid-step): 0.015
================================================================================
```

#### Example 2: Testing multiple bid_step values

Use the provided test script:

```bash
# Using the automated test script
./test_bid_step_v3.sh
```

Or manually:

```bash
# Test bid_step = 0.005
python -m auction_simulator.cli simulate \
  --country 13 --categories 6282 \
  --time-from 2026-01-31 --time-to 2026-02-01 \
  --config config/local.yaml \
  --bid-step 0.005 \
  --clean --no-cache

# Test bid_step = 0.01
python -m auction_simulator.cli simulate \
  --country 13 --categories 6282 \
  --time-from 2026-01-31 --time-to 2026-02-01 \
  --config config/local.yaml \
  --bid-step 0.01 \
  --clean --no-cache
```

#### Example 3: Using default from config

If you omit `--bid-step`, the value from config file is used:

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 6282 \
  --time-from 2026-01-31 \
  --time-to 2026-02-01 \
  --config config/local.yaml

# Uses bid_step from config/local.yaml (currently 0.003)
```

## Automated Testing Script

### test_bid_step_v3.sh

Tests multiple bid_step values automatically:

```bash
./test_bid_step_v3.sh
```

**What it does:**
1. Tests bid_step values: `0.003`, `0.005`, `0.0075`, `0.01`
2. Runs simulation for each value
3. Tags output files with bid_step value
4. Generates comparison table

**Output:**

```
┌──────────┬───────────────┬──────────────┬──────────────┐
│ bid_step │ Budget Util % │ Simul Spend  │ Output File  │
├──────────┼───────────────┼──────────────┼──────────────┤
│  0.0030  │        XX.X%  │     XXX.XX ₼ │ summary_...  │
│  0.0050  │        XX.X%  │     XXX.XX ₼ │ summary_...  │
│  0.0075  │        XX.X%  │     XXX.XX ₼ │ summary_...  │
│  0.0100  │        XX.X%  │     XXX.XX ₼ │ summary_...  │
└──────────┴───────────────┴──────────────┴──────────────┘
```

## Implementation Details

### Code Changes

**File**: `src/auction_simulator/cli.py`

1. **Added CLI option:**
   ```python
   @click.option('--bid-step', type=float, default=None,
                 help='Override bid_step from config (e.g., 0.003, 0.005, 0.01)')
   ```

2. **Override logic:**
   ```python
   # Load configuration
   cfg = load_config(config)

   # Override bid_step if provided via command line
   if bid_step is not None:
       original_bid_step = cfg.simulation.bid_step
       cfg.simulation.bid_step = bid_step
       logger.info("BID_STEP OVERRIDE")
       logger.info(f"Original (from config): {original_bid_step}")
       logger.info(f"Override (from --bid-step): {bid_step}")
   ```

### Verification

The override is logged in the simulation output:

```
2026-02-05 22:27:04 - INFO - ================================================================================
2026-02-05 22:27:04 - INFO - BID_STEP OVERRIDE
2026-02-05 22:27:04 - INFO - ================================================================================
2026-02-05 22:27:04 - INFO - Original (from config): 0.003
2026-02-05 22:27:04 - INFO - Override (from --bid-step): 0.015
2026-02-05 22:27:04 - INFO - ================================================================================
```

## Testing Results

### Category 6282 Test Results

| bid_step | Budget Util % | Simul Spend | Improvement |
|----------|---------------|-------------|-------------|
| 0.005    | 56.1%         | 112.89 ₼    | baseline    |
| 0.0075   | 62.0%         | 124.65 ₼    | +10.5%      |
| 0.01     | 69.1%         | 139.02 ₼    | +11.5%      |

**Conclusion**: Higher bid_step → Better budget utilization (with cascading_win_cap + feedback_pricing enabled)

## Tips

1. **Always use `--clean --no-cache`** when testing different parameters to ensure fresh data

2. **Tag your outputs** by copying summary files with bid_step in filename:
   ```bash
   cp outputs/summary_statistics_latest.txt \
      outputs/summary_statistics_bidstep_0.01.txt
   ```

3. **Compare results** using the comparison script or manual inspection

4. **Test systematically**: Start with a small date range (1-2 days) before full testing

## See Also

- [Configuration Guide](../config/README.md) - Default bid_step configuration
- [Simulation Guide](SIMULATION.md) - General simulation usage
- [Test Scripts](../test_bid_step_v3.sh) - Automated testing
