"""Public Greenhouse and Lever company-board discovery adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable
from urllib.parse import quote, urlsplit

import httpx

from backend.sources.base import (
    DiscoveryRequest,
    DiscoveryResult,
    JobSourceAdapter,
    html_to_text,
    matches_keywords,
    matches_location,
    save_job_payload,
)

_REQUEST_HEADERS = {"User-Agent": "Jobbot/1.0 local job discovery"}
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_REQUEST_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class BoardTarget:
    token: str
    company: str
    api_base: str = ""


def _get_json(url: str, cancelled: Callable[[], bool]):
    last_error: Exception | None = None
    for attempt in range(_MAX_REQUEST_ATTEMPTS):
        if cancelled():
            raise RuntimeError("Discovery cancelled")
        try:
            response = httpx.get(
                url,
                headers=_REQUEST_HEADERS,
                timeout=30,
                follow_redirects=True,
            )
            if (
                getattr(response, "status_code", 200) in _TRANSIENT_STATUS_CODES
                and attempt + 1 < _MAX_REQUEST_ATTEMPTS
            ):
                time.sleep(0.5 * (2**attempt))
                continue
            response.raise_for_status()
            return response.json()
        except httpx.TransportError as exc:
            last_error = exc
            if attempt + 1 >= _MAX_REQUEST_ATTEMPTS:
                raise
            time.sleep(0.5 * (2**attempt))
    if last_error:
        raise last_error
    raise RuntimeError("Job-board request failed after retries")


def _labeled_target(value: str) -> tuple[str, str]:
    if "|" not in value:
        return "", value.strip()
    label, target = value.split("|", 1)
    return label.strip(), target.strip()


def _company_from_token(token: str) -> str:
    return token.replace("-", " ").replace("_", " ").strip().title()


def parse_greenhouse_target(value: str) -> BoardTarget:
    label, raw = _labeled_target(value)
    if not raw:
        raise ValueError("Greenhouse board target is empty")
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").casefold()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host and "greenhouse.io" in host:
        if "boards" in segments:
            index = segments.index("boards")
            token = segments[index + 1] if index + 1 < len(segments) else ""
        else:
            token = segments[0] if segments else ""
    elif "://" in raw or "." in raw:
        token = segments[0] if segments else ""
    else:
        token = raw
    token = token.strip().strip("/")
    if not token:
        raise ValueError(f"Could not determine a Greenhouse board token from '{value}'")
    return BoardTarget(token=token, company=label or _company_from_token(token))


def parse_lever_target(value: str) -> BoardTarget:
    label, raw = _labeled_target(value)
    if not raw:
        raise ValueError("Lever site target is empty")
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").casefold()
    segments = [segment for segment in parsed.path.split("/") if segment]
    api_base = "https://api.lever.co"
    if host and "lever.co" in host:
        if host.startswith("api.") and "postings" in segments:
            index = segments.index("postings")
            token = segments[index + 1] if index + 1 < len(segments) else ""
        else:
            token = segments[0] if segments else ""
        if ".eu.lever.co" in host:
            api_base = "https://api.eu.lever.co"
    elif "://" in raw or "." in raw:
        token = segments[0] if segments else ""
    else:
        token = raw
    token = token.strip().strip("/")
    if not token:
        raise ValueError(f"Could not determine a Lever site name from '{value}'")
    return BoardTarget(
        token=token,
        company=label or _company_from_token(token),
        api_base=api_base,
    )


def greenhouse_jobs(payload: dict, target: BoardTarget, request: DiscoveryRequest) -> list[dict]:
    jobs: list[dict] = []
    for item in payload.get("jobs", []):
        title = str(item.get("title") or "").strip()
        location = str((item.get("location") or {}).get("name") or "").strip() or None
        if not matches_keywords(title, request.keywords):
            continue
        if not matches_location(location, request.locations, request.work_models):
            continue
        jobs.append(
            {
                "title": title or "Untitled job",
                "company": target.company,
                "link": item.get("absolute_url"),
                "description": html_to_text(item.get("content")),
                "location": location,
                "external_id": str(item.get("id") or ""),
                "role_query": " OR ".join(request.keywords),
                "location_query": " OR ".join(request.locations),
                "scraped_at": item.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            }
        )
    return jobs


def lever_jobs(payload: list, target: BoardTarget, request: DiscoveryRequest) -> list[dict]:
    jobs: list[dict] = []
    for item in payload:
        title = str(item.get("text") or "").strip()
        categories = item.get("categories") or {}
        location = str(categories.get("location") or "").strip() or None
        if not matches_keywords(title, request.keywords):
            continue
        if not matches_location(location, request.locations, request.work_models):
            continue
        list_text = "\n".join(
            f"{section.get('text', '')}\n{html_to_text(section.get('content'))}".strip()
            for section in item.get("lists", [])
        )
        description = "\n\n".join(
            part
            for part in (
                str(item.get("descriptionPlain") or "").strip(),
                list_text.strip(),
                str(item.get("additionalPlain") or "").strip(),
            )
            if part
        )
        created = item.get("createdAt")
        if isinstance(created, (int, float)):
            scraped_at = datetime.fromtimestamp(created / 1000, timezone.utc).isoformat()
        else:
            scraped_at = datetime.now(timezone.utc).isoformat()
        jobs.append(
            {
                "title": title or "Untitled job",
                "company": target.company,
                "link": item.get("hostedUrl") or item.get("applyUrl"),
                "description": description,
                "location": location,
                "external_id": str(item.get("id") or ""),
                "workplace_type": item.get("workplaceType"),
                "role_query": " OR ".join(request.keywords),
                "location_query": " OR ".join(request.locations),
                "scraped_at": scraped_at,
            }
        )
    return jobs


class GreenhouseAdapter(JobSourceAdapter):
    name = "Greenhouse"
    note = "Public company job boards; configure board URLs or tokens below."
    target_field = "greenhouse_boards"

    def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        result = DiscoveryResult()
        discovered: list[dict] = []
        for raw_target in request.targets:
            if request.cancelled():
                break
            try:
                target = parse_greenhouse_target(raw_target)
                url = f"https://boards-api.greenhouse.io/v1/boards/{quote(target.token, safe='')}/jobs?content=true"
                discovered.extend(greenhouse_jobs(_get_json(url, request.cancelled), target, request))
                result.completed_targets += 1
            except Exception as exc:
                result.errors.append(f"{raw_target}: {type(exc).__name__}: {exc}")

        discovered.sort(key=lambda job: str(job.get("scraped_at") or ""), reverse=True)
        for job in discovered[: request.max_jobs]:
            if request.cancelled():
                break
            result.paths.append(
                save_job_payload(
                    job,
                    request.data_dir,
                    source="greenhouse",
                    external_id=job.get("external_id"),
                )
            )
        return result


class LeverAdapter(JobSourceAdapter):
    name = "Lever"
    note = "Public company job boards; configure site URLs or names below."
    target_field = "lever_sites"

    def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        result = DiscoveryResult()
        discovered: list[dict] = []
        for raw_target in request.targets:
            if request.cancelled():
                break
            try:
                target = parse_lever_target(raw_target)
                url = f"{target.api_base}/v0/postings/{quote(target.token, safe='')}?mode=json"
                payload = _get_json(url, request.cancelled)
                if not isinstance(payload, list):
                    raise ValueError("Lever returned an unexpected response")
                discovered.extend(lever_jobs(payload, target, request))
                result.completed_targets += 1
            except Exception as exc:
                result.errors.append(f"{raw_target}: {type(exc).__name__}: {exc}")

        discovered.sort(key=lambda job: str(job.get("scraped_at") or ""), reverse=True)
        for job in discovered[: request.max_jobs]:
            if request.cancelled():
                break
            result.paths.append(
                save_job_payload(
                    job,
                    request.data_dir,
                    source="lever",
                    external_id=job.get("external_id"),
                )
            )
        return result
