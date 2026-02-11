#!/usr/bin/env python3
"""
Test ClickHouse connection.

Usage:
    python test_connection.py [--config config/local.yaml]
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auction_simulator.config import load_config
from auction_simulator.data_extraction import DataExtractor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_connection(config_path: str = "config/local.yaml"):
    """Test connection to ClickHouse."""
    try:
        logger.info("=" * 80)
        logger.info("TESTING CLICKHOUSE CONNECTION")
        logger.info("=" * 80)

        # Load config
        logger.info(f"Loading config from: {config_path}")
        config = load_config(config_path)

        logger.info(f"Host: {config.database.host}")
        logger.info(f"Port: {config.database.port}")
        logger.info(f"Database: {config.database.database}")
        logger.info(f"User: {config.database.user}")
        logger.info("")

        # Create extractor
        extractor = DataExtractor(config)

        # Connect
        logger.info("Attempting to connect...")
        extractor.connect()

        # Test simple query
        logger.info("Testing simple query: SELECT 1...")
        result = extractor._execute_query("SELECT 1")
        logger.info(f"Result: {result}")

        # Test database access
        logger.info(f"Testing database access: SHOW TABLES...")
        result = extractor._execute_query("SHOW TABLES")
        logger.info(f"Found {len(result)} tables")

        # Check for required tables
        tables = [row[0] for row in result]
        required_tables = ['enriched_distributed', 'spendings_distributed']

        logger.info("")
        logger.info("Checking for required tables:")
        for table in required_tables:
            if table in tables:
                logger.info(f"  ✓ {table} - FOUND")
            else:
                logger.warning(f"  ✗ {table} - NOT FOUND")

        # Test enriched_distributed sample
        logger.info("")
        logger.info("Testing enriched_distributed sample query...")
        query = """
        SELECT COUNT(*) as count
        FROM enriched_distributed
        LIMIT 1
        """
        result = extractor._execute_query(query)
        logger.info(f"enriched_distributed row count: {result[0][0]:,}")

        # Test spendings_distributed sample
        logger.info("")
        logger.info("Testing spendings_distributed sample query...")
        query = """
        SELECT COUNT(*) as count
        FROM analytics_reports.spendings_distributed
        LIMIT 1
        """
        result = extractor._execute_query(query)
        logger.info(f"spendings_distributed row count: {result[0][0]:,}")

        # Disconnect
        extractor.disconnect()

        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ CONNECTION TEST SUCCESSFUL!")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("✗ CONNECTION TEST FAILED!")
        logger.error("=" * 80)
        logger.error(f"Error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test ClickHouse connection")
    parser.add_argument(
        "--config",
        default="config/local.yaml",
        help="Path to config file"
    )

    args = parser.parse_args()

    success = test_connection(args.config)
    sys.exit(0 if success else 1)
