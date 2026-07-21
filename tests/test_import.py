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
