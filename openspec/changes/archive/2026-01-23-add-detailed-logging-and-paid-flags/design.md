# Design: Detailed Logging and Paid Status Flags

## Overview

Add two independent enhancements to auction simulator:
1. **Paid status classification** in comparison reports
2. **Step-by-step simulation logging** for debugging and validation

Both changes are additive and backward compatible.

## 1. Paid Status Flags Design

### Data Flow

```
Data Sources:
├─ budgets_df (from ClickHouse)
│  └─ daily_budget per (ad_id, date)
│
├─ simulation_results (from Simulation)
│  └─ simulated_spending per ad_id
│
└─ impressions_df (from ClickHouse)
   └─ is_paid per impression (historical)

↓

Reporter.build_seller_comparison()
├─ Calculate is_paid_actual per seller:
│  └─ TRUE if any ad of seller had daily_budget > 0 in budgets_df
│
└─ Calculate is_paid_simulated per seller:
   └─ TRUE if seller's total simulated_spending > 0

Reporter.build_ad_comparison()
├─ Calculate is_paid_actual per ad:
│  └─ TRUE if ad had daily_budget > 0 on any day in budgets_df
│
└─ Calculate is_paid_simulated per ad:
   └─ TRUE if ad's simulated_spending > 0
```

### Implementation Logic

#### Seller-level flags

```python
# is_paid_actual
seller_budgets = budgets_df.groupby('seller_id')['daily_budget'].max()
seller_comparison['is_paid_actual'] = seller_comparison['seller_id'].map(
    lambda sid: seller_budgets.get(sid, 0) > 0
)

# is_paid_simulated
seller_comparison['is_paid_simulated'] = (
    seller_comparison['simulated_spending'] > 0
)
```

#### Ad-level flags

```python
# is_paid_actual
ad_budgets = budgets_df.groupby('ad_id')['daily_budget'].max()
ad_comparison['is_paid_actual'] = ad_comparison['ad_id'].map(
    lambda aid: ad_budgets.get(aid, 0) > 0
)

# is_paid_simulated
ad_comparison['is_paid_simulated'] = (
    ad_comparison['simulated_spending'] > 0
)
```

### CSV Output Format

**seller_comparison_TIMESTAMP.csv:**
```csv
seller_id,is_paid_actual,is_paid_simulated,actual_impressions_total,simulated_impressions_total,...
12345,true,true,10000,12000,...
67890,true,false,5000,3000,...  # Had budget but didn't spend in simulation
11111,false,false,2000,2500,...  # Fully organic
```

**ad_comparison_TIMESTAMP.csv:**
```csv
ad_id,seller_id,is_paid_actual,is_paid_simulated,actual_impressions_total,simulated_impressions_total,...
777,12345,true,true,500,600,...
888,12345,true,true,300,400,...
999,67890,true,false,100,50,...
1000,11111,false,false,50,75,...
```

### Use Cases

**Filter paid sellers only:**
```python
df = pd.read_csv('seller_comparison_*.csv')
paid_sellers = df[df['is_paid_actual'] == True]
```

**Find status changes:**
```python
# Became paid in simulation
newly_paid = df[(df['is_paid_actual'] == False) & (df['is_paid_simulated'] == True)]

# Lost paid status in simulation
lost_paid = df[(df['is_paid_actual'] == True) & (df['is_paid_simulated'] == False)]
```

---

## 2. Simulation Logging Design

### Architecture

```
Simulation Flow:
├─ Simulation.run_simulation()
│  ├─ Logger.log_day_start()
│  ├─ For each hour:
│  │  ├─ Logger.log_hour_start()
│  │  ├─ Simulation.simulate_hour()
│  │  │  ├─ For each batch:
│  │  │  │  ├─ AuctionEngine.run_batch_auction()
│  │  │  │  │  ├─ rank_ads() → Logger.log_batch_start()
│  │  │  │  │  ├─ select_winners() → Logger.log_auction_winners()
│  │  │  │  │  ├─ charge_winners() → Logger.log_budget_changes()
│  │  │  │  │  └─ detect pacing → Logger.log_pacing_event()
│  │  │  │  └─ Logger.log_batch_complete()
│  │  │  └─ organic_fallback() → Logger.log_organic_fallback()
│  │  └─ Logger.log_hour_complete()
│  └─ Logger.log_day_complete()
└─ Logger.close()
```

### Logger Class Design

```python
class SimulationLogger:
    """Dual-format logger for simulation events."""

    def __init__(self, output_dir, timestamp, config):
        self.output_dir = Path(output_dir)
        self.timestamp = timestamp
        self.config = config

        # File handles
        self.jsonl_file = None
        self.txt_file = None

        if config.logging.simulation_log_enabled:
            if config.logging.log_format in ['jsonl', 'both']:
                self.jsonl_file = open(
                    self.output_dir / f'simulation_log_{timestamp}.jsonl', 'w'
                )

            if config.logging.log_format in ['text', 'both']:
                self.txt_file = open(
                    self.output_dir / f'simulation_summary_{timestamp}.txt', 'w'
                )

    def log_event(self, event_type: str, data: Dict):
        """Log event to both formats."""
        if self.jsonl_file:
            self._write_jsonl(event_type, data)

        if self.txt_file:
            self._write_text(event_type, data)

    def _write_jsonl(self, event_type: str, data: Dict):
        """Write structured JSON line."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': event_type,
            **data
        }
        self.jsonl_file.write(json.dumps(entry) + '\n')
        self.jsonl_file.flush()

    def _write_text(self, event_type: str, data: Dict):
        """Write human-readable text."""
        # Format based on event type
        if event_type == 'day_start':
            self.txt_file.write(f"\n{'='*80}\n")
            self.txt_file.write(f"DAY: {data['date']} | ")
            self.txt_file.write(f"Total Ads: {data['total_ads']} | ")
            self.txt_file.write(f"Ads with Budget: {data['ads_with_budget']}\n")
            self.txt_file.write(f"{'='*80}\n\n")

        elif event_type == 'batch_auction':
            self.txt_file.write(f"  Batch #{data['batch']} (slots: {data['slots']})\n")
            self.txt_file.write(f"  ├─ Eligible: {data['eligible_ads']} ads ")
            self.txt_file.write(f"({data['ads_with_budget']} with budget)\n")

            if 'top_winners' in data:
                self.txt_file.write(f"  ├─ Top {len(data['top_winners'])} Winners:\n")
                for i, w in enumerate(data['top_winners'][:self.config.logging.log_top_n_winners]):
                    self.txt_file.write(
                        f"  │  {i+1}. Ad {w['ad_id']} | "
                        f"pressure={w['pressure']:.1f} | "
                        f"bid={w['bid']:.2f}₭ | "
                        f"remaining={w['remaining_budget']:,}\n"
                    )

            self.txt_file.write(f"  └─ Allocated: {data['allocated']}\n\n")

        # ... other event types

        self.txt_file.flush()
```

### Event Types and Data

#### 1. day_start
```json
{
  "event": "day_start",
  "date": "2024-01-15",
  "total_ads": 150,
  "ads_with_budget": 45,
  "total_daily_budget": 1500000
}
```

#### 2. hour_start
```json
{
  "event": "hour_start",
  "date": "2024-01-15",
  "hour": 10,
  "category_id": 1234,
  "total_impressions": 5000,
  "min_bid": 0.5
}
```

#### 3. batch_start
```json
{
  "event": "batch_start",
  "batch": 1,
  "category_id": 1234,
  "hour": 10,
  "slots": 40,
  "eligible_ads": 100,
  "ads_with_budget": 40,
  "time_progress": 0.42,
  "time_left": 0.58
}
```

#### 4. auction_winners
```json
{
  "event": "auction_winners",
  "batch": 1,
  "category_id": 1234,
  "hour": 10,
  "top_winners": [
    {
      "ad_id": 777,
      "seller_id": 12345,
      "pressure": 13793.5,
      "rank": 0,
      "bid": 1.4,
      "remaining_budget": 9998,
      "impressions_won": 1
    },
    ...
  ],
  "total_winners": 40
}
```

#### 5. pressure_change
```json
{
  "event": "pressure_change",
  "batch": 2,
  "ad_id": 777,
  "pressure_before": 13793.5,
  "pressure_after": 13791.2,
  "budget_before": 10000,
  "budget_after": 9998,
  "reason": "charged_for_impression"
}
```

#### 6. pacing_exclusion
```json
{
  "event": "pacing_exclusion",
  "batch": 5,
  "ad_id": 888,
  "reason": "exceeded_pacing_limit",
  "actual_spend": 350,
  "expected_spend": 250,
  "max_allowed": 300,
  "pacing_tolerance": 0.2
}
```

#### 7. budget_exhaustion
```json
{
  "event": "budget_exhaustion",
  "batch": 45,
  "ad_id": 999,
  "initial_budget": 5000,
  "total_spent": 5000,
  "impressions_won": 3500,
  "hour": 14
}
```

#### 8. organic_fallback
```json
{
  "event": "organic_fallback",
  "category_id": 1234,
  "hour": 10,
  "remaining_slots": 200,
  "method": "proportional",
  "allocations": [
    {"ad_id": 999, "organic_historical": 100, "allocated": 150},
    {"ad_id": 1000, "organic_historical": 50, "allocated": 50}
  ],
  "conservation_check": {"expected": 200, "actual": 200, "valid": true}
}
```

#### 9. hour_complete
```json
{
  "event": "hour_complete",
  "category_id": 1234,
  "hour": 10,
  "total_allocated": 5000,
  "paid_slots": 4800,
  "organic_slots": 200,
  "num_batches": 125,
  "unique_winners": 45
}
```

### Configuration

```yaml
logging:
  # Enable simulation logging
  simulation_log_enabled: true

  # Log format: jsonl, text, or both
  log_format: "both"

  # Number of top winners to log per batch
  log_top_n_winners: 10

  # Track pressure changes between batches
  log_pressure_changes: true

  # Log pacing gate events
  log_pacing_events: true

  # Log budget exhaustion events
  log_budget_events: true

  # Output directory
  log_directory: "outputs"
```

### Performance Considerations

**I/O Overhead:**
- JSONL: ~100-200 bytes per event
- TXT: ~50-100 bytes per event (less verbose)
- Typical simulation: ~10,000 events per day
- Total log size: 1-5 MB per day (JSONL + TXT)

**Optimization:**
- Buffered I/O (flush every N events or every second)
- Optional: Only log top-N winners (not all 40)
- Optional: Disable logging for production runs

**Memory:**
- Negligible (streaming writes, no accumulation)

### Analysis Tools

**Query JSONL logs:**
```bash
# Find all budget exhaustion events
cat simulation_log_*.jsonl | jq 'select(.event == "budget_exhaustion")'

# Calculate average pressure per ad
cat simulation_log_*.jsonl | jq -s '
  map(select(.event == "auction_winners") | .top_winners[]) |
  group_by(.ad_id) |
  map({ad_id: .[0].ad_id, avg_pressure: (map(.pressure) | add / length)})
'

# Count pacing exclusions per hour
cat simulation_log_*.jsonl | jq -s '
  map(select(.event == "pacing_exclusion")) |
  group_by(.hour) |
  map({hour: .[0].hour, count: length})
'
```

**Python analysis:**
```python
import json
import pandas as pd

# Load JSONL
events = []
with open('simulation_log_20240115.jsonl') as f:
    for line in f:
        events.append(json.loads(line))

df = pd.DataFrame(events)

# Find ads that exhausted budget
exhausted = df[df['event'] == 'budget_exhaustion']['ad_id'].unique()

# Trace pressure changes for specific ad
ad_777_pressure = df[
    (df['event'] == 'auction_winners') &
    (df['top_winners'].apply(lambda x: any(w['ad_id'] == 777 for w in x)))
]
```

## Integration Points

### In Simulation class

```python
class Simulation:
    def __init__(self, config, auction_engine):
        self.config = config
        self.engine = auction_engine
        self.logger = SimulationLogger(
            config.reporting.output_directory,
            datetime.now().strftime("%Y%m%d_%H%M%S"),
            config
        ) if config.logging.simulation_log_enabled else None

    def run_simulation(self, ...):
        if self.logger:
            self.logger.log_event('day_start', {
                'date': current_date,
                'total_ads': len(self.ads),
                'ads_with_budget': sum(1 for a in self.ads.values() if a.daily_budget > 0)
            })

        # ... existing logic
```

### In AuctionEngine class

```python
class AuctionEngine:
    def run_batch_auction(self, ads, min_bid, time_progress, time_left, batch_slots, logger=None):
        # Log batch start
        if logger:
            logger.log_event('batch_start', {
                'slots': batch_slots,
                'eligible_ads': len(ads),
                'ads_with_budget': sum(1 for a in ads if a.remaining_budget > 0),
                'time_progress': time_progress,
                'time_left': time_left
            })

        # Rank ads
        ranked = self.rank_ads(ads, time_progress, time_left)

        # Select winners
        winners = self.select_winners(ranked, min_bid, batch_slots)

        # Log winners
        if logger:
            top_winners = [
                {
                    'ad_id': ad.ad_id,
                    'seller_id': ad.seller_id,
                    'pressure': pressure,
                    'rank': rank_index,
                    'bid': effective_bid,
                    'remaining_budget': ad.remaining_budget,
                    'impressions_won': impressions
                }
                for ad, effective_bid, impressions in winners[:logger.config.logging.log_top_n_winners]
            ]

            logger.log_event('auction_winners', {
                'top_winners': top_winners,
                'total_winners': len(winners)
            })

        # Charge winners
        self.charge_winners(winners)

        return len(winners)
```

## Alternatives Considered

### Alternative 1: Single format (JSONL only)
**Pros:** Simpler implementation, smaller codebase
**Cons:** Not human-readable, requires tools to view
**Rejected:** Need both machine and human readability

### Alternative 2: Single format (TXT only)
**Pros:** Human-readable, easy scanning
**Cons:** Hard to programmatically analyze
**Rejected:** Need programmatic analysis capability

### Alternative 3: SQLite database
**Pros:** Queryable, structured, efficient
**Cons:** Overhead, requires DB library, harder to share
**Rejected:** JSONL sufficient for analysis needs

### Alternative 4: is_paid single column
**Pros:** Simpler schema
**Cons:** Cannot see status changes (actual → simulated)
**Rejected:** Need to track both dimensions

## Chosen Approach

**Dual-format logging (JSONL + TXT):**
- Best of both worlds
- JSONL for analysis, TXT for quick viewing
- Configurable (can disable either)
- Acceptable overhead (~5-10%)

**Two is_paid columns:**
- Clear distinction between actual and simulated
- Enables change detection
- Minimal storage overhead (2 boolean columns)
