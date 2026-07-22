"""Database repositories and idempotent import services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import func, not_, or_, select
from sqlalchemy.orm import Session

from analyzer import CANDIDATE_PROFILE
from backend.dedup import dedup_key
from backend.models import (
    AnalysisResult,
    AnalysisRun,
    Application,
    CandidateProfile,
    CoverLetter,
    CVDocument,
    Job,
    SearchSettings,
    utc_now,
)
from backend.profile_service import (
    DEFAULT_PROFILE,
    DEFAULT_SEARCH_SETTINGS,
    build_profile_snapshot,
    initial_profile_from_legacy,
    json_dict,
    json_list,
    render_profile_text,
)


@dataclass(slots=True)
class ImportStats:
    files_seen: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    files_failed: int = 0
    job_ids: list[int] | None = None

    def __post_init__(self) -> None:
        if self.job_ids is None:
            self.job_ids = []


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return utc_now()


def upsert_job(session: Session, payload: dict[str, Any]) -> tuple[Job, bool]:
    """Insert or refresh a job using deterministic URL-first deduplication."""
    title = str(payload.get("title") or "Untitled job").strip()
    company = str(payload.get("company") or "Unknown").strip()
    url = str(payload.get("link") or payload.get("url") or "").strip() or None
    description = str(payload.get("description") or "").strip()
    location = str(
        payload.get("location") or payload.get("location_query") or ""
    ).strip() or None
    source = str(payload.get("source") or "linkedin").strip().casefold()
    key, normalized_url, hash_value = dedup_key(
        url, title, company, location, description
    )
    seen_at = _parse_timestamp(payload.get("scraped_at"))

    job = session.scalar(select(Job).where(Job.dedup_key == key))
    created = job is None
    if job is None:
        job = Job(
            title=title,
            company=company,
            url=url,
            normalized_url=normalized_url,
            description=description,
            location=location,
            source=source,
            first_seen=seen_at,
            last_seen=seen_at,
            content_hash=hash_value,
            dedup_key=key,
        )
        session.add(job)
        session.flush()
        return job, True

    # Refresh mutable content while preserving first_seen and history.
    job.title = title or job.title
    job.company = company or job.company
    job.url = url or job.url
    job.normalized_url = normalized_url or job.normalized_url
    if description:
        job.description = description
    job.location = location or job.location
    job.source = source or job.source
    job.content_hash = hash_value
    if job.last_seen is None:
        job.last_seen = seen_at
    else:
        # SQLite can return a naive datetime even for timezone=True columns.
        # Compare POSIX timestamps so imports remain safe and idempotent.
        previous = (
            job.last_seen.replace(tzinfo=timezone.utc)
            if job.last_seen.tzinfo is None
            else job.last_seen
        )
        candidate = (
            seen_at.replace(tzinfo=timezone.utc)
            if seen_at.tzinfo is None
            else seen_at
        )
        if candidate.timestamp() > previous.timestamp():
            job.last_seen = seen_at
    session.flush()
    return job, created


def import_json_files(session: Session, paths: Iterable[Path]) -> ImportStats:
    """Idempotently import scraped JSON files into SQLite."""
    stats = ImportStats()
    seen_job_ids: set[int] = set()
    for path in paths:
        stats.files_seen += 1
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            job, created = upsert_job(session, payload)
            if created:
                stats.jobs_created += 1
            else:
                stats.jobs_updated += 1
            if job.id not in seen_job_ids:
                stats.job_ids.append(job.id)
                seen_job_ids.add(job.id)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            stats.files_failed += 1
    session.flush()
    return stats


def import_data_directory(session: Session, data_dir: Path) -> ImportStats:
    """Import all existing scraper files. Safe to call on every startup."""
    if not data_dir.exists():
        return ImportStats()
    return import_json_files(session, sorted(data_dir.glob("job_*.json")))


def get_or_create_profile(session: Session) -> CandidateProfile:
    profile = session.get(CandidateProfile, 1)
    if profile is None:
        structured = initial_profile_from_legacy(CANDIDATE_PROFILE)
        profile = CandidateProfile(
            id=1,
            content=render_profile_text(structured),
            structured_json=json.dumps(structured, ensure_ascii=False, sort_keys=True),
            version=1,
        )
        session.add(profile)
        session.flush()
    elif not json_dict(profile.structured_json):
        structured = initial_profile_from_legacy(profile.content)
        profile.structured_json = json.dumps(
            structured, ensure_ascii=False, sort_keys=True
        )
        profile.content = render_profile_text(structured)
        session.flush()
    return profile


def get_structured_profile(session: Session) -> dict[str, Any]:
    profile = get_or_create_profile(session)
    return json_dict(profile.structured_json, DEFAULT_PROFILE)


def update_structured_profile(
    session: Session, structured: dict[str, Any]
) -> CandidateProfile:
    profile = get_or_create_profile(session)
    encoded = json.dumps(structured, ensure_ascii=False, sort_keys=True)
    if profile.structured_json != encoded:
        profile.structured_json = encoded
        profile.content = render_profile_text(structured)
        profile.version += 1
        profile.updated_at = utc_now()
        session.flush()
    return profile


def reset_structured_profile(session: Session) -> CandidateProfile:
    return update_structured_profile(
        session, json.loads(json.dumps(DEFAULT_PROFILE))
    )


def update_profile(session: Session, content: str) -> CandidateProfile:
    profile = get_or_create_profile(session)
    cleaned = content.strip()
    if profile.content != cleaned:
        profile.content = cleaned
        profile.version += 1
        profile.updated_at = utc_now()
        session.flush()
    return profile


def reset_profile(session: Session) -> CandidateProfile:
    return update_profile(session, CANDIDATE_PROFILE.strip())


def get_cv_document(session: Session) -> CVDocument | None:
    return session.get(CVDocument, 1)


def upsert_cv_document(
    session: Session,
    *,
    original_name: str,
    content_type: str,
    storage_path: str,
    size_bytes: int,
    raw_text: str,
) -> CVDocument:
    document = get_cv_document(session)
    if document is None:
        document = CVDocument(
            id=1,
            original_name=original_name,
            content_type=content_type,
            storage_path=storage_path,
            size_bytes=size_bytes,
            raw_text=raw_text,
        )
        session.add(document)
    else:
        document.original_name = original_name
        document.content_type = content_type
        document.storage_path = storage_path
        document.size_bytes = size_bytes
        document.raw_text = raw_text
        document.extracted_json = "{}"
        document.uploaded_at = utc_now()
        document.extracted_at = None
    session.flush()
    return document


def get_or_create_search_settings(session: Session) -> SearchSettings:
    settings = session.get(SearchSettings, 1)
    if settings is None:
        defaults = DEFAULT_SEARCH_SETTINGS
        settings = SearchSettings(
            id=1,
            keywords_json=json.dumps(defaults["keywords"]),
            target_locations_json=json.dumps(defaults["target_locations"]),
            work_models_json=json.dumps(defaults["work_models"]),
            minimum_match_score=defaults["minimum_match_score"],
            number_of_jobs=defaults["number_of_jobs"],
            include_stretch_roles=defaults["include_stretch_roles"],
            max_required_experience_years=defaults[
                "max_required_experience_years"
            ],
            exclude_unavailable_languages=defaults[
                "exclude_unavailable_languages"
            ],
            exclude_outside_locations=defaults["exclude_outside_locations"],
            sources_json=json.dumps(defaults["sources"]),
        )
        session.add(settings)
        session.flush()
    return settings


def search_settings_dict(settings: SearchSettings) -> dict[str, Any]:
    return {
        "keywords": json_list(settings.keywords_json),
        "target_locations": json_list(settings.target_locations_json),
        "work_models": json_list(settings.work_models_json),
        "minimum_match_score": settings.minimum_match_score,
        "number_of_jobs": settings.number_of_jobs,
        "include_stretch_roles": settings.include_stretch_roles,
        "max_required_experience_years": settings.max_required_experience_years,
        "exclude_unavailable_languages": settings.exclude_unavailable_languages,
        "exclude_outside_locations": settings.exclude_outside_locations,
        "sources": json_list(settings.sources_json),
    }


def update_search_settings(
    session: Session, values: dict[str, Any]
) -> SearchSettings:
    settings = get_or_create_search_settings(session)
    settings.keywords_json = json.dumps(values["keywords"], ensure_ascii=False)
    settings.target_locations_json = json.dumps(
        values["target_locations"], ensure_ascii=False
    )
    settings.work_models_json = json.dumps(values["work_models"], ensure_ascii=False)
    settings.minimum_match_score = int(values["minimum_match_score"])
    settings.number_of_jobs = int(values["number_of_jobs"])
    settings.include_stretch_roles = bool(values["include_stretch_roles"])
    settings.max_required_experience_years = values[
        "max_required_experience_years"
    ]
    settings.exclude_unavailable_languages = bool(
        values["exclude_unavailable_languages"]
    )
    settings.exclude_outside_locations = bool(values["exclude_outside_locations"])
    settings.sources_json = json.dumps(values["sources"], ensure_ascii=False)
    settings.updated_at = utc_now()
    session.flush()
    return settings


def latest_analysis_id_subquery():
    return (
        select(func.max(AnalysisResult.id))
        .where(AnalysisResult.job_id == Job.id)
        .correlate(Job)
        .scalar_subquery()
    )


def _job_rows_statement():
    latest_id = latest_analysis_id_subquery()
    return (
        select(Job, AnalysisResult, Application)
        .outerjoin(AnalysisResult, AnalysisResult.id == latest_id)
        .outerjoin(Application, Application.job_id == Job.id)
    )


def list_jobs(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    match: str | None = None,
    seniority: str | None = None,
    analyzed: str | None = None,
    application_status: str | None = None,
    company: str | None = None,
    archived: str = "active",
    dismissed: str = "active",
    minimum_score: int | None = None,
    sort: str = "newest",
    direction: str = "desc",
) -> tuple[list[tuple[Job, AnalysisResult | None, Application | None]], int]:
    """List unique jobs with latest analysis/application and rich filters."""
    statement = _job_rows_statement()

    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(Job.title.ilike(term), Job.company.ilike(term))
        )
    if match == "good":
        statement = statement.where(
            AnalysisResult.is_good_match.is_(True),
            AnalysisResult.seniority_ok.is_(True),
            AnalysisResult.error_message.is_(None),
        )
    elif match == "not":
        statement = statement.where(
            AnalysisResult.id.is_not(None),
            or_(
                AnalysisResult.is_good_match.is_not(True),
                AnalysisResult.seniority_ok.is_not(True),
                AnalysisResult.error_message.is_not(None),
            ),
        )
    if seniority == "suitable":
        statement = statement.where(AnalysisResult.seniority_ok.is_(True))
    elif seniority == "unsuitable":
        statement = statement.where(AnalysisResult.seniority_ok.is_(False))
    if analyzed == "yes":
        statement = statement.where(AnalysisResult.id.is_not(None))
    elif analyzed == "no":
        statement = statement.where(AnalysisResult.id.is_(None))
    if application_status:
        statement = statement.where(Application.status == application_status)
    if company:
        statement = statement.where(Job.company == company)
    if archived == "active":
        statement = statement.where(Job.archived.is_(False))
    elif archived == "archived":
        statement = statement.where(Job.archived.is_(True))
    if dismissed == "active":
        statement = statement.where(Job.dismissed.is_(False))
    elif dismissed == "dismissed":
        statement = statement.where(Job.dismissed.is_(True))
    if minimum_score is not None:
        statement = statement.where(
            AnalysisResult.error_message.is_(None),
            AnalysisResult.qualifies.is_(True),
            AnalysisResult.match_score >= minimum_score,
        )

    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = int(session.scalar(count_statement) or 0)

    sort_columns = {
        "newest": Job.first_seen,
        "last_analyzed": AnalysisResult.created_at,
        "company": Job.company,
        "match_quality": AnalysisResult.match_score,
    }
    sort_column = sort_columns.get(sort, Job.first_seen)
    ordered = sort_column.asc() if direction == "asc" else sort_column.desc()
    statement = statement.order_by(ordered, Job.id.desc())
    statement = statement.offset((page - 1) * page_size).limit(page_size)
    rows = list(session.execute(statement).all())
    return rows, total


def get_job_row(
    session: Session, job_id: int
) -> tuple[Job, AnalysisResult | None, Application | None] | None:
    return session.execute(
        _job_rows_statement().where(Job.id == job_id)
    ).one_or_none()


def get_job_analyses(session: Session, job_id: int) -> list[AnalysisResult]:
    return list(
        session.scalars(
            select(AnalysisResult)
            .where(AnalysisResult.job_id == job_id)
            .order_by(AnalysisResult.created_at.desc(), AnalysisResult.id.desc())
        )
    )


def get_or_update_application(
    session: Session,
    job: Job,
    *,
    status: str,
    application_date: date | None,
    next_follow_up_date: date | None,
    notes: str,
) -> Application:
    application = job.application or session.scalar(
        select(Application).where(Application.job_id == job.id)
    )
    if application is None:
        application = Application(job=job)
        session.add(application)
    application.status = status
    application.application_date = application_date
    application.next_follow_up_date = next_follow_up_date
    application.notes = notes
    application.updated_at = utc_now()
    job.archived = status == "Archived"
    session.flush()
    return application


def set_job_archived(
    session: Session,
    job: Job,
    archived: bool,
) -> Application | None:
    """Keep the job archive flag and application workflow status in sync."""
    application = job.application or session.scalar(
        select(Application).where(Application.job_id == job.id)
    )
    job.archived = archived

    if archived:
        if application is None:
            application = Application(job=job, status="Archived")
            session.add(application)
        else:
            application.status = "Archived"
            application.updated_at = utc_now()
    elif application is not None and application.status == "Archived":
        application.status = "Saved"
        application.updated_at = utc_now()

    session.flush()
    return application


def set_job_dismissed(session: Session, job: Job, dismissed: bool) -> Job:
    job.dismissed = dismissed
    session.flush()
    return job


def jobs_needing_analysis(
    session: Session,
    profile_snapshot: str,
    job_ids: list[int] | None = None,
) -> list[Job]:
    """Return active jobs without a successful analysis for this exact profile."""
    successful_analysis_exists = (
        select(AnalysisResult.id)
        .where(
            AnalysisResult.job_id == Job.id,
            AnalysisResult.candidate_profile_snapshot == profile_snapshot,
            AnalysisResult.error_message.is_(None),
        )
        .exists()
    )
    statement = select(Job).where(
        Job.archived.is_(False), not_(successful_analysis_exists)
    )
    if job_ids is not None:
        if not job_ids:
            return []
        statement = statement.where(Job.id.in_(job_ids))
    return list(session.scalars(statement.order_by(Job.last_seen.desc())))


def list_companies(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(Job.company)
            .where(Job.archived.is_(False))
            .distinct()
            .order_by(Job.company.asc())
        )
    )


def list_applications(
    session: Session,
) -> list[tuple[Job, AnalysisResult | None, Application]]:
    latest_id = latest_analysis_id_subquery()
    statement = (
        select(Job, AnalysisResult, Application)
        .join(Application, Application.job_id == Job.id)
        .outerjoin(AnalysisResult, AnalysisResult.id == latest_id)
        .order_by(Application.updated_at.desc())
    )
    return list(session.execute(statement).all())


def create_run(
    session: Session,
    run_id: str,
    run_type: str,
    parameters: dict[str, Any],
) -> AnalysisRun:
    run = AnalysisRun(
        id=run_id,
        run_type=run_type,
        status="pending",
        parameters_json=json.dumps(parameters),
    )
    session.add(run)
    session.flush()
    return run


def list_runs(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    run_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[AnalysisRun], int]:
    statement = select(AnalysisRun)
    if run_type:
        statement = statement.where(AnalysisRun.run_type == run_type)
    if status:
        statement = statement.where(AnalysisRun.status == status)
    if date_from:
        statement = statement.where(AnalysisRun.created_at >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc))
    if date_to:
        statement = statement.where(AnalysisRun.created_at <= datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc))
    total = int(
        session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    )
    runs = list(
        session.scalars(
            statement.order_by(AnalysisRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return runs, total


def get_run_results(
    session: Session, run_id: str
) -> list[tuple[Job, AnalysisResult, Application | None]]:
    return list(
        session.execute(
            select(Job, AnalysisResult, Application)
            .join(AnalysisResult, AnalysisResult.job_id == Job.id)
            .outerjoin(Application, Application.job_id == Job.id)
            .where(AnalysisResult.run_id == run_id)
            .order_by(AnalysisResult.created_at.desc())
        ).all()
    )


def latest_cover_letter(session: Session, job_id: int) -> CoverLetter | None:
    return session.scalar(
        select(CoverLetter)
        .where(CoverLetter.job_id == job_id)
        .order_by(CoverLetter.created_at.desc(), CoverLetter.id.desc())
    )


def create_cover_letter(
    session: Session,
    *,
    job_id: int,
    analysis_result_id: int | None,
    profile_version: int,
    content: str,
    model: str,
) -> CoverLetter:
    letter = CoverLetter(
        job_id=job_id,
        analysis_result_id=analysis_result_id,
        candidate_profile_version=profile_version,
        content=content,
        gemini_model=model,
    )
    session.add(letter)
    session.flush()
    return letter


def update_cover_letter_content(
    session: Session, letter: CoverLetter, content: str
) -> CoverLetter:
    letter.content = content.strip()
    letter.updated_at = utc_now()
    session.flush()
    return letter


def active_run(session: Session) -> AnalysisRun | None:
    return session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.status.in_(("pending", "running")))
        .order_by(AnalysisRun.created_at.desc())
    )


def dashboard_data(session: Session) -> dict[str, Any]:
    """Compute dashboard aggregates from unique jobs and latest analyses."""
    rows = list(
        session.execute(
            _job_rows_statement()
            .where(Job.archived.is_(False))
            .order_by(Job.last_seen.desc())
        ).all()
    )
    settings = get_or_create_search_settings(session)
    cv = get_cv_document(session)
    profile_snapshot = build_profile_snapshot(
        get_structured_profile(session),
        search_settings_dict(settings),
        cv.raw_text if cv else "",
    )
    waiting_ids = {job.id for job in jobs_needing_analysis(session, profile_snapshot)}
    good_rows = [
        row
        for row in rows
        if row[1]
        and row[1].error_message is None
        and row[1].qualifies
        and (row[1].match_score or 0) >= settings.minimum_match_score
        and not row[0].dismissed
    ]
    good_rows.sort(key=lambda row: row[1].match_score or 0, reverse=True)
    submitted_statuses = {"Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"}
    today = date.today()
    applications = [row[2] for row in rows if row[2] is not None]
    follow_up_active = {"Interested", "Applied", "Interviewing", "Offer"}

    status_counts: dict[str, int] = {}
    for application in applications:
        status_counts[application.status] = status_counts.get(application.status, 0) + 1

    return {
        "total_jobs": len(rows),
        "good_matches": len(good_rows),
        "waiting_for_analysis": len(waiting_ids),
        "applications_submitted": sum(
            application.status in submitted_statuses for application in applications
        ),
        "follow_ups_due": sum(
            application.next_follow_up_date is not None
            and application.next_follow_up_date <= today
            and application.status in follow_up_active
            for application in applications
        ),
        "recent_good_matches": good_rows[:6],
        "application_statuses": [
            {"status": status, "count": count}
            for status, count in sorted(status_counts.items())
        ],
        "active_run": active_run(session),
    }
