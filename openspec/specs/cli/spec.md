# cli Specification

## Purpose
TBD - created by archiving change add-cache-output-cleanup. Update Purpose after archive.
## Requirements
### Requirement: Cache and Output Cleanup Before Simulation

The system SHALL provide a `--clean` flag that removes cached data and old output files before starting simulation, helping users maintain a clean working environment.

#### Scenario: Clean flag removes all cache files

- **WHEN** user runs simulation with `--clean` flag
- **THEN** system deletes all files in `data/cache/` directory before data extraction
- **AND** logs cleanup action: "Cache: N files removed (X MB freed)"
- **NOTE**: Empty cache directory is preserved, only files are deleted

#### Scenario: Clean flag removes old output files, keeps recent runs

- **WHEN** user runs simulation with `--clean` flag
- **THEN** system deletes output files older than last `keep_last_runs` (default: 5) simulation runs
- **AND** keeps files from the 5 most recent runs based on timestamp in filename
- **AND** logs cleanup action: "Outputs: N files removed, M files kept (X MB freed)"
- **NOTE**: One "run" consists of 3 files: `ad_comparison_*.csv`, `seller_comparison_*.csv`, `summary_statistics_*.txt` with same timestamp

#### Scenario: Clean flag shows cleanup summary

- **WHEN** user runs simulation with `--clean` flag
- **THEN** before starting data extraction, system displays:
  ```
  Cleaning up before simulation...
    Cache: 12 files removed (45.3 MB freed)
    Outputs: 18 files removed, 5 most recent kept (23.1 MB freed)
  ```
- **AND** cleanup summary uses INFO log level (always visible)

#### Scenario: Simulation runs normally without clean flag

- **WHEN** user runs simulation without `--clean` flag
- **THEN** no cleanup is performed
- **AND** no cleanup messages are logged
- **AND** simulation proceeds directly to data extraction

#### Scenario: Clean flag works independently of no-cache flag

- **WHEN** user runs simulation with `--clean` and `--no-cache` flags
- **THEN** cleanup removes cache files first
- **AND** data extraction proceeds with caching disabled (as per `--no-cache` behavior)
- **NOTE**: `--clean` affects pre-run cleanup, `--no-cache` affects extraction behavior

### Requirement: Configurable Output Retention

The system SHALL allow configuration of how many recent simulation runs to keep when cleaning outputs.

#### Scenario: Default keeps 5 recent runs

- **WHEN** configuration does not specify `cleanup.keep_last_runs`
- **THEN** system keeps files from 5 most recent simulation runs
- **AND** deletes all older output files

#### Scenario: Custom retention count

- **WHEN** configuration specifies `cleanup.keep_last_runs: 3`
- **AND** user runs simulation with `--clean` flag
- **THEN** system keeps files from 3 most recent simulation runs only
- **AND** deletes all older output files

#### Scenario: Retention applies per-file-set

- **WHEN** outputs directory contains files from 10 simulation runs
- **AND** user runs simulation with `--clean` flag and `keep_last_runs: 5`
- **THEN** system identifies the 5 most recent timestamps
- **AND** deletes all files not matching those 5 timestamps
- **EXAMPLE**: If timestamps are `20260201_120000` through `20260201_130000`, keep 5 newest

### Requirement: Human-Readable Size Reporting

The system SHALL report freed disk space in human-readable format (KB, MB, GB).

#### Scenario: Bytes converted to appropriate units

- **WHEN** cleanup removes 1,500 bytes of cache
- **THEN** log shows "1.5 KB freed"
- **WHEN** cleanup removes 45,000,000 bytes of outputs
- **THEN** log shows "45.0 MB freed"
- **WHEN** cleanup removes 1,500,000,000 bytes
- **THEN** log shows "1.5 GB freed"

#### Scenario: Zero cleanup handled gracefully

- **WHEN** cleanup finds no files to remove in cache
- **THEN** log shows "Cache: 0 files removed (0 B freed)"
- **AND** no error is raised
- **AND** simulation continues normally

