"""Registry of connected job-discovery source adapters."""

from __future__ import annotations

from backend.sources.ats import GreenhouseAdapter, LeverAdapter
from backend.sources.base import DiscoveryRequest, DiscoveryResult, JobSourceAdapter
from backend.sources.linkedin import LinkedInAdapter

_ADAPTER_LIST: list[JobSourceAdapter] = [
    LinkedInAdapter(),
    GreenhouseAdapter(),
    LeverAdapter(),
]
SOURCE_ADAPTERS = {adapter.name.casefold(): adapter for adapter in _ADAPTER_LIST}


def get_source_adapter(name: str) -> JobSourceAdapter:
    adapter = SOURCE_ADAPTERS.get(name.casefold())
    if adapter is None:
        raise KeyError(f"Search source '{name}' is not connected")
    return adapter


def connected_source_capabilities() -> list[dict[str, object]]:
    return [
        {"name": adapter.name, "available": True, "note": adapter.note}
        for adapter in _ADAPTER_LIST
    ]


__all__ = [
    "DiscoveryRequest",
    "DiscoveryResult",
    "JobSourceAdapter",
    "SOURCE_ADAPTERS",
    "connected_source_capabilities",
    "get_source_adapter",
]
