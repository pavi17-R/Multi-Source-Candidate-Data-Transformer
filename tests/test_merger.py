"""
tests/test_merger.py

Unit tests for the candidate merge logic.
Tests priority resolution, aggregation, provenance, and confidence.
"""

import pytest
from src.mergers.candidate_merger import merge_records, _sort_by_priority


# ---------------------------------------------------------------------------
# Priority sorting
# ---------------------------------------------------------------------------

class TestSourcePriority:
    def test_csv_before_github(self):
        records = [
            {"source": "GitHub", "confidence": 0.80},
            {"source": "Recruiter CSV", "confidence": 0.95},
        ]
        sorted_recs = _sort_by_priority(records)
        assert sorted_recs[0]["source"] == "Recruiter CSV"

    def test_unknown_source_goes_last(self):
        records = [
            {"source": "Unknown Source"},
            {"source": "Recruiter CSV", "confidence": 0.95},
        ]
        sorted_recs = _sort_by_priority(records)
        assert sorted_recs[0]["source"] == "Recruiter CSV"
        assert sorted_recs[-1]["source"] == "Unknown Source"


# ---------------------------------------------------------------------------
# Merge behavior
# ---------------------------------------------------------------------------

def make_csv_record(**kwargs) -> dict:
    base = {
        "source": "Recruiter CSV",
        "confidence": 0.95,
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+14155550101",
        "current_company": "Acme Corp",
        "title": "Senior Engineer",
        "skills": [],
    }
    base.update(kwargs)
    return base


def make_github_record(**kwargs) -> dict:
    base = {
        "source": "GitHub",
        "confidence": 0.80,
        "name": "Alice J.",
        "email": "alice@example.com",
        "location": "San Francisco, CA",
        "bio": "Engineer with 6 years experience.",
        "years_experience": 6.0,
        "skills": ["Python", "Go"],
        "repo_names": ["cool-project"],
    }
    base.update(kwargs)
    return base


def find_provenance(candidate, field_name):
    """Helper to find a ProvenanceEntry by field name in the provenance list."""
    for entry in candidate.provenance:
        if entry.field == field_name:
            return entry
    return None


class TestMergeGroup:
    def test_single_csv_record(self):
        records = [make_csv_record()]
        candidates = merge_records(records)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.full_name == "Alice Johnson"
        assert "alice@example.com" in c.emails

    def test_csv_name_wins_over_github(self):
        """Recruiter CSV has higher priority; name should come from CSV."""
        records = [make_csv_record(), make_github_record()]
        candidates = merge_records(records)
        assert len(candidates) == 1
        assert candidates[0].full_name == "Alice Johnson"

    def test_github_fills_location(self):
        """Location not in CSV; should be filled from GitHub as structured object."""
        records = [make_csv_record(), make_github_record()]
        candidates = merge_records(records)
        location = candidates[0].location
        assert location.city == "San Francisco"
        assert location.region == "CA"

    def test_location_defaults_to_empty_object(self):
        """When no source supplies location, Location object is present with all-null fields."""
        records = [make_csv_record(current_company=None, title=None)]
        c = merge_records(records)[0]
        assert c.location.city is None
        assert c.location.region is None
        assert c.location.country is None

    def test_skills_aggregated(self):
        """Skills are unioned across sources as Skill objects."""
        records = [
            make_csv_record(skills=["SQL"]),
            make_github_record(skills=["Python", "Go"]),
        ]
        candidates = merge_records(records)
        skill_names = [s.name for s in candidates[0].skills]
        assert "Python" in skill_names
        assert "Go" in skill_names
        assert "SQL" in skill_names

    def test_skill_has_confidence_and_sources(self):
        records = [make_csv_record(skills=["Python"])]
        c = merge_records(records)[0]
        python_skill = next(s for s in c.skills if s.name == "Python")
        assert python_skill.confidence == 0.95
        assert "Recruiter CSV" in python_skill.sources

    def test_skill_sources_combine_across_records(self):
        """A skill mentioned by both sources should list both sources."""
        records = [
            make_csv_record(skills=["Python"]),
            make_github_record(skills=["Python"]),
        ]
        c = merge_records(records)[0]
        python_skill = next(s for s in c.skills if s.name == "Python")
        assert set(python_skill.sources) == {"Recruiter CSV", "GitHub"}
        # Confidence should be the max across contributing sources
        assert python_skill.confidence == 0.95

    def test_emails_deduplicated(self):
        """Same email from two sources should appear only once."""
        records = [make_csv_record(), make_github_record()]
        candidates = merge_records(records)
        assert candidates[0].emails.count("alice@example.com") == 1

    def test_years_experience_from_github(self):
        records = [make_csv_record(), make_github_record(years_experience=6.0)]
        candidates = merge_records(records)
        assert candidates[0].years_experience == 6.0

    def test_provenance_full_name_source(self):
        records = [make_csv_record(), make_github_record()]
        c = merge_records(records)[0]
        entry = find_provenance(c, "full_name")
        assert entry is not None
        assert entry.source == "Recruiter CSV"

    def test_provenance_is_a_list(self):
        """Provenance must be a flat list of entries, each with field/source/method."""
        records = [make_csv_record()]
        c = merge_records(records)[0]
        assert isinstance(c.provenance, list)
        for entry in c.provenance:
            assert entry.field
            assert entry.source
            assert entry.method

    def test_overall_confidence_is_average(self):
        records = [make_csv_record()]
        c = merge_records(records)[0]
        assert 0.0 < c.overall_confidence <= 1.0

    def test_two_different_candidates(self):
        """Records with different emails produce separate canonical profiles."""
        records = [
            make_csv_record(email="alice@example.com"),
            make_csv_record(name="Bob", email="bob@example.com"),
        ]
        candidates = merge_records(records)
        assert len(candidates) == 2

    def test_no_records_returns_empty(self):
        assert merge_records([]) == []

    def test_phone_preserved(self):
        records = [make_csv_record(phone="+14155550101")]
        c = merge_records(records)[0]
        assert "+14155550101" in c.phones

    def test_links_from_github_repos(self):
        """GitHub repos populate the structured Links object's github/other fields."""
        records = [make_github_record(repo_names=["my-repo"])]
        c = merge_records(records)[0]
        assert c.links.github == "https://github.com/my-repo"

    def test_links_multiple_repos_first_is_github_rest_is_other(self):
        records = [make_github_record(repo_names=["repo-a", "repo-b"])]
        c = merge_records(records)[0]
        assert c.links.github == "https://github.com/repo-a"
        assert "https://github.com/repo-b" in c.links.other

    def test_links_default_object_when_no_repos(self):
        records = [make_csv_record(current_company=None, title=None)]
        c = merge_records(records)[0]
        assert c.links.github is None
        assert c.links.linkedin is None
        assert c.links.portfolio is None
        assert c.links.other == []

    def test_education_defaults_to_empty_list(self):
        """No source currently supplies education; should be an empty list, not omitted."""
        records = [make_csv_record()]
        c = merge_records(records)[0]
        assert c.education == []

    def test_experience_entries_have_structured_fields(self):
        records = [make_csv_record(title="Engineer", current_company="Acme")]
        c = merge_records(records)[0]
        assert len(c.experience) == 1
        exp = c.experience[0]
        assert exp.title == "Engineer"
        assert exp.company == "Acme"
        assert exp.start is None
        assert exp.end is None

    def test_links_provenance_recorded_with_single_repo(self):
        """
        Regression test: a candidate with exactly one GitHub repo populates
        links.github but leaves links.other empty. Provenance must still be
        recorded for the links field in this case (every populated field
        needs a provenance entry, per the assignment spec).
        """
        records = [make_github_record(repo_names=["solo-repo"])]
        c = merge_records(records)[0]
        assert c.links.github == "https://github.com/solo-repo"
        assert c.links.other == []
        field_names = {p.field for p in c.provenance}
        assert "links" in field_names

    def test_links_no_provenance_when_truly_empty(self):
        records = [make_csv_record(current_company=None, title=None)]
        c = merge_records(records)[0]
        field_names = {p.field for p in c.provenance}
        assert "links" not in field_names

    def test_method_is_direct_when_only_one_source_has_the_field(self):
        """
        Regression test: years_experience is only ever supplied by GitHub.
        Even though this candidate also has a Recruiter CSV record (so the
        group has 2 records), there's no actual conflict for this field --
        only GitHub contributed a value. The method must be 'direct', not
        'priority merge', because no priority decision was made.
        """
        records = [make_csv_record(), make_github_record(years_experience=6.0)]
        c = merge_records(records)[0]
        entry = find_provenance(c, "years_experience")
        assert entry is not None
        assert entry.method == "direct"
        assert entry.source == "GitHub"

    def test_method_is_priority_merge_when_both_sources_contribute(self):
        """Full_name is supplied by both CSV and GitHub -- a real conflict
        exists and CSV wins by priority, so the method should say so."""
        records = [make_csv_record(), make_github_record()]
        c = merge_records(records)[0]
        entry = find_provenance(c, "full_name")
        assert entry is not None
        assert entry.method == "priority merge"
        assert entry.source == "Recruiter CSV"
