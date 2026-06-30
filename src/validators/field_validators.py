"""
validators/field_validators.py

Functions to validate individual field values.
Returns (is_valid, reason) tuples so callers can decide how to handle failures.
"""

from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> tuple[bool, str]:
    """Return (True, '') if email looks valid, else (False, reason)."""
    if not email or not email.strip():
        return False, "empty email"
    if EMAIL_RE.match(email.strip()):
        return True, ""
    return False, f"invalid email format: {email!r}"


def validate_phone_raw(phone: str) -> tuple[bool, str]:
    """
    Basic pre-validation before phonenumbers library parsing.
    Rejects clearly non-numeric strings.
    """
    if not phone or not phone.strip():
        return False, "empty phone"
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return False, f"too few digits in phone: {phone!r}"
    return True, ""


def validate_name(name: str) -> tuple[bool, str]:
    """Names must be non-empty after stripping."""
    if not name or not name.strip():
        return False, "empty name"
    return True, ""
