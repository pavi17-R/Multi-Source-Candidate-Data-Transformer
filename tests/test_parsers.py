"""
tests/test_parsers.py

Unit tests for CSV and GitHub parsers, focusing on graceful handling
of malformed/missing/edge-case input.
"""

import json
import pytest
from src.parsers.csv_parser import parse_csv
from src.parsers.github_parser import parse_github


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

class TestCsvParser:
    def test_missing_file_returns_empty_list(self, tmp_path):
        result = parse_csv(tmp_path / "does_not_exist.csv")
        assert result == []

    def test_empty_csv_returns_empty_list(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        result = parse_csv(path)
        assert result == []

    def test_valid_row_parsed(self, tmp_path):
        path = tmp_path / "valid.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            "Alice,alice@example.com,+1-415-555-0101,Acme,Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["email"] == "alice@example.com"
        assert result[0]["phone"] == "+14155550101"

    def test_missing_phone_handled_gracefully(self, tmp_path):
        path = tmp_path / "no_phone.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            "Bob,bob@example.com,,Acme,Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert len(result) == 1
        assert result[0]["phone"] is None

    def test_invalid_phone_handled_gracefully(self, tmp_path):
        path = tmp_path / "bad_phone.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            "Carol,carol@example.com,notaphone,Acme,Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert len(result) == 1
        assert result[0]["phone"] is None

    def test_invalid_email_treated_as_none(self, tmp_path):
        path = tmp_path / "bad_email.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            "Dave,not-an-email,,Acme,Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert len(result) == 1
        assert result[0]["email"] is None
        assert result[0]["name"] == "Dave"

    def test_row_with_no_name_and_no_email_skipped(self, tmp_path):
        path = tmp_path / "blank_row.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            ",,,Acme,Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert result == []

    def test_duplicate_emails_both_parsed(self, tmp_path):
        """Parser itself doesn't dedupe; merging is responsible for that."""
        path = tmp_path / "dupes.csv"
        path.write_text(
            "name,email,phone,current_company,title\n"
            "Alice,alice@example.com,,Acme,Engineer\n"
            "Alice J,alice@example.com,,Acme,Senior Engineer\n",
            encoding="utf-8",
        )
        result = parse_csv(path)
        assert len(result) == 2

    def test_malformed_csv_missing_columns(self, tmp_path):
        """CSV missing expected columns should not crash; just warns."""
        path = tmp_path / "malformed.csv"
        path.write_text("foo,bar\n1,2\n", encoding="utf-8")
        result = parse_csv(path)
        # No usable name/email -> skipped, but no crash
        assert result == []


# ---------------------------------------------------------------------------
# GitHub parser
# ---------------------------------------------------------------------------

class TestGithubParser:
    def test_missing_file_returns_empty_list(self, tmp_path):
        result = parse_github(tmp_path / "missing.json")
        assert result == []

    def test_empty_json_array_returns_empty_list(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("[]", encoding="utf-8")
        result = parse_github(path)
        assert result == []

    def test_malformed_json_returns_empty_list(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        result = parse_github(path)
        assert result == []

    def test_valid_item_parsed(self, tmp_path):
        path = tmp_path / "valid.json"
        path.write_text(json.dumps([{
            "name": "Alice",
            "bio": "Engineer with 5 years experience.",
            "email": "alice@example.com",
            "location": "SF",
            "repositories": [{"name": "repo1", "language": "Python"}],
            "languages": ["Python"],
        }]), encoding="utf-8")
        result = parse_github(path)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["years_experience"] == 5.0
        assert "Python" in result[0]["skills"]

    def test_item_with_no_name_or_email_skipped(self, tmp_path):
        path = tmp_path / "blank.json"
        path.write_text(json.dumps([{
            "name": "",
            "bio": "",
            "email": "",
            "location": "",
            "repositories": [],
            "languages": [],
        }]), encoding="utf-8")
        result = parse_github(path)
        assert result == []

    def test_single_object_format_supported(self, tmp_path):
        """Some APIs return a single object instead of a list."""
        path = tmp_path / "single.json"
        path.write_text(json.dumps({
            "name": "Bob",
            "email": "bob@example.com",
            "bio": "",
            "location": "",
            "repositories": [],
            "languages": [],
        }), encoding="utf-8")
        result = parse_github(path)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"

    def test_non_dict_items_skipped(self, tmp_path):
        path = tmp_path / "mixed.json"
        path.write_text(json.dumps(["not a dict", {"name": "Carol", "email": "carol@example.com"}]), encoding="utf-8")
        result = parse_github(path)
        assert len(result) == 1
        assert result[0]["name"] == "Carol"
