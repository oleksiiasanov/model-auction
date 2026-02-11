"""
Command-line interface for auction simulator.

Usage:
    python -m auction_simulator.cli simulate --country 13 --categories 1234,5678
        --time-from 2024-01-15 --time-to 2024-01-17 --config config/local.yaml
"""

import click
import logging
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .data_extraction import DataExtractor
from .auction_engine import AuctionEngine
from .simulation import Simulation
from .reporting import Reporter
from .cleanup import clean_cache, clean_outputs, format_size


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


@click.group()
def cli():
    """Auction-Based Traffic Distribution Simulator"""
    pass


@cli.command()
@click.option('--country', type=int, required=True, help='Country ID (e.g., 13 for Azerbaijan)')
@click.option('--categories', default=None, help='Comma-separated category IDs (e.g., 1234,5678). If not specified, all categories for the country will be used.')
@click.option('--time-from', required=True, help='Start date (YYYY-MM-DD, full day only)')
@click.option('--time-to', required=True, help='End date (YYYY-MM-DD, full day only)')
@click.option('--config', default='config/config.yaml', help='Path to config file')
@click.option('--bid-step', type=float, default=None, help='Override bid_step from config (e.g., 0.003, 0.005, 0.01)')
@click.option('--feed-id', default=None, help='Comma-separated feed IDs (e.g., 6500,6002). If not specified, config value is used. Use empty string for all feeds.')
@click.option('--no-cache', is_flag=True, help='Disable local data caching')
@click.option('--clean', is_flag=True, help='Clean cache and old outputs before simulation')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def simulate(country, categories, time_from, time_to, config, bid_step, feed_id, no_cache, clean, verbose):
    """
    Run auction simulation for specified parameters.

    Example:
        python -m auction_simulator.cli simulate \\
            --country 13 \\
            --categories 1234,5678 \\
            --time-from 2024-01-15 \\
            --time-to 2024-01-17 \\
            --config config/local.yaml

    Example with custom bid_step:
        python -m auction_simulator.cli simulate \\
            --country 13 \\
            --categories 6282 \\
            --time-from 2026-01-31 \\
            --time-to 2026-02-01 \\
            --config config/local.yaml \\
            --bid-step 0.01

    Example with custom feed_id (only specific feeds):
        python -m auction_simulator.cli simulate \\
            --country 13 \\
            --categories 6282 \\
            --time-from 2026-01-31 \\
            --time-to 2026-02-01 \\
            --config config/local.yaml \\
            --feed-id 6500,6002

    Example with all feeds (no filter):
        python -m auction_simulator.cli simulate \\
            --country 13 \\
            --categories 6282 \\
            --time-from 2026-01-31 \\
            --time-to 2026-02-01 \\
            --config config/local.yaml \\
            --feed-id ""
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    try:
        # Parse parameters
        if categories is not None:
            category_list = [int(c.strip()) for c in categories.split(',')]
        else:
            category_list = None
        date_from = date.fromisoformat(time_from)
        date_to = date.fromisoformat(time_to)

        logger.info("=" * 80)
        logger.info("AUCTION SIMULATION")
        logger.info("=" * 80)
        logger.info(f"Country: {country}")
        logger.info(f"Categories: {category_list if category_list else 'ALL'}")
        logger.info(f"Time Range: {date_from} to {date_to}")
        logger.info(f"Config: {config}")
        logger.info(f"Cache: {'disabled' if no_cache else 'enabled'}")
        logger.info(f"Clean: {'enabled' if clean else 'disabled'}")
        logger.info("=" * 80)

        # Load configuration
        cfg = load_config(config)

        # Override bid_step if provided via command line
        if bid_step is not None:
            original_bid_step = cfg.simulation.bid_step
            # Modify underlying dict to ensure override persists
            cfg._config['simulation']['bid_step'] = bid_step
            logger.info("")
            logger.info("=" * 80)
            logger.info("BID_STEP OVERRIDE")
            logger.info("=" * 80)
            logger.info(f"Original (from config): {original_bid_step}")
            logger.info(f"Override (from --bid-step): {bid_step}")
            logger.info("=" * 80)
            logger.info("")

        # Override feed_id if provided via command line
        if feed_id is not None:
            # Ensure data_extraction section exists
            if 'data_extraction' not in cfg._config:
                cfg._config['data_extraction'] = {}

            original_feed_id = cfg._config['data_extraction'].get('feed_id', ['6500', '6002'])

            # Parse feed_id parameter: empty string = None (all feeds), otherwise split by comma
            if feed_id == '':
                new_feed_id = None
            else:
                new_feed_id = [fid.strip() for fid in feed_id.split(',')]

            cfg._config['data_extraction']['feed_id'] = new_feed_id
            logger.info("")
            logger.info("=" * 80)
            logger.info("FEED_ID OVERRIDE")
            logger.info("=" * 80)
            logger.info(f"Original (from config): {original_feed_id}")
            logger.info(f"Override (from --feed-id): {new_feed_id if new_feed_id else 'ALL (no filter)'}")
            logger.info("=" * 80)
            logger.info("")

        # Phase 0: Cleanup (if requested)
        if clean:
            logger.info("\nCleaning up before simulation...")

            # Clean cache
            cache_dir = Path(cfg.cache.directory)
            cache_stats = clean_cache(cache_dir)
            logger.info(f"  Cache: {cache_stats['files_removed']} files removed ({format_size(cache_stats['bytes_freed'])} freed)")

            # Clean outputs
            output_dir = Path(cfg.reporting.output_directory)
            keep_last_runs = getattr(cfg.cleanup, 'keep_last_runs', 5)
            output_stats = clean_outputs(output_dir, keep_last=keep_last_runs)
            logger.info(f"  Outputs: {output_stats['files_removed']} files removed, {output_stats['files_kept']} files kept ({format_size(output_stats['bytes_freed'])} freed)")
            logger.info("")

        # Phase 1: Data Extraction
        logger.info("\n[1/4] Extracting data from ClickHouse...")
        extractor = DataExtractor(cfg)

        try:
            impressions_df, budgets_df, min_bid_by_category, category_list = extractor.extract_data(
                country=country,
                categories=category_list,
                time_from=date_from,
                time_to=date_to,
                use_cache=not no_cache
            )
        finally:
            extractor.disconnect()

        logger.info(f"  Reach: {len(impressions_df)} records")
        logger.info(f"  Budgets: {len(budgets_df)} records")
        logger.info(f"  Categories: {len(category_list)} categories")
        logger.info(f"  Min bids: {min_bid_by_category}")

        # Phase 2: Simulation
        logger.info("\n[2/4] Running auction simulation...")
        engine = AuctionEngine(cfg)
        sim = Simulation(cfg, engine)

        simulation_results = sim.run_simulation(
            impressions_df=impressions_df,
            budgets_df=budgets_df,
            min_bid_by_category=min_bid_by_category,
            time_from=date_from,
            time_to=date_to
        )

        logger.info(f"  Simulation complete: {len(simulation_results)} ads processed")

        # Phase 3: Reporting
        logger.info("\n[3/4] Generating comparison reports...")
        reporter = Reporter(cfg)

        reporter.generate_reports(
            impressions_df=impressions_df,
            budgets_df=budgets_df,
            simulation_results=simulation_results,
            time_from=date_from,
            time_to=date_to,
            min_bid_by_category=min_bid_by_category,
            bid_step=cfg.simulation.bid_step,
            country=country,
            categories=','.join(map(str, category_list))
        )

        # Phase 4: Summary
        logger.info("\n[4/4] Summary")
        logger.info("=" * 80)
        logger.info(f"✓ Simulation completed successfully")
        logger.info(f"✓ Reports saved to: {cfg.reporting.output_directory}")
        logger.info("=" * 80)

        logger.info("\nNext steps:")
        logger.info("  1. Review seller_comparison_*.csv for per-seller metrics")
        logger.info("  2. Review ad_comparison_*.csv for per-ad metrics")
        logger.info("  3. Check summary_statistics_*.txt for overall results")

    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
def version():
    """Show version information."""
    from . import __version__
    click.echo(f"Auction Simulator v{__version__}")


if __name__ == '__main__':
    cli()
