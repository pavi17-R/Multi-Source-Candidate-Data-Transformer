"""
normalizers/email_normalizer.py

Normalizes email addresses to lowercase and deduplicates lists.
"""

from __future__ import annotations
import logging
from src.validators import validate_email

logger = logging.getLogger(__name__)


def normalize_email(raw: str) -> str | None:
    """Lowercase and strip an email. Returns None if invalid."""
    if not raw:
        return None
    cleaned = raw.strip().lower()
    valid, reason = validate_email(cleaned)
    if not valid:
        logger.warning("Skipping invalid email: %s", reason)
        return None
    return cleaned


def normalize_email_list(emails: list[str]) -> list[str]:
    """Normalize and deduplicate a list of emails."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in emails:
        normalized = normalize_email(raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
