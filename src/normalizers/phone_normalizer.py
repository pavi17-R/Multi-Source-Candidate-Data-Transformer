"""
normalizers/phone_normalizer.py

Converts phone numbers to E.164-like format (+XXXXXXXXXXX).
Uses the 'phonenumbers' library for robust parsing.
Falls back gracefully when parsing fails.
"""

from __future__ import annotations
import logging
import phonenumbers

logger = logging.getLogger(__name__)


def normalize_phone(raw: str, default_region: str = "US") -> str | None:
    """
    Parse and format a phone number in E.164 format.

    Args:
        raw: Raw phone string (e.g. "+1-415-555-0101", "415 555 0102").
        default_region: ISO 3166-1 alpha-2 region hint for numbers without country code.

    Returns:
        E.164 string like "+14155550101", or None if parsing fails.
    """
    if not raw or not raw.strip():
        return None
    try:
        parsed = phonenumbers.parse(raw.strip(), default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        logger.warning("Phone number not valid: %r", raw)
        return None
    except phonenumbers.phonenumberutil.NumberParseException:
        logger.warning("Could not parse phone number: %r", raw)
        return None
