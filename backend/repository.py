"""Database repositories and idempotent import services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.orm import Session

from analyzer import CANDIDATE_PROFILE
from backend.dedup import dedup_key
from backend.models import (
    AnalysisResult,
    AnalysisRun,
    Application,
    CandidateProfile,
    Job,
    utc_now,
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
        profile = CandidateProfile(id=1, content=CANDIDATE_PROFILE.strip(), version=1)
        session.add(profile)
        session.flush()
    return profile


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

    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = int(session.scalar(count_statement) or 0)

    sort_columns = {
        "newest": Job.first_seen,
        "last_analyzed": AnalysisResult.created_at,
        "company": Job.company,
        "match_quality": case(
            (
                and_(
                    AnalysisResult.is_good_match.is_(True),
                    AnalysisResult.seniority_ok.is_(True),
                ),
                2,
            ),
            (AnalysisResult.seniority_ok.is_(True), 1),
            else_=0,
        ),
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
    profile = get_or_create_profile(session)
    waiting_ids = {job.id for job in jobs_needing_analysis(session, profile.content)}
    good_rows = [
        row
        for row in rows
        if row[1]
        and row[1].error_message is None
        and row[1].is_good_match
        and row[1].seniority_ok
    ]
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
