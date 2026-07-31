"""Search-source capabilities exposed to the web client."""

from __future__ import annotations

from backend.sources import connected_source_capabilities

SOURCE_CAPABILITIES = connected_source_capabilities() + [
    {
        "name": "Company career pages",
        "available": False,
        "note": "Generic career-page adapter not configured yet.",
    },
    {"name": "Workday", "available": False, "note": "Adapter not configured yet."},
    {
        "name": "Manual job URL",
        "available": False,
        "note": "Manual URL importer is reserved for a future source adapter.",
    },
    {
        "name": "Other public job boards",
        "available": False,
        "note": "Adapter not configured yet.",
    },
]

AVAILABLE_SOURCE_NAMES = {
    item["name"] for item in SOURCE_CAPABILITIES if item["available"]
}
