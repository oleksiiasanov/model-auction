# Change: Add ClickHouse HTTP Protocol Support

## Why

The auction simulator was initially implemented with `clickhouse-driver` which only supports **native protocol (port 9000)**. However, production ClickHouse is accessible via **HTTP protocol (port 8123)**.

**Current Problem:**
- Simulator code hardcoded to use `clickhouse-driver` (native protocol)
- Production ClickHouse: `ch-prod.yallasvc.net:8123` (HTTP)
- Cannot connect to production without protocol support

**Impact:**
- Simulator cannot run against real production data
- Cannot validate auction model with actual historical data
- Blocks production readiness assessment

## What Changes

Add **dual protocol support** to data extraction module:

**Auto-detection based on port:**
- Port `8123` or `8443` → HTTP protocol (uses `clickhouse-connect`)
- Port `9000` → Native protocol (uses `clickhouse-driver`)
- No user configuration needed (automatic)

**Implementation:**
- Add `clickhouse-connect` dependency for HTTP support
- Refactor `DataExtractor.connect()` to detect protocol
- Add `_execute_query()` method for protocol-agnostic queries
- Update all SQL execution calls to use unified interface

**Scope:**
- Minimal changes to existing code
- Backward compatible (native protocol still works)
- No changes to query logic or business logic
- Production credentials configured in `config/local.yaml` (gitignored)

## Impact

- **Affected files**:
  - `requirements.txt` (add clickhouse-connect)
  - `src/auction_simulator/data_extraction.py` (protocol detection)
  - `config/local.yaml` (production credentials, not committed)

- **Affected systems**: None (internal change only)

- **Data requirements**: None (same ClickHouse tables)

- **Business value**: Enables production validation of auction model

- **Risk**: Low (backward compatible, additive change)

- **Testing**:
  - Added `test_connection.py` script
  - Tests both protocol detection and table access
  - Manual validation against production ClickHouse

## Production Credentials

**Host**: `ch-prod.yallasvc.net`
**Port**: `8123` (HTTP)
**Database**: `analytics`
**User**: `app_tableau_20230509` (read-only)
**Password**: (stored in gitignored `config/local.yaml`)

**Security:**
- Credentials only in `config/local.yaml` (gitignored)
- Read-only user account
- No write access to production
