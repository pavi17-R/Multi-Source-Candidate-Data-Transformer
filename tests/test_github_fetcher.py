"""
tests/test_github_fetcher.py

Unit tests for src/fetchers/github_fetcher.py — username extraction,
GitHub REST API response mapping, and error handling. Uses the
`responses` library to mock HTTP calls so tests run fully offline.
"""

import pytest
import responses

from src.fetchers.github_fetcher import (
    extract_username,
    fetch_github_profile_as_dict,
    fetch_github_profiles_as_list,
    GithubFetchError,
)
from src.parsers.github_parser import parse_github


# ---------------------------------------------------------------------------
# extract_username
# ---------------------------------------------------------------------------

class TestExtractUsername:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://github.com/octocat", "octocat"),
            ("http://github.com/octocat/", "octocat"),
            ("github.com/octocat", "octocat"),
            ("www.github.com/octocat", "octocat"),
            ("https://www.github.com/octocat?tab=repositories", "octocat"),
            ("https://github.com/Octo-Cat123", "Octo-Cat123"),
        ],
    )
    def test_valid_urls(self, url, expected):
        assert extract_username(url) == expected

    def test_empty_url_raises(self):
        with pytest.raises(ValueError):
            extract_username("")

    def test_non_github_url_raises(self):
        with pytest.raises(ValueError):
            extract_username("https://gitlab.com/octocat")

    def test_reserved_path_raises(self):
        with pytest.raises(ValueError):
            extract_username("https://github.com/orgs")


# ---------------------------------------------------------------------------
# fetch_github_profile_as_dict (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchGithubProfileAsDict:
    @responses.activate
    def test_full_profile_mapped_correctly(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/octocat",
            json={
                "login": "octocat",
                "name": "The Octocat",
                "bio": "GitHub mascot with 10 years experience",
                "email": "octocat@github.com",
                "location": "San Francisco",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/octocat/repos",
            json=[
                {"name": "Hello-World", "description": "My first repo",
                 "language": "Python", "fork": False},
                {"name": "forked-repo", "description": "a fork",
                 "language": "JavaScript", "fork": True},
                {"name": "Spoon-Knife", "description": None,
                 "language": "Ruby", "fork": False},
            ],
            status=200,
        )

        record = fetch_github_profile_as_dict("https://github.com/octocat")

        assert record["name"] == "The Octocat"
        assert record["email"] == "octocat@github.com"
        assert record["location"] == "San Francisco"
        # forked repo must be excluded
        repo_names = [r["name"] for r in record["repositories"]]
        assert "Hello-World" in repo_names
        assert "Spoon-Knife" in repo_names
        assert "forked-repo" not in repo_names
        assert record["languages"] == ["Python", "Ruby"]

    @responses.activate
    def test_falls_back_to_login_when_no_name(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/anonuser",
            json={"login": "anonuser", "name": None, "bio": None,
                  "email": None, "location": None},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/anonuser/repos",
            json=[],
            status=200,
        )
        record = fetch_github_profile_as_dict("https://github.com/anonuser")
        assert record["name"] == "anonuser"
        assert record["email"] is None
        assert record["repositories"] == []
        assert record["languages"] == []

    @responses.activate
    def test_404_raises_githubfetcherror(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/doesnotexist",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(GithubFetchError):
            fetch_github_profile_as_dict("https://github.com/doesnotexist")

    @responses.activate
    def test_rate_limit_raises_githubfetcherror(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/octocat",
            json={"message": "API rate limit exceeded"},
            status=403,
        )
        with pytest.raises(GithubFetchError):
            fetch_github_profile_as_dict("https://github.com/octocat")

    def test_invalid_url_raises_valueerror_without_http_call(self):
        with pytest.raises(ValueError):
            fetch_github_profile_as_dict("https://notgithub.com/octocat")

    @responses.activate
    def test_repository_pagination_followed(self):
        full_page = [
            {"name": f"repo-{i}", "description": None, "language": "Python", "fork": False}
            for i in range(100)
        ]
        second_page = [
            {"name": "repo-100", "description": None, "language": "Go", "fork": False}
        ]
        responses.add(
            responses.GET,
            "https://api.github.com/users/prolific",
            json={"login": "prolific", "name": "Prolific Coder", "bio": None,
                  "email": None, "location": None},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/prolific/repos",
            json=full_page,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/prolific/repos",
            json=second_page,
            status=200,
        )
        record = fetch_github_profile_as_dict("https://github.com/prolific")
        assert len(record["repositories"]) == 101
        assert "Go" in record["languages"]


# ---------------------------------------------------------------------------
# fetch_github_profiles_as_list
# ---------------------------------------------------------------------------

class TestFetchGithubProfilesAsList:
    @responses.activate
    def test_skips_failed_profiles_without_aborting_batch(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/gooduser",
            json={"login": "gooduser", "name": "Good User", "bio": None,
                  "email": "good@example.com", "location": None},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/gooduser/repos",
            json=[],
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/baduser",
            json={"message": "Not Found"},
            status=404,
        )
        results = fetch_github_profiles_as_list(
            ["https://github.com/gooduser", "https://github.com/baduser"]
        )
        assert len(results) == 1
        assert results[0]["name"] == "Good User"


# ---------------------------------------------------------------------------
# Integration: fetched dict flows correctly into the unchanged github_parser
# ---------------------------------------------------------------------------

class TestFetcherParserIntegration:
    @responses.activate
    def test_fetched_dict_parses_into_intermediate_record(self):
        responses.add(
            responses.GET,
            "https://api.github.com/users/octocat",
            json={
                "login": "octocat",
                "name": "The Octocat",
                "bio": "Engineer with 7 years experience",
                "email": "octocat@github.com",
                "location": "SF",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/users/octocat/repos",
            json=[{"name": "Hello-World", "description": "demo",
                   "language": "Python", "fork": False}],
            status=200,
        )
        fetched = fetch_github_profile_as_dict("https://github.com/octocat")
        parsed = parse_github(fetched)

        assert len(parsed) == 1
        assert parsed[0]["source"] == "GitHub"
        assert parsed[0]["confidence"] == 0.80
        assert parsed[0]["years_experience"] == 7.0
        assert "Python" in parsed[0]["skills"]
        assert "Hello-World" in parsed[0]["repo_names"]
