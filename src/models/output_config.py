"""
models/output_config.py

Pydantic model for the runtime output configuration.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class OutputConfig(BaseModel):
    """
    Controls which fields appear in the final JSON output,
    optional renaming, and whether to include metadata.
    """

    fields: list[str] | None = None  # None means include all
    rename: dict[str, str] = Field(default_factory=dict)
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: Literal["null", "omit"] = "null"
