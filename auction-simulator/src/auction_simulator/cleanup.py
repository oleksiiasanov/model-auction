"""
Cleanup utilities for cache and output files.

Provides functions to remove old cache and simulation output files
to maintain a clean working environment.
"""

import logging
from pathlib import Path
from typing import Dict
import re

logger = logging.getLogger(__name__)


def format_size(bytes: int) -> str:
    """
    Convert bytes to human-readable format.

    Args:
        bytes: Number of bytes

    Returns:
        Human-readable string (e.g., "45.3 MB", "1.2 GB")
    """
    if bytes == 0:
        return "0 B"

    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def clean_cache(cache_dir: Path) -> Dict[str, int]:
    """
    Remove all files from cache directory.

    Args:
        cache_dir: Path to cache directory

    Returns:
        Dictionary with cleanup stats:
        - files_removed: Number of files deleted
        - bytes_freed: Total bytes freed
    """
    files_removed = 0
    bytes_freed = 0

    if not cache_dir.exists():
        logger.debug(f"Cache directory does not exist: {cache_dir}")
        return {"files_removed": 0, "bytes_freed": 0}

    # Recursively find all files in cache directory
    for file_path in cache_dir.rglob('*'):
        if file_path.is_file():
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                files_removed += 1
                bytes_freed += file_size
                logger.debug(f"Removed cache file: {file_path} ({format_size(file_size)})")
            except Exception as e:
                logger.warning(f"Failed to remove cache file {file_path}: {e}")

    return {
        "files_removed": files_removed,
        "bytes_freed": bytes_freed
    }


def clean_outputs(output_dir: Path, keep_last: int = 5) -> Dict[str, int]:
    """
    Remove old output files, keeping only the most recent runs.

    One "run" consists of files with the same timestamp:
    - ad_comparison_YYYYMMDD_HHMMSS.csv
    - seller_comparison_YYYYMMDD_HHMMSS.csv
    - summary_statistics_YYYYMMDD_HHMMSS.txt
    - simulation_log_YYYYMMDD_HHMMSS.jsonl
    - simulation_summary_YYYYMMDD_HHMMSS.txt

    Args:
        output_dir: Path to outputs directory
        keep_last: Number of recent runs to keep (default: 5)

    Returns:
        Dictionary with cleanup stats:
        - files_removed: Number of files deleted
        - files_kept: Number of files kept
        - bytes_freed: Total bytes freed
    """
    files_removed = 0
    files_kept = 0
    bytes_freed = 0

    if not output_dir.exists():
        logger.debug(f"Output directory does not exist: {output_dir}")
        return {"files_removed": 0, "files_kept": 0, "bytes_freed": 0}

    # Pattern to extract timestamp from output filenames
    # Matches: ad_comparison_20260202_115131.csv
    #          seller_comparison_20260202_115131.csv
    #          summary_statistics_20260202_115131.txt
    #          simulation_log_20260202_115131.jsonl
    #          simulation_summary_20260202_115131.txt
    timestamp_pattern = re.compile(r'_(\d{8}_\d{6})\.(csv|txt|jsonl)$')

    # Collect all output files with their timestamps
    files_by_timestamp = {}

    for file_path in output_dir.glob('*'):
        if file_path.is_file():
            match = timestamp_pattern.search(file_path.name)
            if match:
                timestamp = match.group(1)
                if timestamp not in files_by_timestamp:
                    files_by_timestamp[timestamp] = []
                files_by_timestamp[timestamp].append(file_path)

    # Sort timestamps (newest first)
    sorted_timestamps = sorted(files_by_timestamp.keys(), reverse=True)

    # Determine which timestamps to keep
    timestamps_to_keep = set(sorted_timestamps[:keep_last])

    # Remove files from old runs
    for timestamp, file_paths in files_by_timestamp.items():
        if timestamp in timestamps_to_keep:
            files_kept += len(file_paths)
            logger.debug(f"Keeping run {timestamp}: {len(file_paths)} files")
        else:
            for file_path in file_paths:
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    files_removed += 1
                    bytes_freed += file_size
                    logger.debug(f"Removed output file: {file_path.name} ({format_size(file_size)})")
                except Exception as e:
                    logger.warning(f"Failed to remove output file {file_path}: {e}")

    return {
        "files_removed": files_removed,
        "files_kept": files_kept,
        "bytes_freed": bytes_freed
    }
