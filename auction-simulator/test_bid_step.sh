#!/bin/bash

# Test different bid_step values for category 6282
# Values to test: 0.003 (base), 0.005, 0.0075, 0.01

set -e

CATEGORY=6282
COUNTRY=13
DATE_FROM="2026-01-31"
DATE_TO="2026-02-01"
CONFIG_FILE="config/local.yaml"
BACKUP_FILE="config/local.yaml.backup"

# Backup original config
cp "$CONFIG_FILE" "$BACKUP_FILE"

echo "=========================================="
echo "Testing bid_step values for category $CATEGORY"
echo "Country: $COUNTRY"
echo "Period: $DATE_FROM to $DATE_TO"
echo "=========================================="
echo ""

# Array of bid_step values to test
BID_STEPS=(0.003 0.005 0.0075 0.01)

for BID_STEP in "${BID_STEPS[@]}"; do
    echo "=========================================="
    echo "Running simulation with bid_step=$BID_STEP"
    echo "=========================================="

    # Update bid_step in config using sed
    # Match the line with "bid_step:" and replace the value
    sed -i.tmp "s/bid_step: [0-9.]*  # Optimal value for simulation/bid_step: $BID_STEP  # Testing bid_step variation/" "$CONFIG_FILE"
    rm -f "${CONFIG_FILE}.tmp"

    # Run simulation
    python -m auction_simulator.cli simulate \
      --clean \
      --no-cache \
      --country "$COUNTRY" \
      --categories "$CATEGORY" \
      --time-from "$DATE_FROM" \
      --time-to "$DATE_TO" \
      --config "$CONFIG_FILE"

    # Find the latest output directory
    LATEST_OUTPUT=$(ls -td outputs/simulation_* | head -1)

    # Rename output directory to include bid_step
    RENAMED_OUTPUT="${LATEST_OUTPUT}_bidstep_${BID_STEP}"
    mv "$LATEST_OUTPUT" "$RENAMED_OUTPUT"

    echo "Results saved to: $RENAMED_OUTPUT"
    echo ""

    # Extract key metrics from summary
    SUMMARY_FILE=$(ls -t "${RENAMED_OUTPUT}"/summary_statistics_*.txt | head -1)
    if [ -f "$SUMMARY_FILE" ]; then
        echo "=== Key metrics for bid_step=$BID_STEP ==="
        echo ""
        grep -A 2 "Budget Utilization:" "$SUMMARY_FILE" || true
        echo ""
        grep -A 5 "Reach Accuracy:" "$SUMMARY_FILE" || true
        echo ""
        grep -A 3 "Paid/Organic Split:" "$SUMMARY_FILE" || true
        echo ""
    fi
done

# Restore original config
mv "$BACKUP_FILE" "$CONFIG_FILE"

echo "=========================================="
echo "All simulations complete!"
echo "=========================================="
echo ""
echo "Results summary:"
echo ""

# Create comparison table
echo "| bid_step | Budget Util | Reach Accuracy | Output Directory |"
echo "|----------|-------------|----------------|------------------|"

for BID_STEP in "${BID_STEPS[@]}"; do
    OUTPUT_DIR=$(ls -td outputs/simulation_*_bidstep_${BID_STEP} 2>/dev/null | head -1)
    if [ -d "$OUTPUT_DIR" ]; then
        SUMMARY_FILE=$(ls -t "${OUTPUT_DIR}"/summary_statistics_*.txt | head -1)

        # Extract budget utilization
        BUDGET_UTIL=$(grep "Budget Utilization:" "$SUMMARY_FILE" -A 1 | grep "%" | head -1 | awk '{print $1}' || echo "N/A")

        # Extract reach accuracy
        REACH_ACC=$(grep "Accuracy:" "$SUMMARY_FILE" | head -1 | awk '{print $2}' || echo "N/A")

        echo "| $BID_STEP | $BUDGET_UTIL | $REACH_ACC | ${OUTPUT_DIR##*/} |"
    fi
done

echo ""
echo "Detailed results in:"
for BID_STEP in "${BID_STEPS[@]}"; do
    OUTPUT_DIR=$(ls -td outputs/simulation_*_bidstep_${BID_STEP} 2>/dev/null | head -1)
    if [ -d "$OUTPUT_DIR" ]; then
        echo "  bid_step=$BID_STEP: $OUTPUT_DIR"
    fi
done
