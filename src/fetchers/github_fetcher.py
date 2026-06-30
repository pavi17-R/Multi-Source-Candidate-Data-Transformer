"""
fetchers/github_fetcher.py

Fetches a GitHub user's profile and repository data from the live
GitHub REST API, given the user's GitHub *profile URL* (the new,
unstructured input source), and converts the response into EXACTLY
the same intermediate dictionary shape that github_parser.py already
expects from github.json.

This module is the ONLY thing that knows about:
  - GitHub profile URL parsing
  - the GitHub REST API (https://api.github.com)
  - HTTP fetching / retries / error handling

github_parser.py never needs to know whether the data originated from
a static JSON fixture or a live API call.

GitHub REST API endpoints used:
  - GET /users/{username}            -> profile data
  - GET /users/{username}/repos      -> repository list (paginated)

Output shape (one dict per fetched profile, list of length 0 or 1),
matching the existing github.json schema:

    {
        "name": str | None,
        "bio": str | None,
        "email": str | None,
        "location": str | None,
        "repositories": [
            {"name": str, "description": str | None, "language": str | None},
            ...
        ],
        "languages": [str, ...]
    }
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'requests' package is required for github_fetcher.py. "
        "Install it with: pip install requests"
    ) from exc

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 10
PER_PAGE = 100
MAX_REPO_PAGES = 10  # safety cap (up to 1000 repos)

# Matches github.com/<username> (optionally with trailing slash, path, query)
GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/?",
    re.IGNORECASE,
)


class GithubFetchError(Exception):
    """Raised when a GitHub profile cannot be fetched (network/API errors)."""


def extract_username(profile_url: str) -> str:
    """
    Extract the GitHub username from a profile URL.

    Accepts forms such as:
        https://github.com/octocat
        http://github.com/octocat/
        github.com/octocat
        www.github.com/octocat

    Raises:
        ValueError: if the URL does not look like a valid GitHub profile URL.
    """
    if not profile_url or not profile_url.strip():
        raise ValueError("GitHub profile URL must not be empty.")

    candidate = profile_url.strip()
    match = GITHUB_URL_RE.match(candidate)
    if not match:
        raise ValueError(
            f"'{profile_url}' does not look like a valid GitHub profile URL "
            f"(expected something like https://github.com/<username>)."
        )

    username = match.group(1)

    # Reject GitHub's reserved/non-user paths so we fail fast with a clear error
    # instead of sending a bogus request to the API.
    reserved = {
        "orgs", "organizations", "marketplace", "notifications", "settings",
        "explore", "topics", "collections", "trending", "events", "sponsors",
        "about", "pricing", "features", "apps", "issues", "pulls", "codespaces",
    }
    if username.lower() in reserved:
        raise ValueError(
            f"'{username}' is a reserved GitHub path, not a username."
        )

    return username


def _build_session() -> "requests.Session":
    session = requests.Session()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "candidate-transformer/1.0",
    }
    session.headers.update(headers)
    return session


def _get_json(session: "requests.Session", url: str, params: dict | None = None):
    try:
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as exc:
        raise GithubFetchError(f"Network error while calling GitHub API: {exc}") from exc

    if response.status_code == 404:
        raise GithubFetchError(f"GitHub resource not found: {url}")

    if response.status_code in (403, 429):
        remaining = response.headers.get("X-RateLimit-Remaining")
        raise GithubFetchError(
            "GitHub API rate limit exceeded or access forbidden "
            f"(status={response.status_code}, remaining={remaining}). "
            "Try again later or set a GITHUB_TOKEN environment variable."
        )

    if not response.ok:
        raise GithubFetchError(
            f"GitHub API request failed: {url} -> status {response.status_code}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise GithubFetchError(f"GitHub API returned invalid JSON for {url}") from exc


def fetch_user_profile(username: str, session: "requests.Session | None" = None) -> dict:
    """
    Fetch the public profile for a GitHub user via GET /users/{username}.
    """
    own_session = session is None
    session = session or _build_session()
    try:
        url = f"{GITHUB_API_BASE}/users/{username}"
        logger.info("Fetching GitHub user profile: %s", url)
        return _get_json(session, url)
    finally:
        if own_session:
            session.close()


def fetch_user_repositories(
    username: str, session: "requests.Session | None" = None
) -> list[dict]:
    """
    Fetch all public repositories for a GitHub user via
    GET /users/{username}/repos, following pagination.
    """
    own_session = session is None
    session = session or _build_session()
    repos: list[dict] = []
    try:
        url = f"{GITHUB_API_BASE}/users/{username}/repos"
        for page in range(1, MAX_REPO_PAGES + 1):
            params = {
                "per_page": PER_PAGE,
                "page": page,
                "type": "owner",
                "sort": "updated",
            }
            logger.info("Fetching GitHub repositories: %s (page %d)", url, page)
            data = _get_json(session, url, params=params)
            if not isinstance(data, list) or not data:
                break
            repos.extend(data)
            if len(data) < PER_PAGE:
                break
        return repos
    finally:
        if own_session:
            session.close()


def _infer_email(profile: dict) -> str | None:
    """
    GitHub profile email is often null unless the user has made it public.
    We only use what the API actually exposes - no scraping/guessing.
    """
    email = profile.get("email")
    return email if email else None


def _to_repository_entries(repos: list[dict]) -> list[dict]:
    """
    Convert raw GitHub API repository objects into the simplified
    {"name", "description", "language"} shape used by github_parser.py.
    """
    entries: list[dict] = []
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        name = repo.get("name")
        if not name:
            continue
        # Skip forks so we reflect the candidate's own work, mirroring
        # the spirit of the original simulated dataset (owner-authored repos).
        if repo.get("fork"):
            continue
        entries.append(
            {
                "name": name,
                "description": repo.get("description"),
                "language": repo.get("language"),
            }
        )
    return entries


def _collect_languages(repo_entries: list[dict]) -> list[str]:
    """Collect the distinct set of primary languages across repositories."""
    seen: list[str] = []
    for entry in repo_entries:
        lang = entry.get("language")
        if lang and lang not in seen:
            seen.append(lang)
    return seen


def fetch_github_profile_as_dict(
    profile_url: str, session: "requests.Session | None" = None
) -> dict:
    """
    High-level entry point: given a GitHub profile URL, fetch the user's
    profile + repositories from the live GitHub REST API and return a
    single dict in EXACTLY the same shape github_parser.py already
    expects from each item in github.json.

    Args:
        profile_url: e.g. "https://github.com/octocat"
        session: optional pre-built requests.Session (mainly for testing
                 or connection reuse).

    Returns:
        dict matching the github.json item schema:
        {
            "name": str | None,
            "bio": str | None,
            "email": str | None,
            "location": str | None,
            "repositories": [{"name", "description", "language"}, ...],
            "languages": [str, ...]
        }

    Raises:
        ValueError: if profile_url is not a valid GitHub profile URL.
        GithubFetchError: if the GitHub API call(s) fail.
    """
    username = extract_username(profile_url)

    own_session = session is None
    session = session or _build_session()
    try:
        profile = fetch_user_profile(username, session=session)
        repos_raw = fetch_user_repositories(username, session=session)
    finally:
        if own_session:
            session.close()

    repository_entries = _to_repository_entries(repos_raw)
    languages = _collect_languages(repository_entries)

    bio = profile.get("bio") or None

    # GitHub's "company"/"hireable" fields aren't part of the existing
    # schema, so we don't introduce new fields - we only populate the
    # keys the parser already understands, keeping it format-compatible.
    record = {
        "name": profile.get("name") or profile.get("login"),
        "bio": bio,
        "email": _infer_email(profile),
        "location": profile.get("location") or None,
        "repositories": repository_entries,
        "languages": languages,
    }

    logger.info(
        "Fetched GitHub profile for '%s': %d repositories, %d languages",
        username,
        len(repository_entries),
        len(languages),
    )
    return record


def fetch_github_profiles_as_list(
    profile_urls: list[str], session: "requests.Session | None" = None
) -> list[dict]:
    """
    Convenience helper to fetch multiple GitHub profile URLs and return
    a list of dicts, matching the list-of-users shape of the original
    github.json file. Profiles that fail to fetch are logged and skipped
    rather than aborting the whole batch.
    """
    own_session = session is None
    session = session or _build_session()
    results: list[dict] = []
    try:
        for url in profile_urls:
            try:
                results.append(fetch_github_profile_as_dict(url, session=session))
            except (ValueError, GithubFetchError) as exc:
                logger.error("Skipping GitHub profile '%s': %s", url, exc)
    finally:
        if own_session:
            session.close()
    return results
