"""LinkedIn adapter around the existing public guest-endpoint scraper."""

from __future__ import annotations

import math

from scraper import scrape_jobs

from backend.sources.base import DiscoveryRequest, DiscoveryResult, JobSourceAdapter


class LinkedInAdapter(JobSourceAdapter):
    name = "LinkedIn"
    note = "Broad search through public LinkedIn job listings."

    def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        result = DiscoveryResult()
        role_query = " OR ".join(request.keywords)
        per_location = max(1, math.ceil(request.max_jobs / max(1, len(request.locations))))
        seen_paths = set()
        for location in request.locations:
            try:
                discovered = scrape_jobs(
                    role=role_query,
                    location=location,
                    max_jobs=per_location,
                    cancelled=request.cancelled,
                )
                result.completed_targets += 1
                for path in discovered:
                    if path not in seen_paths:
                        result.paths.append(path)
                        seen_paths.add(path)
            except Exception as exc:  # isolate one location from the others
                result.errors.append(f"{location}: {type(exc).__name__}: {exc}")
            if request.cancelled():
                break
        return result
