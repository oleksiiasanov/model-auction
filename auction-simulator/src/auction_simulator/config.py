"""
Configuration management for auction simulator.

Loads configuration from YAML files with support for local overrides.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration container with nested attribute access."""

    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize config from dictionary."""
        self._config = config_dict

    def __getattr__(self, name: str) -> Any:
        """Get config value by attribute access."""
        if name.startswith('_'):
            return object.__getattribute__(self, name)

        value = self._config.get(name)
        if isinstance(value, dict):
            return Config(value)
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        """Set config value by attribute access."""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            self._config[name] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with default."""
        return self._config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self._config.copy()


def load_config(config_path: str) -> Config:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Config object with nested attribute access

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError(f"Empty config file: {config_path}")

    return Config(config_dict)
