"""Common contracts and helpers for pluggable job-discovery sources."""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    keywords: list[str]
    locations: list[str]
    work_models: list[str]
    max_jobs: int
    targets: list[str]
    data_dir: Path
    cancelled: Callable[[], bool] = lambda: False


@dataclass(slots=True)
class DiscoveryResult:
    paths: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    completed_targets: int = 0


class JobSourceAdapter(ABC):
    name: str
    note: str
    target_field: str | None = None

    @abstractmethod
    def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Discover normalized jobs and persist replayable JSON artifacts."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def html_to_text(value: str | None) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(value or "")
        parser.close()
    except Exception:
        return " ".join(unescape(value or "").split())
    return "\n".join(parser.parts).strip()


def normalize_search_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def matches_keywords(title: str, keywords: list[str]) -> bool:
    """Match role phrases against titles without broad description false positives."""
    title_text = normalize_search_text(title)
    title_words = re.findall(r"[a-z0-9+#.]+", title_text)
    if not title_words:
        return False

    for keyword in keywords:
        phrase = normalize_search_text(keyword)
        if phrase and phrase in title_text:
            return True
        tokens = [
            token
            for token in re.findall(r"[a-z0-9+#.]+", phrase)
            if token not in {"and", "or", "the", "a", "an"}
        ]
        if tokens and all(
            any(
                word == token
                or (len(word) >= 5 and len(token) >= 5 and word[:5] == token[:5])
                for word in title_words
            )
            for token in tokens
        ):
            return True
    return False


def matches_location(location: str | None, locations: list[str], work_models: list[str]) -> bool:
    if not location:
        return True
    job_location = normalize_search_text(location)
    if "remote" in job_location and any(model.casefold() == "remote" for model in work_models):
        return True
    for requested in locations:
        requested_text = normalize_search_text(requested)
        if not requested_text:
            continue
        primary = requested_text.split(",", 1)[0].strip()
        if primary and (primary in job_location or job_location in primary):
            return True
    return False


def save_job_payload(
    payload: dict,
    data_dir: Path,
    *,
    source: str,
    external_id: str | int | None = None,
) -> Path:
    """Persist one normalized source payload using a stable source identity."""
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["source"] = source.casefold()
    payload.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
    identity = str(external_id or payload.get("link") or payload.get("url") or json.dumps(payload, sort_keys=True))
    digest = hashlib.sha256(f"{source.casefold()}:{identity}".encode("utf-8")).hexdigest()[:16]
    path = data_dir / f"job_{digest}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
