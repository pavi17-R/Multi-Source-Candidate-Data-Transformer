"""
tests/test_normalizers.py

Unit tests for phone, email, and skill normalization.
"""

import pytest
from src.normalizers.phone_normalizer import normalize_phone
from src.normalizers.email_normalizer import normalize_email, normalize_email_list
from src.normalizers.skill_normalizer import normalize_skills, canonicalize_skill


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

class TestPhoneNormalizer:
    def test_us_with_dashes(self):
        assert normalize_phone("+1-415-555-0101") == "+14155550101"

    def test_us_with_spaces(self):
        assert normalize_phone("415 555 0102") == "+14155550102"

    def test_uk_number(self):
        result = normalize_phone("+44 20 7946 0103")
        assert result is not None
        assert result.startswith("+44")

    def test_empty_returns_none(self):
        assert normalize_phone("") is None
        assert normalize_phone("   ") is None

    def test_invalid_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_too_short_returns_none(self):
        assert normalize_phone("123") is None

    def test_already_e164(self):
        result = normalize_phone("+14155550101")
        assert result == "+14155550101"


# ---------------------------------------------------------------------------
# Email normalization
# ---------------------------------------------------------------------------

class TestEmailNormalizer:
    def test_lowercase(self):
        assert normalize_email("Alice@EXAMPLE.COM") == "alice@example.com"

    def test_strips_whitespace(self):
        assert normalize_email("  bob@example.com  ") == "bob@example.com"

    def test_invalid_returns_none(self):
        assert normalize_email("not-an-email") is None

    def test_empty_returns_none(self):
        assert normalize_email("") is None
        assert normalize_email(None) is None

    def test_no_at_symbol(self):
        assert normalize_email("userexample.com") is None

    def test_list_deduplication(self):
        result = normalize_email_list([
            "Alice@Example.com",
            "alice@example.com",
            "BOB@example.com",
            "bob@example.com",
        ])
        assert result == ["alice@example.com", "bob@example.com"]

    def test_list_filters_invalid(self):
        result = normalize_email_list(["valid@email.com", "not-valid", ""])
        assert result == ["valid@email.com"]


# ---------------------------------------------------------------------------
# Skill normalization
# ---------------------------------------------------------------------------

class TestSkillNormalizer:
    def test_synonym_ml(self):
        assert canonicalize_skill("ML") == "Machine Learning"
        assert canonicalize_skill("machine learning") == "Machine Learning"
        assert canonicalize_skill("machine-learning") == "Machine Learning"

    def test_synonym_js(self):
        assert canonicalize_skill("js") == "JavaScript"
        assert canonicalize_skill("javascript") == "JavaScript"

    def test_unknown_skill_title_case(self):
        assert canonicalize_skill("kubernetes") == "Kubernetes"

    def test_deduplication(self):
        result = normalize_skills(["Python", "python", "PYTHON"])
        assert result == ["Python"]

    def test_mixed_synonyms_deduplication(self):
        result = normalize_skills(["ML", "Machine Learning", "machine-learning"])
        assert result == ["Machine Learning"]

    def test_empty_list(self):
        assert normalize_skills([]) == []

    def test_empty_strings_filtered(self):
        assert normalize_skills(["", "  ", "Python"]) == ["Python"]

    def test_sorted_output(self):
        result = normalize_skills(["SQL", "Python", "Go"])
        assert result == sorted(result)

    def test_union_across_sources(self):
        result = normalize_skills(["Python", "SQL", "Python", "JavaScript"])
        assert len(result) == 3
        assert "Python" in result
        assert "SQL" in result
        assert "JavaScript" in result
