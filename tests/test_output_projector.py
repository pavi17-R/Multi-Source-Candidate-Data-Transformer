"""
tests/test_output_projector.py

Unit tests for the output projection (configurable output) logic.
"""

import pytest
from src.models import (
    CanonicalCandidate,
    OutputConfig,
    ProvenanceEntry,
    Experience,
    Location,
    Links,
    Skill,
    Education,
)
from src.utils.output_projector import project


def make_candidate() -> CanonicalCandidate:
    return CanonicalCandidate(
        candidate_id="abc-123",
        full_name="Alice Johnson",
        emails=["alice@example.com"],
        phones=["+14155550101"],
        location=Location(city="San Francisco", region="CA", country=None),
        links=Links(linkedin=None, github="https://github.com/cool-project", portfolio=None, other=[]),
        headline="Senior Software Engineer",
        years_experience=6.0,
        skills=[Skill(name="Python", confidence=0.95, sources=["Recruiter CSV"])],
        experience=[],
        education=[],
        provenance=[
            ProvenanceEntry(field="full_name", source="Recruiter CSV", method="priority merge"),
        ],
        field_confidence={"full_name": 0.95},
        overall_confidence=0.875,
    )


class TestOutputProjector:
    def test_default_config_includes_all_fields(self):
        candidate = make_candidate()
        config = OutputConfig()
        result = project(candidate, config)
        assert result["full_name"] == "Alice Johnson"
        assert result["emails"] == ["alice@example.com"]

    def test_field_selection(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name", "emails"])
        result = project(candidate, config)
        assert set(result.keys()) == {"full_name", "emails"}

    def test_rename_field(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name"], rename={"full_name": "candidate_name"})
        result = project(candidate, config)
        assert "candidate_name" in result
        assert "full_name" not in result
        assert result["candidate_name"] == "Alice Johnson"

    def test_include_confidence_true(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name", "overall_confidence"], include_confidence=True)
        result = project(candidate, config)
        assert result["overall_confidence"] == 0.875

    def test_include_confidence_false(self):
        candidate = make_candidate()
        config = OutputConfig(
            fields=["full_name", "overall_confidence"],
            include_confidence=False,
            on_missing="null",
        )
        result = project(candidate, config)
        assert result["overall_confidence"] is None

    def test_include_provenance_true(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name", "provenance"], include_provenance=True)
        result = project(candidate, config)
        assert "provenance" in result
        assert isinstance(result["provenance"], list)
        assert result["provenance"][0]["field"] == "full_name"
        assert result["provenance"][0]["source"] == "Recruiter CSV"

    def test_include_provenance_false(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name", "provenance"], include_provenance=False)
        result = project(candidate, config)
        assert "provenance" not in result

    def test_missing_field_null_mode(self):
        candidate = make_candidate()
        candidate.headline = None
        config = OutputConfig(fields=["headline"], on_missing="null")
        result = project(candidate, config)
        assert result["headline"] is None

    def test_missing_field_omit_mode(self):
        candidate = make_candidate()
        candidate.headline = None
        config = OutputConfig(fields=["headline"], on_missing="omit")
        result = project(candidate, config)
        assert "headline" not in result

    def test_canonical_model_unchanged_after_projection(self):
        """Projection must never mutate the canonical candidate."""
        candidate = make_candidate()
        config = OutputConfig(fields=["full_name"], rename={"full_name": "candidate_name"})
        project(candidate, config)
        assert candidate.full_name == "Alice Johnson"  # original field name intact

    def test_empty_experience_list_stays_empty_list(self):
        """List-typed schema fields keep [] rather than becoming null when empty,
        per the assignment's 'use null or empty list, never omit' requirement."""
        candidate = make_candidate()
        config = OutputConfig(fields=["experience"], on_missing="null")
        result = project(candidate, config)
        assert result["experience"] == []

    def test_empty_list_field_omitted_under_omit_mode(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["experience"], on_missing="omit")
        result = project(candidate, config)
        assert "experience" not in result

    def test_non_empty_experience_list_serialized(self):
        candidate = make_candidate()
        candidate.experience = [Experience(title="Engineer", company="Acme", start=None, end=None, summary=None)]
        config = OutputConfig(fields=["experience"])
        result = project(candidate, config)
        assert result["experience"] == [{
            "title": "Engineer", "company": "Acme", "start": None, "end": None, "summary": None,
        }]

    def test_empty_fields_list_produces_empty_dict(self):
        candidate = make_candidate()
        config = OutputConfig(fields=[])
        result = project(candidate, config)
        assert result == {}

    def test_location_serialized_as_object(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["location"])
        result = project(candidate, config)
        assert result["location"] == {"city": "San Francisco", "region": "CA", "country": None}

    def test_location_default_object_present_when_empty(self):
        """Even with no location data, the schema requires a location object, not null."""
        candidate = make_candidate()
        candidate.location = Location()
        config = OutputConfig(fields=["location"], on_missing="null")
        result = project(candidate, config)
        assert result["location"] == {"city": None, "region": None, "country": None}

    def test_links_serialized_as_object(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["links"])
        result = project(candidate, config)
        assert result["links"]["github"] == "https://github.com/cool-project"
        assert result["links"]["other"] == []

    def test_skills_serialized_as_list_of_objects(self):
        candidate = make_candidate()
        config = OutputConfig(fields=["skills"])
        result = project(candidate, config)
        assert result["skills"] == [{"name": "Python", "confidence": 0.95, "sources": ["Recruiter CSV"]}]

    def test_education_empty_list_stays_empty_list(self):
        """Per assignment requirement #7: education must be [] when unavailable,
        never null and never omitted from the schema."""
        candidate = make_candidate()
        candidate.education = []
        config = OutputConfig(fields=["education"], on_missing="null")
        result = project(candidate, config)
        assert "education" in result
        assert result["education"] == []

    def test_education_list_of_objects_when_present(self):
        candidate = make_candidate()
        candidate.education = [Education(institution="MIT", degree="BS", field="CS", end_year=2020)]
        config = OutputConfig(fields=["education"])
        result = project(candidate, config)
        assert result["education"] == [{
            "institution": "MIT", "degree": "BS", "field": "CS", "end_year": 2020,
        }]
