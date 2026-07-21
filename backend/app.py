"""FastAPI application for the local-first Jobbot dashboard."""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import config
from analyzer import CANDIDATE_PROFILE
from backend.database import get_db, init_database, session_scope
from backend.models import AnalysisResult, AnalysisRun, Application, Job
from backend.repository import (
    dashboard_data,
    get_job_analyses,
    get_job_row,
    get_or_create_profile,
    get_or_update_application,
    get_run_results,
    import_data_directory,
    list_applications,
    list_companies,
    list_jobs,
    list_runs,
    reset_profile,
    set_job_archived,
    update_profile,
)
from backend.run_manager import RunConflictError, run_manager
from backend.schemas import (
    AnalysisResultOut,
    ApplicationBoardItem,
    ApplicationOut,
    ApplicationStatus,
    ApplicationUpdate,
    ArchiveUpdate,
    CandidateProfileOut,
    CandidateProfileUpdate,
    DashboardSummary,
    JobDetail,
    JobListItem,
    PaginatedJobs,
    PaginatedRuns,
    RunOut,
    RunRequest,
    RunResultItem,
    SettingsOut,
    StatusCount,
)

DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    run_manager.recover_stale_runs()
    with session_scope() as session:
        stats = import_data_directory(session, config.DATA_DIR)
        if stats.files_seen:
            print(
                "[startup] Imported raw data: "
                f"{stats.jobs_created} new, {stats.jobs_updated} refreshed, "
                f"{stats.files_failed} failed."
            )
        get_or_create_profile(session)
    yield


app = FastAPI(
    title="Jobbot Local API",
    version="1.0.0",
    description="Local-first job discovery, Gemini analysis, and application tracking.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def analysis_out(value: AnalysisResult | None) -> AnalysisResultOut | None:
    return AnalysisResultOut.model_validate(value) if value else None


def application_out(value: Application | None) -> ApplicationOut | None:
    return ApplicationOut.model_validate(value) if value else None


def job_item(
    job: Job,
    analysis: AnalysisResult | None = None,
    application: Application | None = None,
) -> JobListItem:
    return JobListItem(
        id=job.id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location,
        source=job.source,
        first_seen=job.first_seen,
        last_seen=job.last_seen,
        archived=job.archived,
        latest_analysis=analysis_out(analysis),
        application=application_out(application),
    )


def start_run_or_409(
    run_type: str,
    payload: dict,
    *,
    job_id: int | None = None,
) -> RunOut:
    try:
        run = run_manager.start(run_type, payload, job_id=job_id)
        return RunOut.model_validate(run)
    except RunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "run_in_progress", "message": str(exc)},
        ) from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings", response_model=SettingsOut)
def settings() -> SettingsOut:
    return SettingsOut(
        default_role=config.DEFAULT_ROLE,
        default_location=config.DEFAULT_LOCATION,
        default_max_jobs=config.MAX_JOBS,
        gemini_model=config.GEMINI_MODEL,
    )


@app.get("/api/dashboard", response_model=DashboardSummary)
def dashboard(session: DbSession) -> DashboardSummary:
    values = dashboard_data(session)
    recent = [job_item(*row) for row in values["recent_good_matches"]]
    active = RunOut.model_validate(values["active_run"]) if values["active_run"] else None
    return DashboardSummary(
        total_jobs=values["total_jobs"],
        good_matches=values["good_matches"],
        waiting_for_analysis=values["waiting_for_analysis"],
        applications_submitted=values["applications_submitted"],
        follow_ups_due=values["follow_ups_due"],
        recent_good_matches=recent,
        application_statuses=[StatusCount(**item) for item in values["application_statuses"]],
        active_run=active,
    )


@app.get("/api/jobs", response_model=PaginatedJobs)
def jobs(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    match: Literal["good", "not"] | None = None,
    seniority: Literal["suitable", "unsuitable"] | None = None,
    analyzed: Literal["yes", "no"] | None = None,
    application_status: ApplicationStatus | None = None,
    company: str | None = Query(None, max_length=300),
    archived: Literal["active", "archived", "all"] = "active",
    sort: Literal["newest", "last_analyzed", "company", "match_quality"] = "newest",
    direction: Literal["asc", "desc"] = "desc",
) -> PaginatedJobs:
    rows, total = list_jobs(
        session,
        page=page,
        page_size=page_size,
        search=search,
        match=match,
        seniority=seniority,
        analyzed=analyzed,
        application_status=application_status.value if application_status else None,
        company=company,
        archived=archived,
        sort=sort,
        direction=direction,
    )
    return PaginatedJobs(
        items=[job_item(*row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@app.get("/api/jobs/companies", response_model=list[str])
def companies(session: DbSession) -> list[str]:
    return list_companies(session)


@app.get("/api/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: int, session: DbSession) -> JobDetail:
    row = get_job_row(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job, latest, application = row
    return JobDetail(
        **job_item(job, latest, application).model_dump(),
        description=job.description,
        content_hash=job.content_hash,
        analyses=[analysis_out(item) for item in get_job_analyses(session, job_id)],
    )


@app.patch("/api/jobs/{job_id}/archive", response_model=JobListItem)
def archive_job(job_id: int, payload: ArchiveUpdate, session: DbSession) -> JobListItem:
    row = get_job_row(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job, analysis, application = row
    application = set_job_archived(session, job, payload.archived)
    session.commit()
    session.refresh(job)
    return job_item(job, analysis, application)


@app.put("/api/jobs/{job_id}/application", response_model=ApplicationOut)
def save_application(
    job_id: int,
    payload: ApplicationUpdate,
    session: DbSession,
) -> ApplicationOut:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    application = get_or_update_application(
        session,
        job,
        status=payload.status.value,
        application_date=payload.application_date,
        next_follow_up_date=payload.next_follow_up_date,
        notes=payload.notes,
    )
    session.commit()
    session.refresh(application)
    return ApplicationOut.model_validate(application)


@app.post("/api/jobs/{job_id}/reanalyze", response_model=RunOut, status_code=202)
def reanalyze_job(job_id: int, session: DbSession) -> RunOut:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return start_run_or_409("analyzer", {"mode": "reanalyze"}, job_id=job_id)


@app.get("/api/applications", response_model=list[ApplicationBoardItem])
def applications(session: DbSession) -> list[ApplicationBoardItem]:
    return [
        ApplicationBoardItem(
            job=job_item(job, analysis, application),
            application=ApplicationOut.model_validate(application),
        )
        for job, analysis, application in list_applications(session)
    ]


@app.get("/api/profile", response_model=CandidateProfileOut)
def candidate_profile(session: DbSession) -> CandidateProfileOut:
    profile = get_or_create_profile(session)
    return CandidateProfileOut(
        content=profile.content,
        version=profile.version,
        updated_at=profile.updated_at,
        is_default=profile.content.strip() == CANDIDATE_PROFILE.strip(),
    )


@app.put("/api/profile", response_model=CandidateProfileOut)
def save_candidate_profile(
    payload: CandidateProfileUpdate,
    session: DbSession,
) -> CandidateProfileOut:
    profile = update_profile(session, payload.content)
    session.commit()
    return CandidateProfileOut(
        content=profile.content,
        version=profile.version,
        updated_at=profile.updated_at,
        is_default=profile.content.strip() == CANDIDATE_PROFILE.strip(),
    )


@app.post("/api/profile/reset", response_model=CandidateProfileOut)
def restore_candidate_profile(session: DbSession) -> CandidateProfileOut:
    profile = reset_profile(session)
    session.commit()
    return CandidateProfileOut(
        content=profile.content,
        version=profile.version,
        updated_at=profile.updated_at,
        is_default=True,
    )


@app.post("/api/runs/scraper", response_model=RunOut, status_code=202)
def run_scraper(payload: RunRequest) -> RunOut:
    return start_run_or_409("scraper", payload.model_dump())


@app.post("/api/runs/analyzer", response_model=RunOut, status_code=202)
def run_analyzer() -> RunOut:
    return start_run_or_409("analyzer", {"mode": "new_jobs"})


@app.post("/api/runs/full", response_model=RunOut, status_code=202)
def run_full_pipeline(payload: RunRequest) -> RunOut:
    return start_run_or_409("full", payload.model_dump())


@app.get("/api/runs/active", response_model=RunOut | None)
def get_active_run(session: DbSession) -> RunOut | None:
    from backend.repository import active_run

    run = active_run(session)
    return RunOut.model_validate(run) if run else None


@app.get("/api/runs", response_model=PaginatedRuns)
def runs(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_type: Literal["scraper", "analyzer", "full"] | None = None,
    run_status: Literal["pending", "running", "completed", "failed"] | None = Query(
        None, alias="status"
    ),
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedRuns:
    items, total = list_runs(
        session,
        page=page,
        page_size=page_size,
        run_type=run_type,
        status=run_status,
        date_from=date_from,
        date_to=date_to,
    )
    return PaginatedRuns(
        items=[RunOut.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@app.get("/api/runs/{run_id}", response_model=RunOut)
def run_status(run_id: str, session: DbSession) -> RunOut:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut.model_validate(run)


@app.get("/api/runs/{run_id}/results", response_model=list[RunResultItem])
def run_results(run_id: str, session: DbSession) -> list[RunResultItem]:
    if session.get(AnalysisRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [
        RunResultItem(
            job=job_item(job, analysis, application),
            analysis=AnalysisResultOut.model_validate(analysis),
        )
        for job, analysis, application in get_run_results(session, run_id)
    ]


# When a production frontend build exists, FastAPI can serve it too. During
# development Vite runs separately on port 5173 and proxies /api to FastAPI.
frontend_dist = config.BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_app(full_path: str):
        """Serve the React entry point for client-side routes."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        candidate = (frontend_dist / full_path).resolve()
        if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
