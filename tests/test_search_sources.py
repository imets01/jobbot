from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schemas import SearchControls
from backend.search_sources import AVAILABLE_SOURCE_NAMES
from backend.sources.ats import (
    GreenhouseAdapter,
    greenhouse_jobs,
    lever_jobs,
    parse_greenhouse_target,
    parse_lever_target,
)
from backend.sources.base import DiscoveryRequest


def request(tmp_path: Path) -> DiscoveryRequest:
    return DiscoveryRequest(
        keywords=["Security Engineer", "DevOps Engineer"],
        locations=["Zurich, Switzerland"],
        work_models=["Hybrid", "Remote"],
        max_jobs=20,
        targets=[],
        data_dir=tmp_path,
    )


def test_greenhouse_target_and_payload_normalization(tmp_path):
    target = parse_greenhouse_target(
        "Example AG | https://job-boards.greenhouse.io/example/jobs/123"
    )
    assert target.token == "example"
    assert target.company == "Example AG"

    jobs = greenhouse_jobs(
        {
            "jobs": [
                {
                    "id": 42,
                    "title": "Cloud Security Engineer",
                    "absolute_url": "https://job-boards.greenhouse.io/example/jobs/42",
                    "location": {"name": "Zurich, Switzerland"},
                    "content": "<p>Protect cloud platforms &amp; automate controls.</p>",
                    "updated_at": "2026-07-29T08:00:00Z",
                },
                {
                    "id": 43,
                    "title": "Account Executive",
                    "location": {"name": "Zurich, Switzerland"},
                },
            ]
        },
        target,
        request(tmp_path),
    )

    assert len(jobs) == 1
    assert jobs[0]["company"] == "Example AG"
    assert jobs[0]["description"] == "Protect cloud platforms & automate controls."


def test_lever_target_and_payload_normalization(tmp_path):
    target = parse_lever_target("Example | https://jobs.eu.lever.co/example")
    assert target.token == "example"
    assert target.api_base == "https://api.eu.lever.co"

    jobs = lever_jobs(
        [
            {
                "id": "abc",
                "text": "DevOps Platform Engineer",
                "categories": {"location": "Remote - Switzerland"},
                "hostedUrl": "https://jobs.eu.lever.co/example/abc",
                "descriptionPlain": "Build the platform.",
                "lists": [{"text": "What you do", "content": "<li>Run Kubernetes</li>"}],
                "createdAt": 1785312000000,
                "workplaceType": "remote",
            }
        ],
        target,
        request(tmp_path),
    )

    assert len(jobs) == 1
    assert "Run Kubernetes" in jobs[0]["description"]
    assert jobs[0]["workplace_type"] == "remote"


def test_connected_sources_and_target_validation():
    assert {"LinkedIn", "Greenhouse", "Lever"} <= AVAILABLE_SOURCE_NAMES

    base = {
        "keywords": ["Security Engineer"],
        "target_locations": ["Zurich, Switzerland"],
        "sources": ["Greenhouse"],
    }
    with pytest.raises(ValidationError, match="Greenhouse company board"):
        SearchControls.model_validate(base)

    controls = SearchControls.model_validate(
        {**base, "greenhouse_boards": ["Example | example"]}
    )
    assert controls.greenhouse_boards == ["Example | example"]


def test_discovery_result_tracks_completed_empty_board(monkeypatch, tmp_path):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"jobs": []}

    monkeypatch.setattr("backend.sources.ats.httpx.get", lambda *_args, **_kwargs: Response())
    result = GreenhouseAdapter().discover(
        DiscoveryRequest(
            keywords=["Security Engineer"],
            locations=["Zurich, Switzerland"],
            work_models=["Hybrid"],
            max_jobs=10,
            targets=["Example | example"],
            data_dir=tmp_path,
        )
    )

    assert result.paths == []
    assert result.errors == []
    assert result.completed_targets == 1
