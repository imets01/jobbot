from sqlalchemy import select

import config
from analyzer import CANDIDATE_PROFILE
from backend.models import AnalysisResult
from backend.repository import create_run, get_run_results, upsert_job


def test_analysis_history_preserves_profile_snapshot(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Security Engineer",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/4412345678",
            "description": "One year of experience required.",
        },
    )
    run = create_run(session, "run-1", "analyzer", {"mode": "new_jobs"})
    snapshot = CANDIDATE_PROFILE.strip()
    result = AnalysisResult(
        job_id=job.id,
        run_id=run.id,
        candidate_profile_snapshot=snapshot,
        candidate_profile_version=1,
        is_good_match=True,
        seniority_ok=True,
        verdict="Strong junior security match.",
        gemini_model=config.GEMINI_MODEL,
    )
    session.add(result)
    session.commit()

    stored = session.scalar(select(AnalysisResult).where(AnalysisResult.id == result.id))
    history = get_run_results(session, run.id)
    assert stored is not None
    assert stored.candidate_profile_snapshot == snapshot
    assert history[0][1].verdict == "Strong junior security match."
