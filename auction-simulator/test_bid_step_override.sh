#!/bin/bash

# Quick test to verify --bid-step parameter override works
# This will run simulation and immediately check if override happened

set -e

CATEGORY=6282
COUNTRY=13
DATE_FROM="2026-01-31"
DATE_TO="2026-02-01"
CONFIG_FILE="config/local.yaml"
BID_STEP=0.01

echo "╔════════════════════════════════════════════════════════════════════════════════════╗"
echo "║              TESTING BID_STEP OVERRIDE --bid-step $BID_STEP                          ║"
echo "╚════════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Config file: $CONFIG_FILE"
echo "Expected override: --bid-step $BID_STEP"
echo ""
echo "Running simulation..."
echo ""

# Run simulation with explicit --bid-step parameter
python -m auction_simulator.cli simulate \
  --country "$COUNTRY" \
  --categories "$CATEGORY" \
  --time-from "$DATE_FROM" \
  --time-to "$DATE_TO" \
  --config "$CONFIG_FILE" \
  --bid-step "$BID_STEP" \
  --clean \
  --no-cache \
  2>&1 | tee /tmp/bid_step_test.log

echo ""
echo "════════════════════════════════════════════════════════════════════════════════════"
echo "  VERIFICATION"
echo "════════════════════════════════════════════════════════════════════════════════════"
echo ""

# Check if override happened in logs
if grep -q "BID_STEP OVERRIDE" /tmp/bid_step_test.log; then
    echo "✅ Override detected in logs:"
    grep -A 3 "BID_STEP OVERRIDE" /tmp/bid_step_test.log
    echo ""
else
    echo "❌ Override NOT detected in logs!"
    echo "   Expected to see 'BID_STEP OVERRIDE' message"
    echo ""
fi

# Check latest summary file
LATEST_SUMMARY=$(ls -t outputs/summary_statistics_*.txt | head -1)
if [ -f "$LATEST_SUMMARY" ]; then
    echo "Latest summary file: $LATEST_SUMMARY"
    echo ""

    # Check bid_step in filename
    if echo "$LATEST_SUMMARY" | grep -q "bidstep_${BID_STEP}"; then
        echo "✅ Filename contains correct bid_step: ${BID_STEP}"
    else
        echo "❌ Filename does NOT contain expected bid_step: ${BID_STEP}"
        echo "   Actual filename: $(basename $LATEST_SUMMARY)"
    fi
    echo ""

    # Check bid_step in file content
    echo "bid_step in summary file:"
    grep "bid_step:" "$LATEST_SUMMARY" || echo "  (not found)"
    echo ""
fi

echo "════════════════════════════════════════════════════════════════════════════════════"
echo ""
