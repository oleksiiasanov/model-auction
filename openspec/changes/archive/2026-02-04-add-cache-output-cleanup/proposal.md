# Change: Add Cache and Output Cleanup Flag

## Why

Users accumulate old cache files and simulation outputs over time, consuming disk space and making it hard to find recent results. Currently, users must manually delete `data/cache/` and `outputs/` directories between runs.

**Problems with current state:**
- Cache files from previous simulations with different parameters can cause confusion
- Outputs directory fills with dozens of timestamped CSV/TXT files
- No built-in way to clean up before a fresh run
- `--no-cache` flag only disables cache usage, doesn't clean old files

**User needs:**
- Start simulations with clean slate (no stale cache)
- Keep outputs directory organized (recent runs only)
- See what was cleaned (transparency)
- Simple one-flag solution

## What Changes

Add `--clean` flag to CLI that removes cache and old output files before simulation runs.

**New behavior:**
- `--clean` flag removes:
  - All files in `data/cache/`
  - Old files in `outputs/` (keeps last 5 runs)
- Shows cleanup summary: files removed, space freed
- Logs cleanup actions at INFO level
- Works independently of `--no-cache` flag

**Files affected:**
- `cli.py`: Add `--clean` option, call cleanup before extraction
- New module `cleanup.py`: Implement cleanup logic with file counting and size calculation
- `config.yaml`: Add `cleanup.keep_last_runs: 5` parameter

**New capability:**
- Create `cli` spec for command-line interface requirements (currently missing)

## Impact

**Benefits:**
- Users can ensure fresh data with single flag
- Reduces disk space usage from accumulated files
- Easier to find recent simulation results
- Transparent about what was removed

**Risks:**
- Users might accidentally delete important outputs (mitigation: keep last 5 runs)
- Breaking change: None (new optional flag)

**Affected specs:**
- New capability: `cli` (command-line interface)
- Related: `data-extraction` (uses cache), `reporting-enhancements` (creates outputs)

**Usage example:**
```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1361 \
  --time-from 2026-02-01 \
  --time-to 2026-02-01 \
  --clean
```

Output:
```
Cleaning up before simulation...
  Cache: 12 files removed (45.3 MB freed)
  Outputs: 18 files removed, 5 most recent kept (23.1 MB freed)
Starting simulation...
```
