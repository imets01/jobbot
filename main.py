"""
main.py
-------
Entry point that orchestrates the pipeline:

    1. Scrape public LinkedIn job cards (scraper.py).
    2. Analyze each scraped description with Gemini (analyzer.py).

Search parameters can be provided via CLI flags; sensible defaults come from
config.py.

Examples:
    python main.py
    python main.py --role "Data Engineer" --location "Berlin" --max-jobs 10
    python main.py --analyze-only
    python main.py --scrape-only
"""

from __future__ import annotations

import argparse

import config
from analyzer import analyze_all
from scraper import scrape_jobs


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape public LinkedIn jobs and evaluate fit with Gemini."
    )
    parser.add_argument(
        "--role",
        default=config.DEFAULT_ROLE,
        help=f"Job role / keywords (default: '{config.DEFAULT_ROLE}').",
    )
    parser.add_argument(
        "--location",
        default=config.DEFAULT_LOCATION,
        help=f"Location to search (default: '{config.DEFAULT_LOCATION}').",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=config.MAX_JOBS,
        help=f"Maximum jobs to scrape (default: {config.MAX_JOBS}).",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only run the scraper; skip Gemini analysis.",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only run the analyzer over existing /data files; skip scraping.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the scrape -> analyze pipeline based on CLI flags."""
    args = parse_args()

    scraped_paths = None

    # --- Scrape stage ------------------------------------------------------
    if not args.analyze_only:
        print("=== Stage 1: Scraping ===")
        scraped_paths = scrape_jobs(
            role=args.role,
            location=args.location,
            max_jobs=args.max_jobs,
        )
    else:
        print("=== Skipping scrape stage (--analyze-only) ===")

    # --- Analyze stage -----------------------------------------------------
    if not args.scrape_only:
        print("\n=== Stage 2: Analyzing ===")
        # A normal full run analyzes only the jobs just scraped. The explicit
        # --analyze-only mode intentionally analyzes every existing data file.
        results = analyze_all(job_paths=scraped_paths)

        # Summarize good matches (relevant technical role AND right seniority).
        matches = [
            r for r in results if r["is_good_match"] and r["seniority_ok"]
        ]
        print(
            f"\n=== Summary: {len(matches)}/{len(results)} roles are a good fit "
            f"(technical + early-career) ==="
        )
        for r in matches:
            print(f"  - {r['title']} @ {r['company']}: {r['link']}")
            print(f"      {r['verdict']}")
    else:
        print("\n=== Skipping analyze stage (--scrape-only) ===")


if __name__ == "__main__":
    main()
