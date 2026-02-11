"""
Unit tests for cleanup module.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from auction_simulator.cleanup import format_size, clean_cache, clean_outputs


class TestFormatSize:
    """Tests for format_size() function."""

    def test_zero_bytes(self):
        """Test formatting zero bytes."""
        assert format_size(0) == "0 B"

    def test_bytes(self):
        """Test formatting bytes (< 1024)."""
        assert format_size(500) == "500 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(10240) == "10.0 KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_size(1048576) == "1.0 MB"
        assert format_size(47560704) == "45.4 MB"
        assert format_size(104857600) == "100.0 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_size(1073741824) == "1.0 GB"
        assert format_size(1610612736) == "1.5 GB"


class TestCleanCache:
    """Tests for clean_cache() function."""

    def test_nonexistent_directory(self):
        """Test cleanup on non-existent directory."""
        non_existent = Path("/tmp/nonexistent_cache_dir_12345")
        result = clean_cache(non_existent)

        assert result["files_removed"] == 0
        assert result["bytes_freed"] == 0

    def test_empty_directory(self):
        """Test cleanup on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            result = clean_cache(cache_dir)

            assert result["files_removed"] == 0
            assert result["bytes_freed"] == 0
            assert cache_dir.exists()  # Directory still exists

    def test_single_file(self):
        """Test cleanup with single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            test_file = cache_dir / "test.cache"
            test_file.write_text("test content")

            result = clean_cache(cache_dir)

            assert result["files_removed"] == 1
            assert result["bytes_freed"] > 0
            assert not test_file.exists()  # File removed
            assert cache_dir.exists()  # Directory still exists

    def test_multiple_files(self):
        """Test cleanup with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create multiple files
            file1 = cache_dir / "cache1.dat"
            file2 = cache_dir / "cache2.dat"
            file3 = cache_dir / "cache3.dat"

            file1.write_text("content1")
            file2.write_text("content2")
            file3.write_text("content3")

            result = clean_cache(cache_dir)

            assert result["files_removed"] == 3
            assert result["bytes_freed"] > 0
            assert not file1.exists()
            assert not file2.exists()
            assert not file3.exists()

    def test_nested_directories(self):
        """Test cleanup with nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create nested structure
            subdir = cache_dir / "subdir"
            subdir.mkdir()

            file1 = cache_dir / "file1.cache"
            file2 = subdir / "file2.cache"

            file1.write_text("content1")
            file2.write_text("content2")

            result = clean_cache(cache_dir)

            assert result["files_removed"] == 2
            assert not file1.exists()
            assert not file2.exists()


class TestCleanOutputs:
    """Tests for clean_outputs() function."""

    def test_nonexistent_directory(self):
        """Test cleanup on non-existent directory."""
        non_existent = Path("/tmp/nonexistent_output_dir_12345")
        result = clean_outputs(non_existent, keep_last=5)

        assert result["files_removed"] == 0
        assert result["files_kept"] == 0
        assert result["bytes_freed"] == 0

    def test_empty_directory(self):
        """Test cleanup on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = clean_outputs(output_dir, keep_last=5)

            assert result["files_removed"] == 0
            assert result["files_kept"] == 0
            assert result["bytes_freed"] == 0

    def test_keep_recent_runs(self):
        """Test that recent runs are kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create 10 runs (30 files total)
            timestamps = [
                "20260201_100000",
                "20260201_110000",
                "20260201_120000",
                "20260201_130000",
                "20260201_140000",
                "20260201_150000",
                "20260201_160000",
                "20260201_170000",
                "20260201_180000",
                "20260201_190000",
            ]

            for ts in timestamps:
                (output_dir / f"ad_comparison_{ts}.csv").write_text("data")
                (output_dir / f"seller_comparison_{ts}.csv").write_text("data")
                (output_dir / f"summary_statistics_{ts}.txt").write_text("data")

            # Keep last 5 runs
            result = clean_outputs(output_dir, keep_last=5)

            assert result["files_removed"] == 15  # 5 old runs × 3 files
            assert result["files_kept"] == 15  # 5 recent runs × 3 files
            assert result["bytes_freed"] > 0

            # Verify newest 5 runs still exist
            for ts in timestamps[-5:]:
                assert (output_dir / f"ad_comparison_{ts}.csv").exists()
                assert (output_dir / f"seller_comparison_{ts}.csv").exists()
                assert (output_dir / f"summary_statistics_{ts}.txt").exists()

            # Verify oldest 5 runs removed
            for ts in timestamps[:5]:
                assert not (output_dir / f"ad_comparison_{ts}.csv").exists()
                assert not (output_dir / f"seller_comparison_{ts}.csv").exists()
                assert not (output_dir / f"summary_statistics_{ts}.txt").exists()

    def test_keep_last_1(self):
        """Test keeping only the most recent run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create 3 runs
            timestamps = ["20260201_100000", "20260201_110000", "20260201_120000"]

            for ts in timestamps:
                (output_dir / f"ad_comparison_{ts}.csv").write_text("data")
                (output_dir / f"seller_comparison_{ts}.csv").write_text("data")
                (output_dir / f"summary_statistics_{ts}.txt").write_text("data")

            result = clean_outputs(output_dir, keep_last=1)

            assert result["files_removed"] == 6  # 2 old runs × 3 files
            assert result["files_kept"] == 3  # 1 recent run × 3 files

            # Only newest exists
            assert (output_dir / "ad_comparison_20260201_120000.csv").exists()
            assert not (output_dir / "ad_comparison_20260201_110000.csv").exists()
            assert not (output_dir / "ad_comparison_20260201_100000.csv").exists()

    def test_fewer_runs_than_keep_last(self):
        """Test when there are fewer runs than keep_last."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create only 2 runs
            timestamps = ["20260201_100000", "20260201_110000"]

            for ts in timestamps:
                (output_dir / f"ad_comparison_{ts}.csv").write_text("data")
                (output_dir / f"seller_comparison_{ts}.csv").write_text("data")
                (output_dir / f"summary_statistics_{ts}.txt").write_text("data")

            # Try to keep 5, but only 2 exist
            result = clean_outputs(output_dir, keep_last=5)

            assert result["files_removed"] == 0  # Nothing to remove
            assert result["files_kept"] == 6  # All 2 runs kept

            # Both runs still exist
            for ts in timestamps:
                assert (output_dir / f"ad_comparison_{ts}.csv").exists()
                assert (output_dir / f"seller_comparison_{ts}.csv").exists()
                assert (output_dir / f"summary_statistics_{ts}.txt").exists()

    def test_ignores_non_matching_files(self):
        """Test that non-output files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create output files
            (output_dir / "ad_comparison_20260201_100000.csv").write_text("data")
            (output_dir / "seller_comparison_20260201_100000.csv").write_text("data")
            (output_dir / "summary_statistics_20260201_100000.txt").write_text("data")

            # Create non-matching files
            (output_dir / "README.txt").write_text("readme")
            (output_dir / "other_file.csv").write_text("other")

            result = clean_outputs(output_dir, keep_last=0)

            # Output files removed, non-matching files kept
            assert result["files_removed"] == 3
            assert (output_dir / "README.txt").exists()
            assert (output_dir / "other_file.csv").exists()
