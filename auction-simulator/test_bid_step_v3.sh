#!/bin/bash

# Test different bid_step values using CLI parameter
# Usage: ./test_bid_step_v3.sh

set -e

CATEGORY=6282
COUNTRY=13
DATE_FROM="2026-01-31"
DATE_TO="2026-02-01"
CONFIG_FILE="config/local.yaml"

echo "╔════════════════════════════════════════════════════════════════════════════════════╗"
echo "║              BID_STEP TESTING - Category $CATEGORY (CLI parameter)                   ║"
echo "╚════════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Period: $DATE_FROM to $DATE_TO"
echo "Config: $CONFIG_FILE (bid_step will be overridden)"
echo ""

# Array of bid_step values to test
BID_STEPS=(0.003 0.005 0.0075 0.01)

for BID_STEP in "${BID_STEPS[@]}"; do
    echo "════════════════════════════════════════════════════════════════════════════════════"
    echo "  Testing bid_step = $BID_STEP"
    echo "════════════════════════════════════════════════════════════════════════════════════"
    echo ""

    # Run simulation with --bid-step parameter
    python -m auction_simulator.cli simulate \
      --country "$COUNTRY" \
      --categories "$CATEGORY" \
      --time-from "$DATE_FROM" \
      --time-to "$DATE_TO" \
      --config "$CONFIG_FILE" \
      --bid-step "$BID_STEP" \
      --clean \
      --no-cache

    echo ""
    echo "✓ Simulation completed for bid_step=$BID_STEP"
    echo ""

    # Find and tag the latest summary file
    LATEST_SUMMARY=$(ls -t outputs/summary_statistics_*.txt | head -1)
    if [ -f "$LATEST_SUMMARY" ]; then
        # Copy and rename to preserve results
        TAGGED_FILE="${LATEST_SUMMARY%.txt}_bidstep_${BID_STEP}.txt"
        cp "$LATEST_SUMMARY" "$TAGGED_FILE"
        echo "→ Results saved: $TAGGED_FILE"

        # Extract quick metrics
        echo ""
        echo "  Quick metrics:"
        grep "Overall Budget Utilization:" "$LATEST_SUMMARY" || true
        grep "Simulated Spend:" "$LATEST_SUMMARY" || true
        echo ""
    fi

    sleep 2
done

echo "════════════════════════════════════════════════════════════════════════════════════"
echo "  ALL TESTS COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Generating comparison table..."
echo ""

# Generate comparison table
echo "┌──────────┬───────────────┬──────────────┬──────────────┐"
echo "│ bid_step │ Budget Util % │ Simul Spend  │ Output File  │"
echo "├──────────┼───────────────┼──────────────┼──────────────┤"

for BID_STEP in "${BID_STEPS[@]}"; do
    TAGGED_FILES=(outputs/summary_statistics_*_bidstep_${BID_STEP}.txt)

    if [ -f "${TAGGED_FILES[0]}" ]; then
        FILE="${TAGGED_FILES[0]}"

        # Extract metrics
        BUDGET_UTIL=$(grep "Overall Budget Utilization:" "$FILE" | grep -oE "[0-9]+\.[0-9]+" | head -1)
        SIMUL_SPEND=$(grep "Simulated Spend:" "$FILE" | awk '{print $3}')
        FILENAME=$(basename "$FILE")

        printf "│ %8s │ %11s%% │ %10s ₼ │ %-12s │\n" \
            "$BID_STEP" "$BUDGET_UTIL" "$SIMUL_SPEND" "${FILENAME:0:12}..."
    else
        printf "│ %8s │ %13s │ %12s │ %-12s │\n" \
            "$BID_STEP" "FAILED" "---" "---"
    fi
done

echo "└──────────┴───────────────┴──────────────┴──────────────┘"
echo ""
echo "📁 Detailed results:"
echo ""

for BID_STEP in "${BID_STEPS[@]}"; do
    TAGGED_FILES=(outputs/summary_statistics_*_bidstep_${BID_STEP}.txt)
    if [ -f "${TAGGED_FILES[0]}" ]; then
        echo "  bid_step=$BID_STEP → ${TAGGED_FILES[0]}"
    fi
done

echo ""
echo "✅ Testing complete!"
