"""
Simulation logging for auction simulator.

Provides dual-format logging (JSONL + human-readable text) for complete
simulation traceability and debugging.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def convert_to_python_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_python_types(item) for item in obj]
    return obj


class SimulationLogger:
    """Dual-format logger for simulation events."""

    def __init__(self, output_dir: str, timestamp: str, config):
        """
        Initialize simulation logger.

        Args:
            output_dir: Directory for log files
            timestamp: Timestamp string for filenames
            config: Configuration object with logging settings
        """
        self.output_dir = Path(output_dir)
        self.timestamp = timestamp
        self.config = config
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # File handles
        self.jsonl_file = None
        self.txt_file = None

        # Track previous batch winners for pressure change detection
        self.prev_batch_winners = {}

        if config.logging.simulation_log_enabled:
            log_format = config.logging.log_format

            if log_format in ['jsonl', 'both']:
                jsonl_path = self.output_dir / f'simulation_log_{timestamp}.jsonl'
                self.jsonl_file = open(jsonl_path, 'w')
                logger.info(f"JSONL log: {jsonl_path}")

            if log_format in ['text', 'both']:
                txt_path = self.output_dir / f'simulation_summary_{timestamp}.txt'
                self.txt_file = open(txt_path, 'w')
                logger.info(f"Text log: {txt_path}")

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log event to configured formats.

        Args:
            event_type: Type of event (e.g., 'day_start', 'batch_auction')
            data: Event-specific data dictionary
        """
        if self.jsonl_file:
            self._write_jsonl(event_type, data)

        if self.txt_file:
            self._write_text(event_type, data)

    def _write_jsonl(self, event_type: str, data: Dict[str, Any]):
        """Write structured JSON line."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': event_type,
            **data
        }
        # Convert numpy types to Python native types
        entry = convert_to_python_types(entry)
        self.jsonl_file.write(json.dumps(entry) + '\n')
        self.jsonl_file.flush()

    def _write_text(self, event_type: str, data: Dict[str, Any]):
        """Write human-readable text."""
        if event_type == 'day_start':
            self.txt_file.write('\n' + '=' * 80 + '\n')
            self.txt_file.write(f"DAY: {data['date']} | ")
            self.txt_file.write(f"Total Ads: {data['total_ads']} | ")
            self.txt_file.write(f"Ads with Budget: {data['ads_with_budget']}\n")
            self.txt_file.write('=' * 80 + '\n\n')

        elif event_type == 'hour_start':
            self.txt_file.write(f"[{data['hour']:02d}:00] Category {data['category_id']} | ")
            self.txt_file.write(f"Total Reach: {data['total_reach']:,}\n")
            self.txt_file.write('-' * 72 + '\n\n')

        elif event_type == 'batch_start':
            self.txt_file.write(f"  Batch #{data['batch']} (slots: {data['slots']})\n")
            self.txt_file.write(f"  ├─ Eligible: {data['eligible_ads']} ads ")
            self.txt_file.write(f"({data['ads_with_budget']} with budget)\n")

        elif event_type == 'auction_winners':
            top_n = self.config.logging.log_top_n_winners
            winners = data.get('top_winners', [])[:top_n]

            if winners:
                self.txt_file.write(f"  ├─ Top {len(winners)} Winners:\n")
                for i, w in enumerate(winners):
                    self.txt_file.write(
                        f"  │  {i+1}. Ad {w['ad_id']} | "
                        f"pressure={w['pressure']:.1f} | "
                        f"bid={w['bid']:.2f}₭ | "
                        f"remaining={w['remaining_budget']:,}\n"
                    )

        elif event_type == 'batch_complete':
            self.txt_file.write(f"  └─ Allocated: {data['allocated']} | ")
            self.txt_file.write(f"Remaining: {data['remaining_slots']:,}\n\n")

        elif event_type == 'pressure_change':
            if self.config.logging.log_pressure_changes:
                self.txt_file.write(f"    → Pressure change: Ad {data['ad_id']} ")
                self.txt_file.write(f"({data['pressure_before']:.1f} → {data['pressure_after']:.1f})\n")

        elif event_type == 'pacing_exclusion':
            if self.config.logging.log_pacing_events:
                self.txt_file.write(f"    ⏸ Pacing pause: Ad {data['ad_id']} ")
                self.txt_file.write(f"(spent {data['actual_spend']:.0f} > max {data['max_allowed']:.0f})\n")

        elif event_type == 'budget_exhaustion':
            if self.config.logging.log_budget_events:
                self.txt_file.write(f"    ⚠ Budget exhausted: Ad {data['ad_id']} ")
                self.txt_file.write(f"(spent {data['total_spent']:,} kopecks, {data['reach_won']} reach)\n")

        elif event_type == 'organic_fallback':
            self.txt_file.write(f"\n  Organic Fallback (method: {data['method']})\n")
            self.txt_file.write(f"  ├─ Remaining slots: {data['remaining_slots']:,}\n")

            allocations = data.get('allocations', [])[:10]  # Show top 10
            if allocations:
                self.txt_file.write("  ├─ Allocations:\n")
                for alloc in allocations:
                    self.txt_file.write(
                        f"  │  Ad {alloc['ad_id']}: {alloc['allocated']} slots "
                        f"(historical: {alloc.get('organic_historical', 0)})\n"
                    )

            check = data.get('conservation_check', {})
            if check:
                symbol = '✓' if check.get('valid') else '✗'
                self.txt_file.write(f"  └─ Conservation: {check['actual']} == {check['expected']} {symbol}\n")

        elif event_type == 'hour_complete':
            self.txt_file.write(f"\n[{data['hour']:02d}:00] Summary\n")
            self.txt_file.write(f"  ├─ Total allocated: {data['total_allocated']:,}\n")
            self.txt_file.write(f"  ├─ Paid slots: {data['paid_slots']:,} ({data['paid_slots']/data['total_allocated']*100:.1f}%)\n")
            self.txt_file.write(f"  ├─ Organic slots: {data['organic_slots']:,} ({data['organic_slots']/data['total_allocated']*100:.1f}%)\n")
            self.txt_file.write(f"  └─ Duration: {data['num_batches']} batches\n\n")

        elif event_type == 'day_complete':
            self.txt_file.write('\n' + '=' * 80 + '\n')
            self.txt_file.write(f"DAY {data['date']} COMPLETE\n")
            self.txt_file.write(f"Total Reach: {data['total_reach_allocated']:,}\n")
            self.txt_file.write(f"Total Spending: {data['total_spending']/100:.2f} AZN\n")
            self.txt_file.write('=' * 80 + '\n\n')

        self.txt_file.flush()

    def track_pressure_changes(self, batch: int, current_winners: List[Dict]):
        """
        Track and log pressure changes between batches.

        Args:
            batch: Current batch number
            current_winners: List of current batch winners
        """
        if not self.config.logging.log_pressure_changes:
            return

        if batch > 1 and self.prev_batch_winners:
            # Compare with previous batch
            for winner in current_winners:
                ad_id = winner['ad_id']
                if ad_id in self.prev_batch_winners:
                    prev = self.prev_batch_winners[ad_id]
                    if winner['pressure'] != prev['pressure']:
                        self.log_event('pressure_change', {
                            'batch': batch,
                            'ad_id': ad_id,
                            'pressure_before': prev['pressure'],
                            'pressure_after': winner['pressure'],
                            'budget_before': prev['remaining_budget'],
                            'budget_after': winner['remaining_budget'],
                            'reason': 'charged_for_reach' if winner['remaining_budget'] < prev['remaining_budget'] else 'time_progression'
                        })

        # Store current winners for next comparison
        self.prev_batch_winners = {w['ad_id']: w for w in current_winners}

    def close(self):
        """Close all file handles."""
        if self.jsonl_file:
            self.jsonl_file.close()
            self.jsonl_file = None

        if self.txt_file:
            self.txt_file.close()
            self.txt_file = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
