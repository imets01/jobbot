"""FastAPI application for the local-first Jobbot dashboard."""

from __future__ import annotations

import math
import json
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

import config
from backend.database import get_db, init_database, session_scope
from backend.dedup import safe_job_url
from backend.cover_letter_service import generate_cover_letter
from backend.cv_service import (
    delete_stored_cv,
    extract_structured_profile,
    extract_text,
    store_cv_bytes,
    validate_cv_upload,
)
from backend.models import (
    AnalysisResult,
    AnalysisRun,
    Application,
    CoverLetter,
    CVDocument,
    Job,
    utc_now,
)
from backend.profile_service import json_dict, json_list
from backend.repository import (
    create_cover_letter,
    dashboard_data,
    delete_application,
    get_cv_document,
    get_job_analyses,
    get_job_row,
    get_or_create_profile,
    get_or_create_search_settings,
    get_or_update_application,
    get_run_results,
    get_structured_profile,
    import_data_directory,
    latest_cover_letter,
    list_applications,
    list_companies,
    list_jobs,
    list_runs,
    remove_run_from_history,
    reset_structured_profile,
    search_settings_dict,
    set_job_archived,
    set_job_dismissed,
    update_cover_letter_content,
    update_search_settings,
    update_structured_profile,
    upsert_cv_document,
)
from backend.run_manager import RunConflictError, run_manager
from backend.search_sources import AVAILABLE_SOURCE_NAMES, SOURCE_CAPABILITIES
from backend.schemas import (
    AnalysisResultOut,
    ApplicationBoardItem,
    ApplicationOut,
    ApplicationStatus,
    ApplicationUpdate,
    ArchiveUpdate,
    CandidateProfileOut,
    CandidateProfileUpdate,
    CoverLetterOut,
    CoverLetterUpdate,
    CVDocumentOut,
    CVExtractionOut,
    DashboardSummary,
    DismissUpdate,
    JobDetail,
    JobListItem,
    PaginatedJobs,
    PaginatedRuns,
    RunOut,
    RunRemovalOut,
    RunResultItem,
    SearchControls,
    SearchControlsOut,
    SearchRunRequest,
    SearchSourceCapability,
    StatusCount,
    StructuredCandidateProfile,
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
        get_or_create_search_settings(session)
    yield


app = FastAPI(
    title="Jobbot Local API",
    version="1.0.0",
    description="Local-first job discovery, Gemini analysis, and application tracking.",
    lifespan=lifespan,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "testserver"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Accept", "Content-Type"],
)


def analysis_out(value: AnalysisResult | None) -> AnalysisResultOut | None:
    if value is None:
        return None
    return AnalysisResultOut(
        id=value.id,
        job_id=value.job_id,
        run_id=value.run_id,
        created_at=value.created_at,
        candidate_profile_snapshot=value.candidate_profile_snapshot,
        candidate_profile_version=value.candidate_profile_version,
        is_good_match=value.is_good_match,
        seniority_ok=value.seniority_ok,
        verdict=value.verdict,
        gemini_model=value.gemini_model,
        error_message=value.error_message,
        match_score=value.match_score,
        qualifies=value.qualifies,
        recommendation_label=value.recommendation_label,
        short_explanation=value.short_explanation or value.verdict,
        score_breakdown={
            key: int(score)
            for key, score in json_dict(value.score_breakdown_json).items()
        },
        matched_strengths=json_list(value.matched_strengths_json),
        weak_areas=json_list(value.weak_areas_json),
        potential_concerns=json_list(value.potential_concerns_json),
        missing_requirements=json_list(value.missing_requirements_json),
        suggested_resume_keywords=json_list(value.resume_keywords_json),
        application_strategy=value.application_strategy,
        work_model=value.work_model,
        required_experience_years=value.required_experience_years,
        required_languages=json_list(value.required_languages_json),
        critical_gaps=json_list(value.critical_gaps_json),
    )


def application_out(value: Application | None) -> ApplicationOut | None:
    return ApplicationOut.model_validate(value) if value else None


def cv_out(value: CVDocument | None) -> CVDocumentOut | None:
    if value is None:
        return None
    return CVDocumentOut(
        file_name=value.original_name,
        content_type=value.content_type,
        size_bytes=value.size_bytes,
        uploaded_at=value.uploaded_at,
        extracted_at=value.extracted_at,
        has_raw_text=bool(value.raw_text.strip()),
    )


def profile_out(session: Session) -> CandidateProfileOut:
    profile = get_or_create_profile(session)
    return CandidateProfileOut(
        profile=StructuredCandidateProfile.model_validate(
            get_structured_profile(session)
        ),
        version=profile.version,
        updated_at=profile.updated_at,
        cv=cv_out(get_cv_document(session)),
    )


def job_item(
    job: Job,
    analysis: AnalysisResult | None = None,
    application: Application | None = None,
) -> JobListItem:
    return JobListItem(
        id=job.id,
        title=job.title,
        company=job.company,
        url=safe_job_url(job.url),
        location=job.location,
        source=job.source,
        first_seen=job.first_seen,
        last_seen=job.last_seen,
        archived=job.archived,
        dismissed=job.dismissed,
        latest_analysis=analysis_out(analysis),
        application=application_out(application),
    )


def run_out(value: AnalysisRun) -> RunOut:
    controls = None
    raw_controls = json_dict(value.parameters_json).get("search_controls")
    if isinstance(raw_controls, dict):
        try:
            controls = SearchControls.model_validate(raw_controls)
        except ValueError:
            controls = None
    return RunOut.model_validate(value).model_copy(
        update={"search_controls": controls}
    )


def start_run_or_409(
    run_type: str,
    payload: dict,
    *,
    job_id: int | None = None,
) -> RunOut:
    try:
        run = run_manager.start(run_type, payload, job_id=job_id)
        return run_out(run)
    except RunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "run_in_progress", "message": str(exc)},
        ) from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard", response_model=DashboardSummary)
def dashboard(session: DbSession) -> DashboardSummary:
    values = dashboard_data(session)
    recent = [job_item(*row) for row in values["recent_good_matches"]]
    active = run_out(values["active_run"]) if values["active_run"] else None
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
    dismissed: Literal["active", "dismissed", "all"] = "active",
    minimum_score: int | None = Query(None, ge=0, le=100),
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
        dismissed=dismissed,
        minimum_score=minimum_score,
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


@app.patch("/api/jobs/{job_id}/dismiss", response_model=JobListItem)
def dismiss_job(job_id: int, payload: DismissUpdate, session: DbSession) -> JobListItem:
    row = get_job_row(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job, analysis, application = row
    set_job_dismissed(session, job, payload.dismissed)
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


@app.delete("/api/jobs/{job_id}/application", status_code=204)
def remove_application(job_id: int, session: DbSession) -> Response:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not delete_application(session, job):
        raise HTTPException(status_code=404, detail="Application is not tracked")
    session.commit()
    return Response(status_code=204)


@app.post("/api/jobs/{job_id}/reanalyze", response_model=RunOut, status_code=202)
def reanalyze_job(job_id: int, session: DbSession) -> RunOut:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return start_run_or_409("analyzer", {"mode": "reanalyze"}, job_id=job_id)


@app.get(
    "/api/jobs/{job_id}/cover-letter",
    response_model=CoverLetterOut | None,
)
def get_job_cover_letter(job_id: int, session: DbSession) -> CoverLetterOut | None:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    letter = latest_cover_letter(session, job_id)
    return CoverLetterOut.model_validate(letter) if letter else None


@app.post(
    "/api/jobs/{job_id}/cover-letter",
    response_model=CoverLetterOut,
    status_code=201,
)
def generate_job_cover_letter(job_id: int, session: DbSession) -> CoverLetterOut:
    row = get_job_row(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job, latest, _application = row
    if latest is None or latest.error_message:
        raise HTTPException(
            status_code=409,
            detail="Analyze this job successfully before generating a cover letter.",
        )
    profile_record = get_or_create_profile(session)
    profile = get_structured_profile(session)
    if not str(profile.get("base_cover_letter") or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Add and save a base cover letter in Candidate Profile first.",
        )
    cv = get_cv_document(session)
    analysis = analysis_out(latest)
    if analysis is None:  # pragma: no cover
        raise HTTPException(status_code=409, detail="Match analysis unavailable")
    try:
        content = generate_cover_letter(
            profile=profile,
            raw_cv_text=cv.raw_text if cv else "",
            job={
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "description": job.description,
            },
            analysis=analysis.model_dump(mode="json"),
        )
    except Exception as exc:  # surface provider failures without losing state
        raise HTTPException(
            status_code=502,
            detail="Cover letter generation is temporarily unavailable. Try again shortly.",
        ) from exc
    letter = create_cover_letter(
        session,
        job_id=job.id,
        analysis_result_id=latest.id,
        profile_version=profile_record.version,
        content=content,
        model=config.GEMINI_MODEL,
    )
    session.commit()
    return CoverLetterOut.model_validate(letter)


@app.put(
    "/api/jobs/{job_id}/cover-letter/{letter_id}",
    response_model=CoverLetterOut,
)
def save_job_cover_letter(
    job_id: int,
    letter_id: int,
    payload: CoverLetterUpdate,
    session: DbSession,
) -> CoverLetterOut:
    letter = session.get(CoverLetter, letter_id)
    if letter is None or letter.job_id != job_id:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    update_cover_letter_content(session, letter, payload.content)
    session.commit()
    return CoverLetterOut.model_validate(letter)


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
    return profile_out(session)


@app.put("/api/profile", response_model=CandidateProfileOut)
def save_candidate_profile(
    payload: CandidateProfileUpdate,
    session: DbSession,
) -> CandidateProfileOut:
    update_structured_profile(session, payload.profile.model_dump(mode="json"))
    session.commit()
    return profile_out(session)


@app.post("/api/profile/reset", response_model=CandidateProfileOut)
def restore_candidate_profile(session: DbSession) -> CandidateProfileOut:
    reset_structured_profile(session)
    session.commit()
    return profile_out(session)


@app.post("/api/profile/cv", response_model=CVDocumentOut, status_code=201)
async def upload_candidate_cv(
    session: DbSession,
    file: UploadFile = File(...),
) -> CVDocumentOut:
    filename = file.filename or "cv"
    content = await file.read(config.MAX_CV_SIZE_BYTES + 1)
    try:
        extension = validate_cv_upload(filename, file.content_type, len(content))
        raw_text = extract_text(content, extension)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # malformed PDF/DOCX
        raise HTTPException(
            status_code=422,
            detail="The CV could not be read. Verify that it is a valid PDF or DOCX file.",
        ) from exc

    previous = get_cv_document(session)
    previous_path = previous.storage_path if previous else None
    path = store_cv_bytes(filename, extension, content)
    document = upsert_cv_document(
        session,
        original_name=filename,
        content_type=file.content_type or (
            "application/pdf" if extension == ".pdf" else
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        storage_path=str(path),
        size_bytes=len(content),
        raw_text=raw_text,
    )
    session.commit()
    if previous_path and previous_path != str(path):
        delete_stored_cv(previous_path)
    result = cv_out(document)
    if result is None:  # pragma: no cover - document was just created
        raise HTTPException(status_code=500, detail="CV metadata was not saved")
    return result


@app.post("/api/profile/cv/extract", response_model=CVExtractionOut)
def extract_candidate_profile_from_cv(session: DbSession) -> CVExtractionOut:
    document = get_cv_document(session)
    if document is None:
        raise HTTPException(status_code=404, detail="Upload a CV before extracting it.")
    try:
        extracted = extract_structured_profile(document.raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="CV profile extraction is temporarily unavailable. Try again shortly.",
        ) from exc

    current = get_structured_profile(session)
    merged = dict(current)
    for key, value in extracted.items():
        if value not in ("", [], None):
            merged[key] = value
    validated = StructuredCandidateProfile.model_validate(merged)
    update_structured_profile(session, validated.model_dump(mode="json"))
    document.extracted_json = json.dumps(extracted, ensure_ascii=False)
    document.extracted_at = utc_now()
    session.commit()
    metadata = cv_out(document)
    if metadata is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="CV metadata unavailable")
    return CVExtractionOut(extracted_profile=validated, cv=metadata)


@app.get("/api/search-controls", response_model=SearchControlsOut)
def get_search_controls(session: DbSession) -> SearchControlsOut:
    settings = get_or_create_search_settings(session)
    return SearchControlsOut(
        **search_settings_dict(settings),
        updated_at=settings.updated_at,
    )


@app.put("/api/search-controls", response_model=SearchControlsOut)
def save_search_controls(
    payload: SearchControls,
    session: DbSession,
) -> SearchControlsOut:
    unavailable = set(payload.sources) - AVAILABLE_SOURCE_NAMES
    if unavailable:
        raise HTTPException(
            status_code=422,
            detail=(
                "These search sources are not connected yet: "
                + ", ".join(sorted(unavailable))
            ),
        )
    settings = update_search_settings(session, payload.model_dump(mode="json"))
    session.commit()
    return SearchControlsOut(
        **search_settings_dict(settings),
        updated_at=settings.updated_at,
    )


@app.get(
    "/api/search-controls/sources",
    response_model=list[SearchSourceCapability],
)
def search_source_capabilities() -> list[SearchSourceCapability]:
    return [SearchSourceCapability(**item) for item in SOURCE_CAPABILITIES]


@app.post("/api/runs/search", response_model=RunOut, status_code=202)
def run_structured_search(
    payload: SearchRunRequest,
    session: DbSession,
) -> RunOut:
    if payload.controls is not None:
        unavailable = set(payload.controls.sources) - AVAILABLE_SOURCE_NAMES
        if unavailable:
            raise HTTPException(
                status_code=422,
                detail=(
                    "These search sources are not connected yet: "
                    + ", ".join(sorted(unavailable))
                ),
            )
        settings = update_search_settings(
            session, payload.controls.model_dump(mode="json")
        )
        session.commit()
    else:
        settings = get_or_create_search_settings(session)
    controls = search_settings_dict(settings)
    return start_run_or_409("search", {"search_controls": controls})


@app.get("/api/runs/active", response_model=RunOut | None)
def get_active_run(session: DbSession) -> RunOut | None:
    from backend.repository import active_run

    run = active_run(session)
    return run_out(run) if run else None


@app.get("/api/runs", response_model=PaginatedRuns)
def runs(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_type: Literal["search", "scraper", "analyzer", "full"] | None = None,
    run_status: Literal["pending", "running", "completed", "failed", "cancelled"] | None = Query(
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
        items=[run_out(item) for item in items],
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
    return run_out(run)


@app.post("/api/runs/{run_id}/cancel", response_model=RunOut, status_code=202)
def cancel_run(run_id: str, session: DbSession) -> RunOut:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="This search has already finished.")
    if not run_manager.cancel(run_id):
        raise HTTPException(
            status_code=409,
            detail="This search is no longer managed by the current process.",
        )
    return run_out(run)


@app.delete("/api/runs/{run_id}", response_model=RunRemovalOut)
def remove_run(run_id: str, session: DbSession) -> RunRemovalOut:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in {"pending", "running"}:
        raise HTTPException(
            status_code=409,
            detail="Wait for the search to finish before removing it.",
        )
    disposition = remove_run_from_history(session, run)
    session.commit()
    return RunRemovalOut(disposition=disposition)


@app.get("/api/runs/{run_id}/results", response_model=list[RunResultItem])
def run_results(run_id: str, session: DbSession) -> list[RunResultItem]:
    if session.get(AnalysisRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [
        RunResultItem(
            job=job_item(job, analysis, application),
            analysis=analysis_out(analysis),
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
