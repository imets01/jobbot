"""
scraper.py
----------
Scrapes public LinkedIn job cards (no login required) for a given role and
location using Playwright.

For each job it extracts:
  - title
  - company
  - link
  - full raw description text

Each job is saved as a unique JSON file inside the `/data` directory.

Human-like random delays (2-5s) are used between actions to reduce the chance
of triggering bot detection. This tool only reads *public* pages and does not
authenticate, in keeping with a safe, decoupled design.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import config

# Lightweight public LinkedIn "guest" job endpoints (no authentication needed).
# The seeMoreJobPostings search API honors the location filter and returns a
# compact list of job cards, which is much faster than rendering the full
# single-page-app search results.
SEARCH_URL_TEMPLATE = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={role}&location={location}&start={start}"
)

# Per-job description endpoint. Returns just the description HTML fragment.
JOB_URL_TEMPLATE = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


def human_delay(
    min_seconds: float = config.MIN_DELAY_SECONDS,
    max_seconds: float = config.MAX_DELAY_SECONDS,
) -> None:
    """Sleep for a random duration to mimic human browsing behavior."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def _job_id_from_link(link: str) -> str:
    """Derive a stable, unique identifier for a job from its link.

    Uses a short SHA-256 hash so repeated runs overwrite the same file
    instead of creating duplicates.
    """
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]


def _save_job(job: dict, data_dir: Path) -> Path:
    """Persist a single job as a JSON file and return its path."""
    job_id = _job_id_from_link(job["link"])
    file_path = data_dir / f"job_{job_id}.json"
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    return file_path


def _job_id_from_url(url: str) -> str | None:
    """Extract the numeric LinkedIn job id from a job view URL.

    Job links look like `.../jobs/view/solution-engineer-at-acme-3812345678`;
    the trailing long number is the job posting id.
    """
    matches = re.findall(r"\d{6,}", url)
    return matches[-1] if matches else None


def _extract_description(page: Page) -> str:
    """Return the full raw description text for the currently open job posting.

    The guest jobPosting endpoint returns the full description markup directly,
    so no "show more" expansion is needed. Tolerates the page navigating away
    mid-query (LinkedIn sometimes redirects), returning "" in that case.
    """
    try:
        description_el = page.query_selector(
            ".show-more-less-html__markup, .description__text"
        )
        if description_el:
            return description_el.inner_text().strip()

        # Fallback: the endpoint returns a bare fragment, so use the whole body.
        body = page.query_selector("body")
        return body.inner_text().strip() if body else ""
    except PlaywrightError:
        # Page navigated/redirected while querying; treat as no description.
        return ""


def _extract_search_cards(page: Page, attempts: int = 3) -> list[dict[str, str]]:
    """Extract one search page atomically, retrying transient redirects.

    LinkedIn can continue navigating after ``domcontentloaded``. Querying and
    then iterating element handles during that redirect leaves stale handles and
    raises "Execution context was destroyed". A single page evaluation returns
    plain dictionaries, and retrying that atomic operation tolerates the race.
    """
    for attempt in range(attempts):
        try:
            cards = page.eval_on_selector_all(
                "li",
                """elements => elements.map(card => {
                    const title = card.querySelector('h3.base-search-card__title');
                    const company = card.querySelector('h4.base-search-card__subtitle');
                    const link = card.querySelector('a.base-card__full-link');
                    return title && link ? {
                        title: title.textContent.trim(),
                        company: company ? company.textContent.trim() : 'Unknown',
                        link: (link.href || '').split('?')[0],
                    } : null;
                }).filter(Boolean)""",
            )
            return cards
        except PlaywrightError:
            if attempt + 1 >= attempts:
                raise
            page.wait_for_timeout(300 * (attempt + 1))
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except PlaywrightTimeoutError:
                pass
    return []


def scrape_jobs(
    role: str = config.DEFAULT_ROLE,
    location: str = config.DEFAULT_LOCATION,
    max_jobs: int = config.MAX_JOBS,
) -> list[Path]:
    """Scrape public LinkedIn job cards and save each as a JSON file.

    Args:
        role: Job title / keywords to search for.
        location: Location to search within.
        max_jobs: Maximum number of jobs to collect this run.

    Returns:
        A list of file paths for the JSON files that were written.
    """
    data_dir = config.ensure_data_dir()
    saved_paths: list[Path] = []

    with sync_playwright() as p:
        # Headless Chromium with a realistic user agent.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = context.new_page()

        print(f"[scraper] Searching: role='{role}', location='{location}'")

        # Phase 1: collect job cards from the lightweight guest search API,
        # paginating (10 per page) until we have enough or run out of results.
        card_infos: list[dict] = []
        start = 0
        seen_ids: set[str] = set()
        while len(card_infos) < max_jobs:
            search_url = SEARCH_URL_TEMPLATE.format(
                role=quote_plus(role),
                location=quote_plus(location),
                start=start,
            )
            try:
                page.goto(search_url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                break

            try:
                cards = _extract_search_cards(page)
            except PlaywrightError as exc:
                print(
                    "[scraper] LinkedIn kept redirecting the search page; "
                    f"stopping pagination safely: {exc}"
                )
                break
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                if len(card_infos) >= max_jobs:
                    break

                link = card["link"]
                job_id = _job_id_from_url(link)
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                card_infos.append(
                    {
                        "title": card["title"],
                        "company": card["company"],
                        "link": link,
                        "job_id": job_id,
                    }
                )
                new_on_page += 1

            print(f"[scraper] Collected {len(card_infos)} job card(s) so far...")

            # Stop if this page added nothing new (end of results).
            if new_on_page == 0:
                break
            start += 10
            human_delay(0.4, 1.0)

        # Phase 2: fetch each description from the lightweight jobPosting API.
        for index, info in enumerate(card_infos):
            description = ""
            job_url = JOB_URL_TEMPLATE.format(job_id=info["job_id"])
            try:
                page.goto(job_url, wait_until="domcontentloaded")
                description = _extract_description(page)
            except (PlaywrightTimeoutError, PlaywrightError):
                print(
                    f"[scraper] Could not load job {index} "
                    f"({info['title']}); saving without description."
                )

            job = {
                "title": info["title"],
                "company": info["company"],
                "link": info["link"],
                "description": description,
                "role_query": role,
                "location_query": location,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

            path = _save_job(job, data_dir)
            saved_paths.append(path)
            print(
                f"[scraper] Saved ({len(saved_paths)}): "
                f"{info['title']} @ {info['company']}"
            )

            # Short, human-like pause before the next request.
            human_delay(0.4, 1.0)

        browser.close()

    print(f"[scraper] Done. {len(saved_paths)} jobs saved to {data_dir}.")
    return saved_paths


if __name__ == "__main__":
    scrape_jobs()
