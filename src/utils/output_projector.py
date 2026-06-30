"""
utils/output_projector.py

Applies the OutputConfig to a CanonicalCandidate to produce the final
JSON-serializable dict.

The canonical model is never mutated. Only the output representation changes.
"""

from __future__ import annotations
import logging
from src.models import CanonicalCandidate, OutputConfig

logger = logging.getLogger(__name__)

# All top-level fields on CanonicalCandidate that are public data (not metadata)
ALL_DATA_FIELDS = [
    "candidate_id",
    "full_name",
    "emails",
    "phones",
    "location",
    "links",
    "headline",
    "years_experience",
    "skills",
    "experience",
    "education",
]


def project(candidate: CanonicalCandidate, config: OutputConfig) -> dict:
    """
    Build the output dict from a canonical candidate according to the config.

    Args:
        candidate: The canonical candidate object.
        config: Runtime output configuration.

    Returns:
        A plain dict suitable for JSON serialization.
    """
    selected_fields = config.fields if config.fields is not None else ALL_DATA_FIELDS

    output: dict = {}

    for field in selected_fields:
        # Skip metadata fields handled separately below
        if field in ("provenance", "overall_confidence"):
            continue

        raw_value = getattr(candidate, field, None)
        serialized = _serialize(raw_value)

        if isinstance(raw_value, list):
            # List-typed schema fields (emails, phones, skills, experience,
            # education) always keep an empty list as [] rather than null --
            # the assignment schema requires the key to remain a list type.
            # on_missing="omit" still allows dropping the key entirely.
            if serialized == [] and config.on_missing == "omit":
                continue
        else:
            # Scalars and structured single objects: null is unavailable data.
            is_missing = serialized is None or (isinstance(serialized, dict) and not serialized)
            if is_missing:
                if config.on_missing == "omit":
                    continue
                serialized = None

        out_key = config.rename.get(field, field)
        output[out_key] = serialized

    # Append overall_confidence if requested
    if "overall_confidence" in selected_fields:
        out_key = config.rename.get("overall_confidence", "overall_confidence")
        if config.include_confidence:
            output[out_key] = candidate.overall_confidence
        elif config.on_missing != "omit":
            output[out_key] = None

    # Append provenance if requested
    if "provenance" in selected_fields and config.include_provenance:
        out_key = config.rename.get("provenance", "provenance")
        output[out_key] = [entry.model_dump() for entry in candidate.provenance]

    return output


def _serialize(value):
    """Recursively serialize Pydantic models / lists of models into plain Python data."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value
