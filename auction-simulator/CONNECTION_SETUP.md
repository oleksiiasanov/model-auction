# ClickHouse Connection Setup

## Quick Start

### 1. Install Dependencies

```bash
cd auction-simulator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies (including clickhouse-connect for HTTP)
pip install -e .
```

### 2. Connection Configuration

The connection is **already configured** in `config/local.yaml`:

```yaml
database:
  type: clickhouse
  host: "ch-prod.yallasvc.net"
  port: 8123  # HTTP protocol
  database: "analytics"
  user: "app_tableau_20230509"
  password: "vmkdWSxgi8k%NrW"
  secure: false
```

### 3. Test Connection

```bash
python test_connection.py
```

**Expected output:**
```
================================================================================
TESTING CLICKHOUSE CONNECTION
================================================================================
Loading config from: config/local.yaml
Host: ch-prod.yallasvc.net
Port: 8123
Database: analytics
User: app_tableau_20230509

Attempting to connect...
INFO - Connecting to ClickHouse via HTTP: ch-prod.yallasvc.net:8123
INFO - Connected to ClickHouse successfully (HTTP protocol)
Testing simple query: SELECT 1...
Result: [(1,)]
Testing database access: SHOW TABLES...
Found X tables

Checking for required tables:
  ✓ enriched_distributed - FOUND
  ✓ spendings_distributed - NOT FOUND  # May need full name: analytics_reports.spendings_distributed
...
================================================================================
✓ CONNECTION TEST SUCCESSFUL!
================================================================================
```

## Protocol Support

The simulator **automatically detects** the protocol based on port:
- **Port 8123 or 8443** → HTTP protocol (uses `clickhouse-connect`)
- **Port 9000** → Native protocol (uses `clickhouse-driver`)

Your current setup uses **HTTP (port 8123)**.

## Troubleshooting

### Error: "clickhouse-connect is required"

```bash
pip install clickhouse-connect
```

### Error: "Connection timeout"

Check network access to `ch-prod.yallasvc.net`:
```bash
ping ch-prod.yallasvc.net
curl http://ch-prod.yallasvc.net:8123/ping
```

### Error: "Authentication failed"

Verify credentials in `config/local.yaml`:
- Username: `app_tableau_20230509`
- Password: `vmkdWSxgi8k%NrW`

### Error: "Table not found"

If `spendings_distributed` is not found, try full table name:
```sql
SELECT * FROM analytics_reports.spendings_distributed LIMIT 1
```

Update code in `data_extraction.py` if needed.

## Table Schema Verification

Check the schema of required tables:

```bash
# From ClickHouse client or test_connection.py
DESCRIBE enriched_distributed;
DESCRIBE analytics_reports.spendings_distributed;
```

Required fields for **enriched_distributed**:
- `category_id`
- `ad_id`
- `user_id` (as seller_id)
- `country_id`
- `campaign_show_ad` (for is_paid detection)
- `timestamp`
- `data_chunk_date`
- `feed_id` (should be '6500' for category feed)
- `ad_type` (should be '1')

Required fields for **spendings_distributed**:
- `ad_id`
- `user_id` (as seller_id)
- `operationdate` (date)
- `price_per_day` (daily_budget in kopecks)
- `spending` (actual_spend in kopecks)
- `campaign_id`
- `country_id`

## Next Steps

After successful connection test:

1. **Verify data availability:**
   ```bash
   # Check date range
   SELECT MIN(data_chunk_date), MAX(data_chunk_date)
   FROM enriched_distributed
   WHERE country_id = 13;  # Azerbaijan
   ```

2. **Check categories:**
   ```bash
   SELECT DISTINCT category_id, COUNT(*) as impressions
   FROM enriched_distributed
   WHERE country_id = 13
     AND data_chunk_date >= '2024-01-15'
     AND data_chunk_date <= '2024-01-17'
   GROUP BY category_id
   ORDER BY impressions DESC
   LIMIT 10;
   ```

3. **Run first simulation:**
   ```bash
   python -m auction_simulator.cli simulate \
     --country 13 \
     --categories 1234,5678 \
     --time-from 2024-01-15 \
     --time-to 2024-01-15 \
     --config config/local.yaml \
     --verbose
   ```

## Security Notes

- `config/local.yaml` is **gitignored** (credentials won't be committed)
- For production use, consider using environment variables or secrets manager
- Current credentials are for read-only access (`app_tableau_*` user)
