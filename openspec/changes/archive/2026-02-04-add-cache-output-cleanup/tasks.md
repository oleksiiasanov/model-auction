# Implementation Tasks

## 1. Create Cleanup Module
- [x] 1.1 Create `src/auction_simulator/cleanup.py` module
- [x] 1.2 Implement `clean_cache(cache_dir: Path) -> dict` function
  - Count files before deletion
  - Calculate total size
  - Delete all files in cache directory
  - Return stats: `{"files_removed": int, "bytes_freed": int}`
- [x] 1.3 Implement `clean_outputs(output_dir: Path, keep_last: int = 5) -> dict` function
  - List all output files sorted by timestamp (from filename)
  - Keep last N runs (each run = 3 files: ad_comparison, seller_comparison, summary)
  - Delete older files
  - Return stats: `{"files_removed": int, "files_kept": int, "bytes_freed": int}`
- [x] 1.4 Implement `format_size(bytes: int) -> str` helper
  - Convert bytes to human-readable format (KB, MB, GB)

## 2. Add CLI Flag
- [x] 2.1 Add `--clean` flag to `cli.py` simulate command
  - `@click.option('--clean', is_flag=True, help='Clean cache and old outputs before simulation')`
- [x] 2.2 Import cleanup module in `cli.py`
- [x] 2.3 Call cleanup functions before Phase 1 (data extraction)
  - Only if `--clean` flag is set
  - Log cleanup actions at INFO level
  - Show summary: files removed, space freed

## 3. Add Configuration
- [x] 3.1 Add `cleanup` section to `config/config.yaml`:
  ```yaml
  cleanup:
    keep_last_runs: 5  # Number of recent output runs to keep
  ```
- [x] 3.2 Add same config to `config/local.yaml`
- [x] 3.3 Update `Config` class in `config.py` to include cleanup settings

## 4. Testing
- [x] 4.1 Write unit tests in `tests/test_cleanup.py`
  - Test `clean_cache()` with mock files
  - Test `clean_outputs()` with various file patterns
  - Test `clean_outputs()` keeps correct number of runs
  - Test `format_size()` with various byte values
- [x] 4.2 Write integration test: simulate with `--clean` flag
  - Create dummy cache files
  - Create dummy output files (10+ runs)
  - Run simulation with `--clean`
  - Verify only last 5 runs remain
  - Verify cache is empty
- [x] 4.3 Manual test: Run on real data
  ```bash
  # Create some cache
  python -m auction_simulator.cli simulate --country 13 --categories 1361 --time-from 2026-02-01 --time-to 2026-02-01

  # Run with --clean
  python -m auction_simulator.cli simulate --country 13 --categories 1361 --time-from 2026-02-01 --time-to 2026-02-01 --clean

  # Verify cleanup logs appear
  # Verify old files removed
  ```

## 5. Documentation
- [x] 5.1 Update `README.md`:
  - Add `--clean` flag to parameters table
  - Add example usage with cleanup
- [x] 5.2 Update `QUICKSTART.md`:
  - Mention `--clean` flag for fresh runs
  - Show cleanup output example
- [x] 5.3 Add FAQ entry in `docs/faq/05-configuration.md`:
  - "How do I clean old simulation data?"
  - Explain `--clean` flag behavior
  - Explain `keep_last_runs` configuration

## Dependencies
- No blocking dependencies
- Can implement and test in isolation
- All tasks can be done sequentially in order

## Validation
- [x] All unit tests pass (`pytest tests/test_cleanup.py -v`)
- [x] Integration test passes
- [x] Manual test shows cleanup working correctly
- [x] Spec validates: `openspec validate add-cache-output-cleanup --strict --no-interactive`
