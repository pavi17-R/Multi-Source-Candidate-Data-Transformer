"""
parsers/csv_parser.py

Reads the recruiter CSV and produces a list of normalized intermediate records.
Supports multiple real-world column names such as:

- name
- full_name
- candidate_name
- candidate name

and

- email
- candidate_email
- candidate email
- email_address
- email address
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.normalizers import normalize_phone, normalize_email
from src.validators import validate_name

logger = logging.getLogger(__name__)

SOURCE_NAME = "Recruiter CSV"
SOURCE_CONFIDENCE = 0.95

# Supported column aliases
NAME_COLUMNS = [
    "name",
    "full_name",
    "candidate_name",
    "candidate name",
]

EMAIL_COLUMNS = [
    "email",
    "candidate_email",
    "candidate email",
    "email_address",
    "email address",
]


def parse_csv(filepath: str | Path) -> list[dict]:
    """
    Parse recruiter CSV.
    """

    path = Path(filepath)

    if not path.exists():
        logger.error("CSV file not found: %s", path)
        return []

    records = []

    try:

        with path.open(newline="", encoding="utf-8") as fh:

            reader = csv.DictReader(fh)

            if reader.fieldnames is None:
                logger.error("CSV file is empty.")
                return []

            actual_columns = {
                c.strip().lower()
                for c in reader.fieldnames
            }

            has_name = any(col in actual_columns for col in NAME_COLUMNS)
            has_email = any(col in actual_columns for col in EMAIL_COLUMNS)

            if not has_name:
                logger.warning("No supported name column found.")

            if not has_email:
                logger.warning("No supported email column found.")

            for line_num, raw_row in enumerate(reader, start=2):

                row = {
                    k.strip().lower(): (v.strip() if v else "")
                    for k, v in raw_row.items()
                }

                record = _parse_row(row, line_num)

                if record:
                    records.append(record)

    except (OSError, csv.Error) as exc:
        logger.error("Failed to read CSV: %s", exc)

    logger.info(
        "CSV parser: %d valid records from %s",
        len(records),
        path,
    )

    return records


def _get_first(row: dict[str, str], columns: list[str]) -> str:
    """
    Return the first matching column value.
    """

    for col in columns:
        value = row.get(col)

        if value:
            return value

    return ""


def _parse_row(row: dict[str, str], line_num: int):

    raw_name = _get_first(row, NAME_COLUMNS)
    raw_email = _get_first(row, EMAIL_COLUMNS)

    # Validate name
    name = None

    valid_name, reason = validate_name(raw_name)

    if valid_name:
        name = raw_name.strip()

    else:
        logger.debug("Line %d: %s", line_num, reason)

    # Normalize email
    email = normalize_email(raw_email) if raw_email else None

    # Need at least one identifier
    if name is None and email is None:
        logger.warning(
            "Line %d: skipping row with no name and no valid email",
            line_num,
        )
        return None

    # Phone
    raw_phone = row.get("phone", "")

    phone = normalize_phone(raw_phone) if raw_phone else None

    if raw_phone and phone is None:
        logger.warning(
            "Line %d: invalid phone %r",
            line_num,
            raw_phone,
        )

    return {
        "source": SOURCE_NAME,
        "confidence": SOURCE_CONFIDENCE,
        "name": name,
        "email": email,
        "phone": phone,
        "current_company": row.get("current_company") or None,
        "title": row.get("title") or None,
    }