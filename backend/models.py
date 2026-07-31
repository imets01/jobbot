"""SQLAlchemy persistence models for jobs, analyses, runs, and applications."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False, default="Unknown")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="linkedin")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    analyses: Mapped[list[AnalysisResult]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    application: Mapped[Application | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    cover_letters: Mapped[list[CoverLetter]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    good_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    candidate_profile_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_good_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    seniority_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verdict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gemini_model: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    qualifies: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    recommendation_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    short_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    matched_strengths_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    weak_areas_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    potential_concerns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    missing_requirements_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    resume_keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    application_strategy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    work_model: Mapped[str | None] = mapped_column(String(30), nullable=True)
    required_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    required_languages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    critical_gaps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    job: Mapped[Job] = relationship(back_populates="analyses")
    run: Mapped[AnalysisRun] = relationship(back_populates="results")


Index("ix_analysis_results_job_created", AnalysisResult.job_id, AnalysisResult.created_at)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Saved", index=True)
    application_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    job: Mapped[Job] = relationship(back_populates="application")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CVDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SearchSettings(Base):
    __tablename__ = "search_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    target_locations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    work_models_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    minimum_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    number_of_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    include_stretch_roles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_required_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    exclude_unavailable_languages: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    exclude_outside_locations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default='["LinkedIn"]')
    greenhouse_boards_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    lever_sites_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="SET NULL"), nullable=True
    )
    candidate_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    gemini_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    job: Mapped[Job] = relationship(back_populates="cover_letters")


Index("ix_cover_letters_job_created", CoverLetter.job_id, CoverLetter.created_at)
