"""
utils/config_loader.py

Loads and validates the OutputConfig from a JSON file.
Returns a default config if the file is missing or malformed.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from pydantic import ValidationError
from src.models import OutputConfig

logger = logging.getLogger(__name__)


def load_config(filepath: str | Path) -> OutputConfig:
    """
    Load OutputConfig from a JSON file.

    Args:
        filepath: Path to the JSON config file.

    Returns:
        OutputConfig instance (defaults if file is missing/invalid).
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("Config file not found: %s — using defaults", path)
        return OutputConfig()

    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return OutputConfig(**data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read config file %s: %s — using defaults", path, exc)
        return OutputConfig()
    except ValidationError as exc:
        logger.warning("Invalid config schema in %s: %s — using defaults", path, exc)
        return OutputConfig()
