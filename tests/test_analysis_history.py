from sqlalchemy import select

import config
from analyzer import CANDIDATE_PROFILE
from backend.models import AnalysisResult, AnalysisRun, Application, CoverLetter, Job
from backend.repository import (
    create_run,
    get_run_results,
    list_runs,
    remove_run_from_history,
    upsert_job,
)


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


def test_completed_run_is_hidden_without_losing_jobs_or_analysis(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Cloud Security Engineer",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/4412345679",
            "description": "Cloud security engineering role.",
        },
    )
    run = create_run(
        session,
        "run-completed",
        "search",
        {"search_controls": {"keywords": ["Security Engineer"]}},
    )
    run.status = "completed"
    result = AnalysisResult(
        job_id=job.id,
        run_id=run.id,
        candidate_profile_snapshot="profile",
        candidate_profile_version=1,
        is_good_match=True,
        seniority_ok=True,
        verdict="Strong match.",
        gemini_model=config.GEMINI_MODEL,
        match_score=88,
        qualifies=True,
    )
    session.add(result)
    session.commit()

    assert remove_run_from_history(session, run) == "hidden"
    session.commit()

    runs, total = list_runs(session)
    assert runs == []
    assert total == 0
    assert session.get(AnalysisRun, run.id) is not None
    assert session.get(AnalysisResult, result.id) is not None
    assert session.get(Job, job.id) is not None


def test_failed_run_is_deleted_without_losing_application_work(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Security Analyst",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/4412345680",
            "description": "Security analysis role.",
        },
    )
    run = create_run(session, "run-failed", "search", {})
    run.status = "failed"
    result = AnalysisResult(
        job_id=job.id,
        run_id=run.id,
        candidate_profile_snapshot="profile",
        candidate_profile_version=1,
        is_good_match=None,
        seniority_ok=None,
        verdict="",
        gemini_model=config.GEMINI_MODEL,
        error_message="Provider unavailable.",
    )
    session.add(result)
    session.flush()
    application = Application(job_id=job.id, status="Interested")
    letter = CoverLetter(
        job_id=job.id,
        analysis_result_id=result.id,
        candidate_profile_version=1,
        content="A retained cover letter with sufficient content.",
        gemini_model=config.GEMINI_MODEL,
    )
    session.add_all([application, letter])
    session.commit()

    assert remove_run_from_history(session, run) == "deleted"
    session.commit()
    session.expire_all()

    assert session.get(AnalysisRun, "run-failed") is None
    assert session.get(AnalysisResult, result.id) is None
    assert session.get(Job, job.id) is not None
    assert session.get(Application, application.id) is not None
    retained_letter = session.get(CoverLetter, letter.id)
    assert retained_letter is not None
    assert retained_letter.analysis_result_id is None
