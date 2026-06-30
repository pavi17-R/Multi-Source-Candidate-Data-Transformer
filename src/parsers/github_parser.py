"""
parsers/github_parser.py

Parses GitHub-sourced candidate data into normalized intermediate
records used by the rest of the pipeline (merger, output projector,
etc).

This parser is INPUT-AGNOSTIC: it accepts data from either of two
sources, both reduced to the exact same intermediate dict shape:

  1. A static github.json file on disk (legacy / backward-compatible
     path) - a JSON array (or single object) of user records.

  2. A live dict (or list of dicts) already fetched from the GitHub
     REST API by src/fetchers/github_fetcher.py.

In both cases the item shape consumed by `_parse_item()` is identical:

    {
        "name": str | None,
        "bio": str | None,
        "email": str | None,
        "location": str | None,
        "repositories": [{"name", "description", "language"}, ...],
        "languages": [str, ...]
    }

Source confidence: 0.80 (self-reported profile data)
"""

from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from src.normalizers import normalize_email, normalize_skills

logger = logging.getLogger(__name__)

SOURCE_NAME = "GitHub"
SOURCE_CONFIDENCE = 0.80

# Simple heuristic: look for "N year" patterns in bio text
YEARS_RE = re.compile(r"(\d+)\s+year", re.IGNORECASE)


def parse_github(source: str | Path | dict | list) -> list[dict]:
    """
    Parse GitHub candidate data into the pipeline's intermediate record
    format. Accepts EITHER:

      - a path (str or Path) to a github.json-style file on disk, OR
      - already-loaded data (dict for a single profile, or list of
        dicts for multiple profiles) such as the output of
        src/fetchers/github_fetcher.fetch_github_profile_as_dict().

    This dual behaviour means callers (e.g. main.py) never need to
    know or care whether the underlying data came from a JSON fixture
    file or a live GitHub REST API call - they just pass whatever they
    have and get the same normalized records back.

    Returns:
        List of record dicts with GitHub-sourced candidate data.
        Each dict has:
        {
            "source": SOURCE_NAME,
            "confidence": SOURCE_CONFIDENCE,
            "name": str | None,
            "email": str | None,
            "location": str | None,
            "bio": str | None,
            "years_experience": float | None,
            "skills": list[str],
            "repo_names": list[str],
        }
    """
    data = _load_data(source)

    if data is None:
        return []

    if not isinstance(data, list):
        # Support single-object format too (one fetched profile, or one
        # JSON object instead of an array).
        data = [data] if isinstance(data, dict) else []

    records: list[dict] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("GitHub item %d is not a dict, skipping", idx)
            continue
        record = _parse_item(item)
        if record:
            records.append(record)

    logger.info("GitHub parser: %d valid records", len(records))
    return records


def _load_data(source: str | Path | dict | list):
    """
    Normalize the various accepted input types into raw Python data
    (dict / list), loading from disk only when given a path-like value.
    """
    # Already-loaded data (e.g. from github_fetcher) - pass straight through.
    if isinstance(source, (dict, list)):
        return source

    # Otherwise treat it as a file path (str or Path) - legacy behaviour.
    path = Path(source)
    if not path.exists():
        logger.error("GitHub JSON file not found: %s", path)
        return None

    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read GitHub JSON: %s", exc)
        return None


def _parse_item(item: dict) -> dict | None:
    """Parse one GitHub user object."""
    raw_email = item.get("email", "")
    email = normalize_email(raw_email) if raw_email else None

    raw_name = item.get("name", "")
    name = raw_name.strip() if raw_name and raw_name.strip() else None

    # Must have at least an email or name to be usable
    if email is None and name is None:
        logger.debug("GitHub item has no name or email, skipping")
        return None

    bio = item.get("bio", "") or None
    years_experience = _extract_years(bio) if bio else None

    location = item.get("location", "") or None

    # Collect languages from top-level field + repository languages
    raw_languages: list[str] = list(item.get("languages") or [])
    for repo in item.get("repositories") or []:
        lang = repo.get("language")
        if lang:
            raw_languages.append(lang)

    skills = normalize_skills(raw_languages)

    repo_names = [r["name"] for r in (item.get("repositories") or []) if r.get("name")]

    return {
        "source": SOURCE_NAME,
        "confidence": SOURCE_CONFIDENCE,
        "name": name,
        "email": email,
        "location": location,
        "bio": bio,
        "years_experience": years_experience,
        "skills": skills,
        "repo_names": repo_names,
    }


def _extract_years(bio: str) -> float | None:
    """
    Extract years of experience from bio text using a simple regex heuristic.
    Returns None if nothing is found.
    """
    match = YEARS_RE.search(bio)
    if match:
        return float(match.group(1))
    return None
