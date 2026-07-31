import asyncio
from contextlib import asynccontextmanager

import httpx

from backend.app import app
from backend.database import get_db
from backend.repository import get_or_update_application, upsert_job


@asynccontextmanager
async def api_client(session_factory):
    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_api_rejects_untrusted_hosts_and_missing_jobs(session_factory):
    async def scenario():
        async with api_client(session_factory) as client:
            assert (await client.get("/api/health")).json() == {"status": "ok"}
            assert (await client.get("/api/health", headers={"host": "malicious.example"})).status_code == 400
            allowed = await client.options(
                "/api/runs/search",
                headers={
                    "origin": "http://localhost:5173",
                    "access-control-request-method": "POST",
                    "access-control-request-headers": "content-type",
                },
            )
            assert allowed.status_code == 200
            assert allowed.headers["access-control-allow-methods"] == "GET, POST, PUT, PATCH, DELETE"
            denied = await client.options(
                "/api/runs/search",
                headers={
                    "origin": "https://malicious.example",
                    "access-control-request-method": "POST",
                },
            )
            assert denied.status_code == 400
            response = await client.get("/api/jobs/999999")
            assert response.status_code == 404
            assert response.json()["detail"] == "Job not found"

    asyncio.run(scenario())


def test_api_validates_search_entry_lengths(session_factory):
    async def scenario():
        async with api_client(session_factory) as client:
            response = await client.put(
                "/api/search-controls",
                json={
                    "keywords": ["x" * 201],
                    "target_locations": ["Zurich, Switzerland"],
                    "work_models": ["Hybrid"],
                    "minimum_match_score": 60,
                    "number_of_jobs": 20,
                    "include_stretch_roles": False,
                    "max_required_experience_years": 4,
                    "exclude_unavailable_languages": False,
                    "exclude_outside_locations": True,
                    "sources": ["LinkedIn"],
                    "greenhouse_boards": [],
                    "lever_sites": [],
                },
            )
            assert response.status_code == 422
            assert "200 characters or fewer" in response.text

    asyncio.run(scenario())


def test_application_untracking_endpoint_preserves_job(session_factory):
    with session_factory() as session:
        job, _ = upsert_job(
            session,
            {
                "title": "Security Engineer",
                "company": "Example",
                "link": "https://linkedin.com/jobs/view/9912345678",
                "description": "Security engineering role.",
            },
        )
        get_or_update_application(
            session,
            job,
            status="Interested",
            application_date=None,
            next_follow_up_date=None,
            notes="Review later.",
        )
        session.commit()
        job_id = job.id

    async def scenario():
        async with api_client(session_factory) as client:
            response = await client.delete(f"/api/jobs/{job_id}/application")
            assert response.status_code == 204
            detail = await client.get(f"/api/jobs/{job_id}")
            assert detail.status_code == 200
            assert detail.json()["application"] is None
            assert (await client.delete(f"/api/jobs/{job_id}/application")).status_code == 404

    asyncio.run(scenario())
