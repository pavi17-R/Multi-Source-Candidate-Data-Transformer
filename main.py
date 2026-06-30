"""
main.py

CLI entry point for the Multi-Source Candidate Data Transformer.

Usage:
    python main.py \\
        --csv input/recruiter.csv \\
        --github-url https://github.com/octocat \\
        --config config/default.json \\
        [--output output/candidates.json]

The GitHub source is now a live GitHub *profile URL* (unstructured
source) instead of a static github.json fixture. Internally:

    GitHub URL
        |
        v
    src/fetchers/github_fetcher.py   (fetch profile + repos via GitHub REST API)
        |
        v
    src/parsers/github_parser.py     (parse into intermediate records - unchanged shape)
        |
        v
    existing merge / project / output pipeline (completely unchanged)

Backward compatibility:
    For local testing/offline use without hitting the live GitHub API,
    --github-json (legacy file path) is still supported and routes
    straight into the unchanged github_parser.parse_github(filepath)
    path, exactly as before.
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

from src.parsers import parse_csv, parse_github
from src.fetchers import fetch_github_profile_as_dict, GithubFetchError
from src.mergers import merge_records
from src.utils import project, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-Source Candidate Data Transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", required=True, help="Path to recruiter CSV file")

    github_group = parser.add_mutually_exclusive_group(required=True)
    github_group.add_argument(
        "--github-url",
        default=None,
        help="GitHub profile URL to fetch live, e.g. https://github.com/octocat",
    )
    github_group.add_argument(
        "--github-json",
        default=None,
        help=(
            "(Legacy / offline) Path to a github.json fixture file, "
            "kept for backward compatibility and offline testing."
        ),
    )

    parser.add_argument(
        "--config",
        default="config/default.json",
        help="Path to output config JSON (default: config/default.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: output/candidates_<timestamp>.json)",
    )
    return parser


def run(
    csv_path: str,
    config_path: str,
    output_path: str | None,
    github_url: str | None = None,
    github_json_path: str | None = None,
) -> None:
    """
    Full pipeline: fetch/parse -> merge -> project -> output.
    """
    logger.info("=== Candidate Transformer Pipeline Start ===")

    # 1. Parse CSV (unchanged)
    logger.info("Parsing CSV: %s", csv_path)
    csv_records = parse_csv(csv_path)

    # 2. Obtain GitHub data: either fetch live from a profile URL, or
    #    (legacy/offline) read straight from a JSON fixture file.
    if github_url:
        logger.info("Fetching GitHub profile from URL: %s", github_url)
        try:
            github_data = fetch_github_profile_as_dict(github_url)
        except (ValueError, GithubFetchError) as exc:
            logger.error("Failed to fetch GitHub profile '%s': %s", github_url, exc)
            github_data = []
        github_records = parse_github(github_data)
    else:
        logger.info("Parsing GitHub JSON (legacy/offline mode): %s", github_json_path)
        github_records = parse_github(github_json_path)

    all_records = csv_records + github_records
    logger.info("Total parsed records: %d", len(all_records))

    # 3. Merge (unchanged)
    candidates = merge_records(all_records)
    logger.info("Canonical profiles produced: %d", len(candidates))

    # 4. Load config (unchanged)
    config = load_config(config_path)

    # 5. Project output (unchanged)
    output_records = [project(c, config) for c in candidates]

    # 6. Print to stdout (unchanged)
    output_json = json.dumps(output_records, indent=2, ensure_ascii=False)
    print("\n" + output_json)

    # 7. Save to file (unchanged)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/candidates_{timestamp}.json"

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(output_json, encoding="utf-8")
    logger.info("Output saved to: %s", out_file)
    logger.info("=== Pipeline Complete ===")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run(
        csv_path=args.csv,
        config_path=args.config,
        output_path=args.output,
        github_url=args.github_url,
        github_json_path=args.github_json,
    )


if __name__ == "__main__":
    main()
