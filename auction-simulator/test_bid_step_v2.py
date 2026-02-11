#!/usr/bin/env python3
"""
Test different bid_step values and compare results.

This script:
1. Backs up original config
2. For each bid_step value:
   - Modifies config (verified)
   - Runs simulation
   - Saves results with bid_step label
   - Extracts key metrics
3. Generates comparison table
"""

import subprocess
import sys
import yaml
import shutil
from pathlib import Path
from datetime import datetime
import re

# Configuration
CATEGORY = 6282
COUNTRY = 13
DATE_FROM = "2026-01-31"
DATE_TO = "2026-02-01"
CONFIG_FILE = Path("config/local.yaml")
BACKUP_FILE = Path("config/local.yaml.backup")
BID_STEPS = [0.003, 0.005, 0.0075, 0.01]

# Results storage
results = []


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_step(text):
    """Print step description."""
    print(f"\n>>> {text}")


def load_config(config_path):
    """Load YAML config."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_config(config_path, config):
    """Save YAML config."""
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def modify_bid_step(config_path, bid_step_value):
    """Modify bid_step in config file."""
    print_step(f"Modifying config: bid_step = {bid_step_value}")

    # Load config
    config = load_config(config_path)

    # Modify bid_step
    if 'simulation' in config and 'bid_step' in config['simulation']:
        old_value = config['simulation']['bid_step']
        config['simulation']['bid_step'] = bid_step_value

        # Save
        save_config(config_path, config)

        # Verify
        config_verify = load_config(config_path)
        actual_value = config_verify['simulation']['bid_step']

        print(f"  Old value: {old_value}")
        print(f"  New value: {actual_value}")

        if abs(actual_value - bid_step_value) > 0.0001:
            print(f"  ❌ ERROR: bid_step not modified correctly!")
            sys.exit(1)
        else:
            print(f"  ✓ Verified: bid_step = {actual_value}")

        return True
    else:
        print("  ❌ ERROR: bid_step not found in config!")
        sys.exit(1)


def run_simulation():
    """Run auction simulation."""
    print_step("Running simulation...")

    cmd = [
        "python", "-m", "auction_simulator.cli", "simulate",
        "--clean",
        "--no-cache",
        "--country", str(COUNTRY),
        "--categories", str(CATEGORY),
        "--time-from", DATE_FROM,
        "--time-to", DATE_TO,
        "--config", str(CONFIG_FILE)
    ]

    print(f"  Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ❌ Simulation failed with code {result.returncode}")
        print(f"  STDERR: {result.stderr[-500:]}")  # Last 500 chars
        return None
    else:
        print(f"  ✓ Simulation completed successfully")
        return result


def find_latest_output_dir():
    """Find latest simulation output directory."""
    output_dirs = sorted(Path("outputs").glob("simulation_*"))
    if output_dirs:
        latest = output_dirs[-1]
        print(f"  Latest output: {latest}")
        return latest
    return None


def rename_output(output_dir, bid_step):
    """Rename output directory to include bid_step."""
    if not output_dir:
        return None

    new_name = f"{output_dir.name}_bidstep_{bid_step}"
    new_path = output_dir.parent / new_name

    if new_path.exists():
        shutil.rmtree(new_path)

    shutil.move(str(output_dir), str(new_path))
    print(f"  Renamed to: {new_path.name}")

    return new_path


def extract_metrics(output_dir):
    """Extract key metrics from summary file."""
    summary_files = list(output_dir.glob("summary_statistics_*.txt"))

    if not summary_files:
        print(f"  ❌ No summary file found in {output_dir}")
        return None

    summary_file = summary_files[0]
    print(f"  Reading metrics from: {summary_file.name}")

    metrics = {
        'budget_util': None,
        'simulated_spend': None,
        'actual_spend': None,
        'paid_ads': None,
        'paid_sellers': None,
        'mean_reach': None,
        'median_reach': None,
    }

    with open(summary_file, 'r') as f:
        content = f.read()

    # Extract budget utilization
    match = re.search(r'Overall Budget Utilization:\s+(\d+\.\d+)%', content)
    if match:
        metrics['budget_util'] = float(match.group(1))

    # Extract simulated spend
    match = re.search(r'Simulated Spend:\s+(\d+\.\d+)\s+AZN', content)
    if match:
        metrics['simulated_spend'] = float(match.group(1))

    # Extract actual spend
    match = re.search(r'Actual Spend:\s+(\d+\.\d+)\s+AZN', content)
    if match:
        metrics['actual_spend'] = float(match.group(1))

    # Extract paid ads count (from "With Reach" line after "Paid Ads:")
    # Look for pattern like:
    #   Paid Ads:
    #     Total:          72
    #     With Reach:     72
    match = re.search(r'Paid Ads:.*?With Reach:\s+(\d+)', content, re.DOTALL)
    if match:
        metrics['paid_ads'] = int(match.group(1))

    # Extract paid sellers
    match = re.search(r'Paid Sellers:.*?With Reach:\s+(\d+)', content, re.DOTALL)
    if match:
        metrics['paid_sellers'] = int(match.group(1))

    # Extract mean reach (Simulated)
    match = re.search(r'Paid Ads \(Simulated\):.*?Mean:\s+(\d+\.\d+)\s+reach/ad', content, re.DOTALL)
    if match:
        metrics['mean_reach'] = float(match.group(1))

    # Extract median reach (Simulated)
    match = re.search(r'Paid Ads \(Simulated\):.*?Median:\s+(\d+\.\d+)\s+reach/ad', content, re.DOTALL)
    if match:
        metrics['median_reach'] = float(match.group(1))

    print(f"  Extracted metrics: {metrics}")
    return metrics


def print_comparison_table():
    """Print comparison table of all results."""
    print_header("COMPARISON TABLE")

    if not results:
        print("No results to compare!")
        return

    print()
    print("┌──────────┬───────────────┬──────────────┬──────────────┬───────────┬──────────┬─────────────┬──────────────┐")
    print("│ bid_step │ Budget Util % │ Simul Spend  │ Actual Spend │ Paid Ads  │ Sellers  │ Mean Reach  │ Median Reach │")
    print("├──────────┼───────────────┼──────────────┼──────────────┼───────────┼──────────┼─────────────┼──────────────┤")

    for result in results:
        bid_step = result['bid_step']
        metrics = result['metrics']

        if metrics:
            print(f"│ {bid_step:>8.4f} │ {metrics['budget_util']:>11.1f}% │ "
                  f"{metrics['simulated_spend']:>10.2f} ₼ │ "
                  f"{metrics['actual_spend']:>10.2f} ₼ │ "
                  f"{metrics['paid_ads']:>9} │ "
                  f"{metrics['paid_sellers']:>8} │ "
                  f"{metrics['mean_reach']:>10.1f} │ "
                  f"{metrics['median_reach']:>11.1f} │")
        else:
            print(f"│ {bid_step:>8.4f} │ {'FAILED':>13} │ {'---':>12} │ "
                  f"{'---':>12} │ {'---':>9} │ {'---':>8} │ {'---':>11} │ {'---':>12} │")

    print("└──────────┴───────────────┴──────────────┴──────────────┴───────────┴──────────┴─────────────┴──────────────┘")

    # Analysis
    print("\n📊 Analysis:")

    valid_results = [r for r in results if r['metrics']]

    if len(valid_results) < 2:
        print("  Not enough valid results for comparison")
        return

    # Check if all metrics are identical
    first_metrics = valid_results[0]['metrics']
    all_identical = all(
        r['metrics']['budget_util'] == first_metrics['budget_util'] and
        r['metrics']['simulated_spend'] == first_metrics['simulated_spend']
        for r in valid_results[1:]
    )

    if all_identical:
        print("  ⚠️  All results are IDENTICAL")
        print("      → bid_step has NO IMPACT (likely due to cascading_win_cap + feedback_pricing)")
    else:
        print("  ✓ Results show variation across bid_step values")

        # Find best budget utilization
        best = max(valid_results, key=lambda r: r['metrics']['budget_util'])
        print(f"  🏆 Best budget utilization: bid_step={best['bid_step']:.4f} ({best['metrics']['budget_util']:.1f}%)")


def main():
    """Main execution."""
    print_header(f"BID_STEP TESTING - Category {CATEGORY}")
    print(f"Date range: {DATE_FROM} to {DATE_TO}")
    print(f"Testing values: {BID_STEPS}")
    print(f"Config file: {CONFIG_FILE}")

    # Backup original config
    print_step("Backing up original config")
    shutil.copy(CONFIG_FILE, BACKUP_FILE)
    print(f"  ✓ Backup created: {BACKUP_FILE}")

    try:
        # Test each bid_step value
        for bid_step in BID_STEPS:
            print_header(f"Testing bid_step = {bid_step}")

            # Modify config
            modify_bid_step(CONFIG_FILE, bid_step)

            # Run simulation
            sim_result = run_simulation()

            if sim_result is None:
                print(f"  ⚠️  Simulation failed for bid_step={bid_step}")
                results.append({
                    'bid_step': bid_step,
                    'output_dir': None,
                    'metrics': None
                })
                continue

            # Find and rename output
            output_dir = find_latest_output_dir()
            if output_dir:
                renamed_dir = rename_output(output_dir, bid_step)

                # Extract metrics
                metrics = extract_metrics(renamed_dir)

                results.append({
                    'bid_step': bid_step,
                    'output_dir': renamed_dir,
                    'metrics': metrics
                })
            else:
                print(f"  ⚠️  Could not find output directory")
                results.append({
                    'bid_step': bid_step,
                    'output_dir': None,
                    'metrics': None
                })

        # Print comparison
        print_comparison_table()

        print_header("OUTPUT DIRECTORIES")
        for result in results:
            if result['output_dir']:
                print(f"  bid_step={result['bid_step']:>6.4f} → {result['output_dir']}")

    finally:
        # Restore original config
        print_step("Restoring original config")
        shutil.copy(BACKUP_FILE, CONFIG_FILE)
        print(f"  ✓ Config restored")

        print_header("TESTING COMPLETE")
        print(f"Results summary: {len([r for r in results if r['metrics']])} / {len(BID_STEPS)} successful")


if __name__ == "__main__":
    main()
