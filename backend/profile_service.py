"""Structured candidate profile defaults and Gemini context rendering."""

from __future__ import annotations

import json
import hashlib
from typing import Any

from analyzer import CANDIDATE_PROFILE


DEFAULT_PROFILE: dict[str, Any] = {
    "full_name": "",
    "email": "",
    "current_location": "Zurich, Switzerland",
    "linkedin_url": "",
    "portfolio_url": "",
    "education": ["Informatics student at the University of Zurich; thesis completion planned for October."],
    "work_experience": [
        "Full-stack engineering internship",
        "DevOps engineering internship at Swisscom",
        "Security Solution Engineer internship at Microsoft",
    ],
    "skills": ["Python", "Java", "Go", "Docker", "Kubernetes", "Microsoft security solutions"],
    "certifications": [],
    "languages": [],
    "projects": [],
    "professional_summary": (
        "Early-career informatics candidate with hands-on software, DevOps, cloud, "
        "and security solution engineering experience."
    ),
    "role_keywords": [
        "Solution Engineer",
        "Security Engineer",
        "DevOps Engineer",
        "Software Engineer",
    ],
    "preferred_seniority": "Entry level / Junior",
    "preferred_industries": ["Technology", "Cloud", "Cybersecurity"],
    "preferred_locations": ["Zurich, Switzerland"],
    "work_model_preferences": ["Remote", "Hybrid", "Onsite"],
    "years_total_experience": 2.0,
    "years_software_engineering": 1.0,
    "years_cloud_experience": 1.0,
    "years_customer_facing": 1.0,
    "base_cover_letter": "",
    "career_motivation": (
        "Build a career in hands-on technical security, cloud, or solution engineering "
        "rather than a predominantly sales-focused role."
    ),
    "key_achievements": [],
    "projects_to_highlight": [],
    "writing_tone": "Professional",
    "mention_preferences": {
        "education": True,
        "certifications": True,
        "internships": True,
        "projects": True,
        "customer_facing_experience": True,
        "technical_skills": True,
        "career_motivation": True,
    },
}

DEFAULT_SEARCH_SETTINGS: dict[str, Any] = {
    "keywords": ["Solution Engineer", "Security Engineer", "DevOps Engineer"],
    "target_locations": ["Zurich, Switzerland"],
    "work_models": ["Remote", "Hybrid", "Onsite"],
    "minimum_match_score": 60,
    "number_of_jobs": 20,
    "include_stretch_roles": False,
    "max_required_experience_years": 4.0,
    "exclude_unavailable_languages": False,
    "exclude_outside_locations": True,
    "sources": ["LinkedIn"],
    "greenhouse_boards": [],
    "lever_sites": [],
}


def json_dict(raw: str | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Safely decode a JSON object from a database text column."""
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else dict(default or {})
    except (json.JSONDecodeError, TypeError):
        return dict(default or {})


def json_list(raw: str | None) -> list[Any]:
    """Safely decode a JSON array from a database text column."""
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def initial_profile_from_legacy(content: str | None) -> dict[str, Any]:
    """Seed structured data without discarding a pre-existing text profile."""
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    cleaned = (content or "").strip()
    if cleaned and cleaned != CANDIDATE_PROFILE.strip():
        profile["professional_summary"] = cleaned
    return profile


def render_profile_text(profile: dict[str, Any]) -> str:
    """Render structured fields into a stable, human-readable audit snapshot."""
    return "Structured candidate profile:\n" + json.dumps(
        profile,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def render_search_settings(settings: dict[str, Any]) -> str:
    return "Job search controls:\n" + json.dumps(
        settings,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def profile_for_search(
    profile: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    """Use search keywords as the sole role-target source for matching."""
    result = json.loads(json.dumps(profile))
    result["role_keywords"] = list(settings.get("keywords") or [])
    return result


def build_analysis_context(
    profile: dict[str, Any],
    settings: dict[str, Any],
    raw_cv_text: str = "",
) -> str:
    """Build the exact context supplied to Gemini and retained in history."""
    sections = [render_profile_text(profile), render_search_settings(settings)]
    cleaned_cv = raw_cv_text.strip()
    if cleaned_cv:
        sections.append(
            "Raw CV text (supporting evidence; never invent facts beyond this text):\n"
            + cleaned_cv[:30_000]
        )
    return "\n\n".join(sections)


def build_profile_snapshot(
    profile: dict[str, Any],
    settings: dict[str, Any],
    raw_cv_text: str = "",
) -> str:
    """Build a stable audit/cache snapshot without exposing private CV text."""
    sections = [render_profile_text(profile), render_search_settings(settings)]
    cleaned_cv = raw_cv_text.strip()
    if cleaned_cv:
        digest = hashlib.sha256(cleaned_cv.encode("utf-8")).hexdigest()
        sections.append(f"Raw CV evidence SHA-256: {digest}")
    else:
        sections.append("Raw CV evidence: none")
    return "\n\n".join(sections)
