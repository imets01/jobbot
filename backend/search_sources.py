"""Search-source capability registry.

Only LinkedIn is connected to the existing scraper today. The registry gives the
UI a stable extension point without pretending that unsupported sources work.
Future adapters can implement the same normalized job-import contract.
"""

from __future__ import annotations


SOURCE_CAPABILITIES = [
    {
        "name": "LinkedIn",
        "available": True,
        "note": "Connected to public LinkedIn job listings.",
    },
    {
        "name": "Company career pages",
        "available": False,
        "note": "Adapter not configured yet.",
    },
    {"name": "Greenhouse", "available": False, "note": "Adapter not configured yet."},
    {"name": "Lever", "available": False, "note": "Adapter not configured yet."},
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
