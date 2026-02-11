"""
Main entry point for running auction simulator as a module.

Usage:
    python -m auction_simulator.cli simulate [options]
"""

from .cli import cli

if __name__ == '__main__':
    cli()
