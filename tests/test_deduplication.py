from sqlalchemy import func, select

from backend.models import Job
from backend.repository import upsert_job


def test_linkedin_locale_and_tracking_urls_deduplicate(session):
    first, created_first = upsert_job(
        session,
        {
            "title": "Security Engineer",
            "company": "Example",
            "link": "https://ch.linkedin.com/jobs/view/security-engineer-at-example-4412345678?trackingId=abc",
            "description": "Build detections.",
            "location_query": "Zurich, Switzerland",
        },
    )
    second, created_second = upsert_job(
        session,
        {
            "title": "Security Engineer - updated",
            "company": "Example",
            "link": "https://www.linkedin.com/jobs/view/4412345678#details",
            "description": "Build detections and response tooling.",
            "location_query": "Zurich, Switzerland",
        },
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert second.normalized_url == "https://www.linkedin.com/jobs/view/4412345678"
    assert second.title == "Security Engineer - updated"
    assert session.scalar(select(func.count(Job.id))) == 1


def test_url_less_jobs_use_deterministic_content_hash(session):
    payload = {
        "title": "Junior Cloud Engineer",
        "company": "Example AG",
        "description": "Python and Kubernetes",
        "location": "Zurich",
    }
    first, _ = upsert_job(session, payload)
    second, created = upsert_job(session, dict(payload))

    assert created is False
    assert first.id == second.id
    assert second.dedup_key.startswith("content:")
