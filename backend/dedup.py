"""Deterministic job URL normalization and duplicate prevention helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit

_TRACKING_SUFFIX = re.compile(r"[?#].*$")
_LINKEDIN_JOB_ID = re.compile(r"(?:jobs/view/[^/?#]*?-|jobs/view/)(\d{6,})", re.IGNORECASE)
_LONG_NUMBER = re.compile(r"\d{6,}")


def normalize_text(value: str | None) -> str:
    """Normalize user-visible text for deterministic comparison and hashing."""
    text = unicodedata.normalize("NFKC", value or "")
    return " ".join(text.casefold().split())


def normalize_job_url(url: str | None) -> str | None:
    """Return a stable URL, canonicalizing LinkedIn locale and tracking URLs."""
    if not url or not url.strip():
        return None

    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlsplit(raw)
    host = (parsed.hostname or "").casefold()
    host = host.removeprefix("www.")
    path = unquote(parsed.path).rstrip("/")

    if host.endswith("linkedin.com"):
        match = _LINKEDIN_JOB_ID.search(path)
        if not match:
            numbers = _LONG_NUMBER.findall(path)
            job_id = numbers[-1] if numbers else None
        else:
            job_id = match.group(1)
        if job_id:
            return f"https://www.linkedin.com/jobs/view/{job_id}"

    scheme = (parsed.scheme or "https").casefold()
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    return urlunsplit((scheme, netloc, path or "/", "", ""))


def content_hash(
    title: str | None,
    company: str | None,
    location: str | None,
    description: str | None,
) -> str:
    """Hash normalized job content for fallback deduplication and change tracking."""
    payload = "\x1f".join(
        normalize_text(part) for part in (title, company, location, description)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dedup_key(
    url: str | None,
    title: str | None,
    company: str | None,
    location: str | None,
    description: str | None,
) -> tuple[str, str | None, str]:
    """Return ``(dedup_key, normalized_url, content_hash)`` for a job."""
    normalized_url = normalize_job_url(url)
    hash_value = content_hash(title, company, location, description)
    if normalized_url:
        url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        return f"url:{url_hash}", normalized_url, hash_value
    return f"content:{hash_value}", None, hash_value
