"""
Tests for configuration management.
"""

import pytest
from pathlib import Path
from auction_simulator.config import Config, load_config


def test_config_attribute_access():
    """Test nested attribute access in Config."""
    config_dict = {
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,
            'batch_size': 40
        },
        'database': {
            'host': 'localhost',
            'port': 9000
        }
    }

    config = Config(config_dict)

    assert config.simulation.min_time_left_threshold == 0.001
    assert config.simulation.min_time_progress_threshold == 0.042
    assert config.simulation.batch_size == 40
    assert config.database.host == 'localhost'
    assert config.database.port == 9000


def test_config_get_with_default():
    """Test get method with default value."""
    config_dict = {
        'simulation': {
            'min_time_left_threshold': 0.001
        }
    }

    config = Config(config_dict)

    assert config.get('simulation') is not None
    assert config.get('nonexistent', 'default') == 'default'


def test_config_to_dict():
    """Test conversion back to dictionary."""
    config_dict = {
        'simulation': {
            'min_time_left_threshold': 0.001
        }
    }

    config = Config(config_dict)
    result = config.to_dict()

    assert result == config_dict


def test_load_config_file_not_found():
    """Test error handling when config file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_config('nonexistent.yaml')


def test_load_config_from_example(tmp_path):
    """Test loading valid config from file."""
    config_file = tmp_path / "test_config.yaml"

    config_content = """
simulation:
  min_time_left_threshold: 0.001
  min_time_progress_threshold: 0.042
  pacing_tolerance: 0.2
  bid_step: 0.1
  batch_size: 40

database:
  host: "localhost"
  port: 9000
"""

    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert config.simulation.min_time_left_threshold == 0.001
    assert config.simulation.min_time_progress_threshold == 0.042
    assert config.simulation.pacing_tolerance == 0.2
    assert config.database.host == "localhost"
    assert config.database.port == 9000
