# Change: Add Cascading Dynamic Win Cap and Pacing Relaxation

## Why
Paid spend does not increase when there are few paid ads because the auction caps one win per ad per batch and pacing gate blocks budget usage. We need a deterministic cascade that first increases wins per ad and only then relaxes pacing.

## What Changes
- Add a dynamic `win_per_ad_cap` evaluated per category per hour based on under-spend ratio.
- Add a fallback rule that relaxes pacing gate only after 2 consecutive hours of under-spend.
- Log cascade decisions and thresholds per category/hour.

## Impact
- Affected specs: `auction-engine`, `simulation-logging`
- Affected code: `auction_engine.py`, `simulation.py`, logging pipeline
