# Design: ClickHouse HTTP Protocol Support

## Overview

Add dual protocol support to auction simulator's data extraction layer, enabling connections to both native (port 9000) and HTTP (port 8123) ClickHouse endpoints without user configuration.

## Architecture

### Current Architecture

```
DataExtractor
  └─ connect() → clickhouse-driver.Client (native only)
  └─ _extract_impressions() → self.client.execute(query)
  └─ _extract_budgets() → self.client.execute(query)
  └─ _calculate_min_bids() → self.client.execute(query)
```

**Limitation:** Only works with native protocol (port 9000)

### New Architecture

```
DataExtractor
  └─ connect() → Auto-detect protocol based on port
      ├─ Port 8123/8443 → clickhouse-connect.get_client() [HTTP]
      └─ Port 9000 → clickhouse-driver.Client() [Native]
  └─ _execute_query(query) → Protocol-agnostic execution
      ├─ HTTP: self.client.query(query).result_rows
      └─ Native: self.client.execute(query)
  └─ _extract_impressions() → self._execute_query(query)
  └─ _extract_budgets() → self._execute_query(query)
  └─ _calculate_min_bids() → self._execute_query(query)
```

**Benefit:** Works with both protocols automatically

## Implementation Details

### 1. Protocol Auto-Detection

```python
def connect(self):
    port = self.config.database.port

    if port in [8123, 8443]:
        self.protocol = 'http'
        import clickhouse_connect
        self.client = clickhouse_connect.get_client(...)
    else:
        self.protocol = 'native'
        from clickhouse_driver import Client
        self.client = Client(...)
```

**Logic:**
- Port `8123` (HTTP) or `8443` (HTTPS) → Use `clickhouse-connect`
- Any other port (typically `9000`) → Use `clickhouse-driver`
- No explicit configuration needed

### 2. Unified Query Execution

```python
def _execute_query(self, query: str) -> List[Tuple]:
    if self.protocol == 'http':
        result = self.client.query(query)
        return result.result_rows  # List[Tuple]
    else:
        return self.client.execute(query)  # List[Tuple]
```

**Abstraction:**
- Both protocols return `List[Tuple]`
- Downstream code unchanged
- All SQL queries work identically

### 3. Connection Lifecycle

```python
def disconnect(self):
    if self.client:
        if self.protocol == 'http':
            self.client.close()  # HTTP method
        else:
            self.client.disconnect()  # Native method
```

**Cleanup:**
- Protocol-specific disconnect
- Prevents resource leaks

## Configuration Schema

### config/local.yaml (Production)

```yaml
database:
  type: clickhouse
  host: "ch-prod.yallasvc.net"
  port: 8123  # → Auto-detected as HTTP
  database: "analytics"
  user: "app_tableau_20230509"
  password: "vmkdWSxgi8k%NrW"
  secure: false  # false for HTTP (8123), true for HTTPS (8443)
  connect_timeout: 30
  send_receive_timeout: 300
```

### config/config.yaml (Default Template)

```yaml
database:
  host: "localhost"
  port: 9000  # → Auto-detected as Native
  database: "analytics"
  user: "default"
  password: ""
  connect_timeout: 30
  send_receive_timeout: 300
```

**Note:** `secure` parameter only used for HTTP protocol

## Dependencies

### requirements.txt

```txt
clickhouse-driver>=0.2.6  # Native protocol (port 9000)
clickhouse-connect>=0.7.0  # HTTP protocol (port 8123)
```

**Installation:**
```bash
pip install clickhouse-driver clickhouse-connect
```

**Size:**
- `clickhouse-driver`: ~500KB (C extension)
- `clickhouse-connect`: ~1MB (pure Python)

**Trade-off:** Both libraries installed, but only one used per connection

## Testing Strategy

### 1. Connection Test Script

`test_connection.py`:
- Load config
- Attempt connection
- Verify protocol detection
- Test simple query (`SELECT 1`)
- Check table existence
- Query row counts

**Usage:**
```bash
python test_connection.py --config config/local.yaml
```

### 2. Manual Validation

Test both protocols:

**HTTP (port 8123):**
```bash
# config/local.yaml with port: 8123
python test_connection.py
```

**Native (port 9000):**
```bash
# config/test.yaml with port: 9000
python test_connection.py --config config/test.yaml
```

### 3. Integration Test

Run full simulation against production:
```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1234 \
  --time-from 2024-01-15 \
  --time-to 2024-01-15 \
  --config config/local.yaml
```

**Success criteria:**
- Data extracted successfully
- No protocol errors
- Results generated

## Error Handling

### Missing Library

```python
try:
    import clickhouse_connect
except ImportError:
    raise ImportError(
        "clickhouse-connect is required for HTTP protocol. "
        "Install it with: pip install clickhouse-connect"
    )
```

**User-friendly error message with fix**

### Connection Failure

Existing error handling unchanged:
- Timeout → `connect_timeout` setting
- Authentication → Clear error from library
- Network → Standard connection error

### Protocol Mismatch

If user tries native protocol on HTTP port (or vice versa):
- Library will fail with clear error
- User should check port number in config

## Security Considerations

### 1. Credential Storage

**gitignored:**
- `config/local.yaml` (contains password)
- Never committed to repository

**Template:**
- `config/local.yaml.template` (no credentials)
- Committed to repository

### 2. Read-Only Access

Production user: `app_tableau_20230509`
- Read-only permissions
- Cannot modify data
- Cannot drop tables
- Safe for simulation

### 3. Password in Config

**Current:** Plain text in YAML (gitignored)

**Future enhancement (optional):**
- Environment variables: `CH_PASSWORD`
- Secrets manager integration
- Encrypted config files

**For MVP:** Gitignored YAML sufficient (read-only user)

## Backward Compatibility

**100% backward compatible:**
- Existing code using native protocol (port 9000) unchanged
- No breaking changes to API
- Default config still uses port 9000

**Migration path:**
- Update port in config
- No code changes needed

## Performance Considerations

### Protocol Performance

**Native (port 9000):**
- Binary protocol
- Faster for large datasets
- Lower latency

**HTTP (port 8123):**
- Text-based protocol
- Slightly slower
- More firewall-friendly

**Impact:** Negligible for simulation (queries run once, cached)

### Library Overhead

Both libraries installed:
- ~1.5MB total
- Minimal memory overhead
- Only one used per session

**Trade-off acceptable** for flexibility

## Future Enhancements

**Not in current scope, but possible:**

1. **HTTPS Support (port 8443)**
   - Already supported (auto-detected)
   - Requires `secure: true` in config

2. **Connection Pooling**
   - `clickhouse-connect` supports pooling
   - Could reduce connection overhead
   - Not needed for batch simulation

3. **Async Queries**
   - Both libraries support async
   - Could parallelize data extraction
   - Optimization for large date ranges

4. **Query Result Streaming**
   - For very large result sets
   - Reduce memory usage
   - Not needed for current data volumes

## Alternatives Considered

### Alternative 1: HTTP Only

**Pros:** Single dependency
**Cons:** Breaks existing native protocol users

**Rejected:** Backward compatibility important

### Alternative 2: Manual Protocol Selection

```yaml
database:
  protocol: "http"  # or "native"
  port: 8123
```

**Pros:** Explicit configuration
**Cons:** Extra config, error-prone

**Rejected:** Auto-detection simpler

### Alternative 3: Separate Classes

```python
class HTTPDataExtractor(DataExtractor):
    ...

class NativeDataExtractor(DataExtractor):
    ...
```

**Pros:** Cleaner separation
**Cons:** More code duplication, factory pattern needed

**Rejected:** Single class with protocol detection cleaner

## Chosen Approach: Auto-Detection

**Why:**
- Zero configuration overhead
- Backward compatible
- Simple implementation
- Port number clearly indicates protocol

**Risk:** None (port numbers well-defined)
