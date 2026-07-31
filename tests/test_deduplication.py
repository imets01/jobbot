from sqlalchemy import func, select

from backend.models import Job
from backend.dedup import normalize_job_url, safe_job_url
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


def test_job_urls_reject_unsafe_schemes_and_credentials(session):
    assert safe_job_url("javascript:alert(1)") is None
    assert safe_job_url("file:///C:/secret.txt") is None
    assert safe_job_url("https://user:password@example.com/job") is None
    assert normalize_job_url("data://text/html/payload") is None

    job, _ = upsert_job(
        session,
        {
            "title": "Imported role",
            "company": "Example",
            "link": "javascript:alert(1)",
            "description": "A safely imported description.",
        },
    )
    assert job.url is None
    assert job.normalized_url is None
    assert job.dedup_key.startswith("content:")


def test_safe_job_url_preserves_required_query_parameters():
    url = "https://jobs.example.com/apply?id=123&source=career-page"
    assert safe_job_url(url) == url
