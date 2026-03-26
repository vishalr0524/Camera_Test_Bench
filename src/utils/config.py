"""
Configuration utilities for Camera Test Bench.
"""

import json
from typing import Dict, Any
from pathlib import Path


def read_config(config_path: str) -> Dict[str, Any]:
    """Read configuration from JSON file.

    Args:
        config_path: Path to the JSON configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file contains invalid JSON
        ValueError: If config file is empty or invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    if not config_path.is_file():
        raise ValueError(f"Configuration path is not a file: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()

        if not content:
            raise ValueError(f"Configuration file is empty: {config_path}")

        config = json.loads(content)
        return config

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in config file {config_path}: {str(e)}", e.doc, e.pos
        )
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading config file {config_path}: {str(e)}") from e


def config_update(base: dict, updates: dict) -> dict:
    """Deep-merge updates into base config dict."""
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            config_update(base[k], v)
        else:
            base[k] = v
    return base
