"""
models/candidate.py

Pydantic models for the canonical candidate profile and supporting types.

These models follow the assignment's canonical output schema:
- location is a structured object (city/region/country)
- links is a structured object (linkedin/github/portfolio/other)
- skills is a list of objects carrying confidence + sources
- experience entries include start/end/summary
- education is a list of structured objects
- provenance is a flat list of {field, source, method} entries
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ProvenanceEntry(BaseModel):
    """Records where a field value came from and how it was resolved."""

    field: str
    source: str
    method: str  # e.g. "direct", "priority merge", "aggregated"


class FieldValue(BaseModel):
    """A field value paired with its confidence score."""

    value: Any
    confidence: float


class Location(BaseModel):
    """Structured location broken into city / region / country."""

    city: str | None = None
    region: str | None = None
    country: str | None = None


class Links(BaseModel):
    """Structured external profile links."""

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    """A single skill with its confidence and contributing sources."""

    name: str
    confidence: float
    sources: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    """A single work experience entry."""

    company: str | None = None
    title: str | None = None
    start: str | None = None  # "YYYY-MM" when available
    end: str | None = None    # "YYYY-MM" when available, "Present" if ongoing
    summary: str | None = None


class Education(BaseModel):
    """A single education entry."""

    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    end_year: int | None = None


class CanonicalCandidate(BaseModel):
    """
    The single canonical representation of a candidate.

    This model is the immutable internal object. Output projection
    is handled separately by the OutputProjector.
    """

    candidate_id: str
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    # Metadata
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = 0.0

