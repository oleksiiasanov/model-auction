# database-connection Specification

## Purpose
TBD - created by archiving change add-clickhouse-http-support. Update Purpose after archive.
## Requirements
### Requirement: Automatic Protocol Detection Based on Port

The system SHALL automatically detect the ClickHouse protocol based on the configured port number without requiring explicit protocol configuration.

#### Scenario: HTTP protocol detection for port 8123

- **WHEN** config specifies `port: 8123`
- **THEN** system uses HTTP protocol via `clickhouse-connect` library
- **AND** logs "Connecting to ClickHouse via HTTP"

#### Scenario: HTTPS protocol detection for port 8443

- **WHEN** config specifies `port: 8443`
- **THEN** system uses HTTP protocol with SSL via `clickhouse-connect` library
- **AND** `secure: true` is used for connection

#### Scenario: Native protocol detection for port 9000

- **WHEN** config specifies `port: 9000`
- **THEN** system uses native protocol via `clickhouse-driver` library
- **AND** logs "Connecting to ClickHouse via native protocol"

#### Scenario: Native protocol detection for other ports

- **WHEN** config specifies port that is not 8123 or 8443 (e.g., `port: 9440`)
- **THEN** system uses native protocol via `clickhouse-driver` library

### Requirement: Protocol-Agnostic Query Execution

The system SHALL provide unified query execution interface that works identically regardless of underlying protocol.

#### Scenario: Execute query via HTTP protocol

- **WHEN** connected via HTTP protocol (port 8123)
- **AND** `_execute_query("SELECT 1")` is called
- **THEN** query is executed via `client.query(query)`
- **AND** result rows are extracted via `result.result_rows`
- **AND** returns `List[Tuple]` format: `[(1,)]`

#### Scenario: Execute query via native protocol

- **WHEN** connected via native protocol (port 9000)
- **AND** `_execute_query("SELECT 1")` is called
- **THEN** query is executed via `client.execute(query)`
- **AND** returns `List[Tuple]` format: `[(1,)]`

#### Scenario: Query result format consistency

- **WHEN** same query executed on both protocols
- **THEN** both return identical `List[Tuple]` format
- **AND** downstream code works without modification

### Requirement: Protocol-Specific Connection Handling

The system SHALL handle connection and disconnection using protocol-appropriate methods.

#### Scenario: Connect via HTTP protocol

- **WHEN** port is 8123
- **THEN** `clickhouse_connect.get_client()` is called with parameters:
  - `host`: from config
  - `port`: from config
  - `database`: from config
  - `username`: from config.database.user
  - `password`: from config.database.password
  - `secure`: from config.database.secure (default: False)
  - `connect_timeout`: from config
  - `send_receive_timeout`: from config

#### Scenario: Connect via native protocol

- **WHEN** port is 9000
- **THEN** `clickhouse_driver.Client()` is called with parameters:
  - `host`: from config
  - `port`: from config
  - `database`: from config
  - `user`: from config.database.user
  - `password`: from config.database.password
  - `connect_timeout`: from config
  - `send_receive_timeout`: from config

#### Scenario: Disconnect from HTTP connection

- **WHEN** connected via HTTP protocol
- **AND** `disconnect()` is called
- **THEN** `client.close()` is called (HTTP method)
- **AND** client is set to None

#### Scenario: Disconnect from native connection

- **WHEN** connected via native protocol
- **AND** `disconnect()` is called
- **THEN** `client.disconnect()` is called (native method)
- **AND** client is set to None

### Requirement: Missing Library Error Handling

The system SHALL provide clear error messages when required protocol library is not installed.

#### Scenario: Missing clickhouse-connect for HTTP protocol

- **WHEN** config specifies port 8123 (HTTP)
- **AND** `clickhouse-connect` library is not installed
- **THEN** ImportError is raised with message:
  - "clickhouse-connect is required for HTTP protocol."
  - "Install it with: pip install clickhouse-connect"

#### Scenario: Missing clickhouse-driver for native protocol

- **WHEN** config specifies port 9000 (native)
- **AND** `clickhouse-driver` library is not installed
- **THEN** ImportError is raised with message:
  - "clickhouse-driver is required for native protocol."
  - "Install it with: pip install clickhouse-driver"

### Requirement: Production Credentials Configuration

The system SHALL support production ClickHouse credentials in gitignored local configuration file.

#### Scenario: Load production credentials from local.yaml

- **WHEN** `config/local.yaml` exists with production credentials
- **THEN** credentials are loaded:
  - `host: "ch-prod.yallasvc.net"`
  - `port: 8123`
  - `database: "analytics"`
  - `user: "app_tableau_20230509"`
  - `password: "vmkdWSxgi8k%NrW"`
  - `secure: false`

#### Scenario: local.yaml is gitignored

- **WHEN** `.gitignore` is checked
- **THEN** `config/local.yaml` is listed (credentials not committed)
- **AND** `config/local.yaml.template` is NOT listed (template is committed)

#### Scenario: Template provides credential placeholders

- **WHEN** `config/local.yaml.template` is read
- **THEN** contains placeholder values:
  - `host: "your-clickhouse-host.example.com"`
  - `user: "your-username"`
  - `password: "your-password"`
- **AND** includes instructions for copying to `local.yaml`

### Requirement: Connection Testing and Validation

The system SHALL provide connection test script to validate ClickHouse connectivity and table access.

#### Scenario: Test connection script successful

- **WHEN** `test_connection.py` is executed with valid config
- **THEN** performs following tests:
  1. Load configuration
  2. Connect to ClickHouse
  3. Execute `SELECT 1` (basic query)
  4. Execute `SHOW TABLES` (database access)
  5. Check for `enriched_distributed` table
  6. Check for `spendings_distributed` table
  7. Query row counts from both tables
  8. Disconnect
- **AND** logs "✓ CONNECTION TEST SUCCESSFUL!"
- **AND** returns exit code 0

#### Scenario: Test connection script failure

- **WHEN** `test_connection.py` is executed with invalid config
- **OR** ClickHouse is unreachable
- **OR** authentication fails
- **THEN** logs detailed error message
- **AND** logs "✗ CONNECTION TEST FAILED!"
- **AND** returns exit code 1

#### Scenario: Test connection with custom config

- **WHEN** `test_connection.py --config config/custom.yaml` is executed
- **THEN** loads configuration from specified path
- **AND** runs same validation tests

### Requirement: Backward Compatibility with Native Protocol

The system SHALL maintain 100% backward compatibility with existing native protocol configurations.

#### Scenario: Existing config with port 9000 unchanged

- **WHEN** config specifies `port: 9000` (native protocol)
- **AND** no other changes to config
- **THEN** connection works identically to previous version
- **AND** all queries execute without modification
- **AND** no breaking changes to API

#### Scenario: Default config remains native protocol

- **WHEN** `config/config.yaml` (default template) is used
- **THEN** port is 9000 (native protocol)
- **AND** behavior unchanged from previous version

### Requirement: Unified Query Execution for All Extractions

The system SHALL use protocol-agnostic `_execute_query()` method for all SQL queries in data extraction.

#### Scenario: Impressions extraction uses unified method

- **WHEN** `_extract_impressions()` executes SQL query
- **THEN** uses `self._execute_query(query)`
- **AND** NOT `self.client.execute(query)` directly

#### Scenario: Budgets extraction uses unified method

- **WHEN** `_extract_budgets()` executes SQL query
- **THEN** uses `self._execute_query(query)`
- **AND** NOT `self.client.execute(query)` directly

#### Scenario: Min bid calculation uses unified method

- **WHEN** `_calculate_min_bids()` executes SQL query
- **THEN** uses `self._execute_query(query)`
- **AND** NOT `self.client.execute(query)` directly

### Requirement: Protocol State Tracking

The system SHALL track which protocol is in use for proper connection lifecycle management.

#### Scenario: Protocol state stored after connection

- **WHEN** connection is established
- **THEN** `self.protocol` is set to either `'http'` or `'native'`
- **AND** protocol value persists until disconnect

#### Scenario: Protocol state used for disconnection

- **WHEN** `disconnect()` is called
- **THEN** uses `self.protocol` to determine correct disconnect method
- **AND** calls `client.close()` for HTTP or `client.disconnect()` for native

#### Scenario: Protocol state cleared on disconnect

- **WHEN** `disconnect()` completes
- **THEN** `self.client` is set to None
- **AND** connection state is fully reset

