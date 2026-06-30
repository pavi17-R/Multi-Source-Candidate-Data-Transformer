"""
mergers/candidate_merger.py

Merges records from multiple sources into CanonicalCandidate objects.

Merge strategy:
- Group records by normalized email (primary key).
- Records without an email are grouped by name instead.
- Within each group, apply priority ordering: Recruiter CSV > GitHub.
- Store provenance and confidence for every resolved field.

Building the structured sub-objects (Location, Skills, Experience, Links) is
delegated to field_mergers.py so this module stays focused on grouping,
priority resolution, and orchestration.
"""

from __future__ import annotations
import logging
import uuid
from collections import defaultdict

from src.models import CanonicalCandidate, ProvenanceEntry, Education
from src.normalizers import normalize_email_list
from src.mergers.field_mergers import (
    merge_location,
    merge_skills,
    merge_experience,
    merge_links,
)

logger = logging.getLogger(__name__)

# Higher index = lower priority. First source in list wins conflicts.
SOURCE_PRIORITY = ["Recruiter CSV", "GitHub"]


def merge_records(all_records: list[dict]) -> list[CanonicalCandidate]:
    """
    Merge all parsed records into canonical candidate profiles.

    Args:
        all_records: Combined list of record dicts from all parsers.

    Returns:
        List of CanonicalCandidate objects, one per unique candidate.
    """
    groups = _group_by_identity(all_records)
    candidates: list[CanonicalCandidate] = []

    for _key, group in groups.items():
        candidate = _merge_group(group)
        candidates.append(candidate)

    logger.info("Merger: produced %d canonical profiles", len(candidates))
    return candidates


def _group_by_identity(records: list[dict]) -> dict[str, list[dict]]:
    """
    Group records by identity.

    Priority:
    1. Exact email match.
    2. Exact normalized name match.

    If a record without an email has the same normalized name as a record
    that already belongs to an email group, merge it into that email group.

    This helps handle real-world GitHub profiles where email is often hidden.
    """

    groups: dict[str, list[dict]] = defaultdict(list)

    # Maps normalized name -> email group key
    name_to_email: dict[str, str] = {}

    # -------------------------------
    # PASS 1: Create all email groups
    # -------------------------------
    for record in records:

        email = record.get("email")
        name = (record.get("name") or "").strip().lower()

        if email:
            groups[email].append(record)

            if name:
                name_to_email[name] = email

    # ------------------------------------
    # PASS 2: Attach no-email records
    # ------------------------------------
    for record in records:

        if record.get("email"):
            continue

        name = (record.get("name") or "").strip().lower()

        if name and name in name_to_email:
            groups[name_to_email[name]].append(record)

        elif name:
            groups[name].append(record)

        else:
            groups[str(uuid.uuid4())].append(record)

    return groups


def _sort_by_priority(records: list[dict]) -> list[dict]:
    """Sort records so highest-priority sources come first."""
    def priority_key(r: dict) -> int:
        source = r.get("source", "")
        try:
            return SOURCE_PRIORITY.index(source)
        except ValueError:
            return len(SOURCE_PRIORITY)  # unknown sources go last

    return sorted(records, key=priority_key)


def _merge_group(records: list[dict]) -> CanonicalCandidate:
    """Build one CanonicalCandidate from a group of same-identity records."""
    sorted_records = _sort_by_priority(records)
    provenance: list[ProvenanceEntry] = []
    field_confidence: dict[str, float] = {}

    def record_provenance(field: str, source: str, method: str, confidence: float) -> None:
        provenance.append(ProvenanceEntry(field=field, source=source, method=method))
        field_confidence[field] = confidence

    def pick(field: str, extractor=None):
        """
        Return the first non-None value from sorted_records and record provenance.

        The method is labeled "priority merge" only when more than one source
        in the group actually supplied a non-empty value for this field (i.e. a
        real conflict was resolved by priority order). If only a single source
        contributed a value -- even when the candidate has records from
        multiple sources overall -- the method is "direct", since no priority
        decision was actually made.
        """
        get_value = extractor if extractor else (lambda r: r.get(field))
        contributing_sources = [
            rec for rec in sorted_records
            if get_value(rec) not in (None, "", [])
        ]
        if not contributing_sources:
            return None

        winner = contributing_sources[0]
        method = "direct" if len(contributing_sources) == 1 else "priority merge"
        record_provenance(field, winner["source"], method, winner["confidence"])
        return get_value(winner)

    # --- Scalar fields ---
    full_name = pick("full_name", lambda r: r.get("name"))
    headline = pick("headline", lambda r: r.get("bio") or r.get("title"))
    years_experience = pick("years_experience")

    # --- Location: structured city/region/country ---
    location = merge_location(sorted_records, record_provenance)

    # --- Email list: aggregate all unique emails across records ---
    all_emails_raw: list[str] = []
    for rec in sorted_records:
        if rec.get("email"):
            all_emails_raw.append(rec["email"])
    emails = normalize_email_list(all_emails_raw)
    if emails:
        record_provenance("emails", "all sources", "aggregated", max(r["confidence"] for r in sorted_records))

    # --- Phone list: aggregate all unique phones ---
    phones_seen: set[str] = set()
    phones: list[str] = []
    for rec in sorted_records:
        ph = rec.get("phone")
        if ph and ph not in phones_seen:
            phones_seen.add(ph)
            phones.append(ph)
    if phones:
        record_provenance("phones", "all sources", "aggregated", max(r["confidence"] for r in sorted_records))

    # --- Skills: union across all records, with per-skill confidence + sources ---
    skills = merge_skills(sorted_records)
    if skills:
        record_provenance("skills", "all sources", "aggregated", max(r["confidence"] for r in sorted_records))

    # --- Experience: built from recruiter data, deduplicated ---
    experience = merge_experience(sorted_records)
    if experience:
        record_provenance("experience", sorted_records[0]["source"], "aggregated", sorted_records[0]["confidence"])

    # --- Education: no source currently supplies structured education data ---
    education: list[Education] = []

    # --- Links: structured object; GitHub repos populate "github"/"other" ---
    links = merge_links(sorted_records)
    if links.github or links.linkedin or links.portfolio or links.other:
        record_provenance("links", "GitHub", "aggregated", 0.80)

    # --- Candidate ID ---
    candidate_id = str(uuid.uuid4())

    # --- Overall confidence: average of all field confidences ---
    overall_confidence = (
        sum(field_confidence.values()) / len(field_confidence)
        if field_confidence else 0.0
    )

    return CanonicalCandidate(
        candidate_id=candidate_id,
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        field_confidence=field_confidence,
        overall_confidence=round(overall_confidence, 4),
    )
