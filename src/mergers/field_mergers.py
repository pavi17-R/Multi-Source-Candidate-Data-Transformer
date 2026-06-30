"""
mergers/field_mergers.py

Builds the structured sub-objects required by the canonical schema
(Location, Skill list, Experience list, Links) from a group of same-identity
record dicts. Split out from candidate_merger.py to keep each file focused:
candidate_merger.py owns grouping/priority/orchestration, this module owns
shaping individual structured fields.

Parsers stay source-agnostic and flat; all schema shaping happens here.
"""

from __future__ import annotations
from typing import Callable

from src.models import Location, Links, Skill, Experience
from src.normalizers import normalize_skills


def merge_location(sorted_records: list[dict], record_provenance: Callable) -> Location:
    """
    Build a structured Location from the first record that has location data.

    Current sources (Recruiter CSV, GitHub) only supply a single free-text
    location string (e.g. "San Francisco, CA"). We split on commas into
    city / region, leaving country null since none of the sources specify it.
    No information is invented beyond this straightforward split.
    """
    for rec in sorted_records:
        raw_location = rec.get("location")
        if raw_location:
            parts = [p.strip() for p in raw_location.split(",") if p.strip()]
            city = parts[0] if len(parts) >= 1 else None
            region = parts[1] if len(parts) >= 2 else None
            country = parts[2] if len(parts) >= 3 else None
            record_provenance("location", rec["source"], "direct", rec["confidence"])
            return Location(city=city, region=region, country=country)
    return Location()


def merge_skills(sorted_records: list[dict]) -> list[Skill]:
    """
    Union skills across all records into Skill objects.

    Each skill tracks every source that mentioned it and uses the highest
    confidence among those sources, satisfying the requirement that every
    skill carry its own confidence and source information.
    """
    # name -> {"sources": list[str], "confidence": float}
    skill_map: dict[str, dict] = {}

    for rec in sorted_records:
        raw_skills = rec.get("skills") or []
        canonical_names = normalize_skills(raw_skills)
        for name in canonical_names:
            entry = skill_map.setdefault(name, {"sources": [], "confidence": 0.0})
            if rec["source"] not in entry["sources"]:
                entry["sources"].append(rec["source"])
            entry["confidence"] = max(entry["confidence"], rec["confidence"])

    skills = [
        Skill(name=name, confidence=round(data["confidence"], 4), sources=data["sources"])
        for name, data in skill_map.items()
    ]
    return sorted(skills, key=lambda s: s.name)


def merge_experience(sorted_records: list[dict]) -> list[Experience]:
    """
    Build Experience entries from recruiter data (current_company/title).

    Start/end dates and a summary are not provided by the current sources,
    so they remain null rather than being invented.
    """
    experience: list[Experience] = []
    seen_experience: set[tuple] = set()
    for rec in sorted_records:
        if rec.get("current_company") or rec.get("title"):
            key = (rec.get("title"), rec.get("current_company"), rec["source"])
            if key not in seen_experience:
                seen_experience.add(key)
                experience.append(Experience(
                    company=rec.get("current_company"),
                    title=rec.get("title"),
                    start=None,
                    end=None,
                    summary=None,
                ))
    return experience


def merge_links(sorted_records: list[dict]) -> Links:
    """
    Build a structured Links object.

    GitHub repository URLs are surfaced under "github" (the profile's primary
    GitHub repo, if any) and any additional repos go into "other". LinkedIn
    and portfolio links are not provided by current sources, so they stay null.
    """
    other: list[str] = []
    github_link: str | None = None

    for rec in sorted_records:
        for repo in rec.get("repo_names") or []:
            link = f"https://github.com/{repo}"
            if github_link is None:
                github_link = link
            elif link not in other:
                other.append(link)

    return Links(linkedin=None, github=github_link, portfolio=None, other=other)
