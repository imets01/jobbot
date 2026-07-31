import json

from sqlalchemy import func, select

from backend.models import Job
from backend.repository import import_json_files


def test_import_current_scraper_json_is_idempotent(session, tmp_path):
    payloads = [
        {
            "title": "Security Engineer",
            "company": "Example AG",
            "link": "https://ch.linkedin.com/jobs/view/security-engineer-at-example-4412345678",
            "description": "Build security automation with Python.",
            "role_query": "Security Engineer",
            "location_query": "Zurich, Switzerland",
            "scraped_at": "2026-07-21T10:00:00+00:00",
        },
        {
            "title": "Cloud Engineer",
            "company": "Cloud AG",
            "link": "https://ch.linkedin.com/jobs/view/cloud-engineer-at-cloud-4498765432",
            "description": "Operate Kubernetes platforms.",
            "role_query": "Security Engineer",
            "location_query": "Zurich, Switzerland",
            "scraped_at": "2026-07-21T10:01:00+00:00",
        },
    ]
    paths = []
    for index, payload in enumerate(payloads):
        path = tmp_path / f"job_{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)

    first = import_json_files(session, paths)
    second = import_json_files(session, paths)

    assert first.jobs_created == 2
    assert first.files_failed == 0
    assert second.jobs_created == 0
    assert second.jobs_updated == 2
    assert second.files_failed == 0
    assert session.scalar(select(func.count(Job.id))) == 2


def test_exact_job_content_is_deduplicated_across_sources(session, tmp_path):
    common = {
        "title": "Security Engineer",
        "company": "Example AG",
        "description": "Build cloud security automation with Python.",
        "location": "Zurich, Switzerland",
        "scraped_at": "2026-07-29T10:00:00+00:00",
    }
    payloads = [
        {
            **common,
            "link": "https://www.linkedin.com/jobs/view/5512345678",
            "source": "linkedin",
        },
        {
            **common,
            "link": "https://job-boards.greenhouse.io/example/jobs/123",
            "source": "greenhouse",
        },
    ]
    paths = []
    for index, payload in enumerate(payloads):
        path = tmp_path / f"job_cross_source_{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)

    stats = import_json_files(session, paths)

    assert stats.jobs_created == 1
    assert stats.jobs_updated == 1
    assert session.scalar(select(func.count(Job.id))) == 1
    job = session.scalar(select(Job))
    assert job is not None
    assert job.source == "linkedin"
    assert "linkedin.com" in (job.normalized_url or "")
