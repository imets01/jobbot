"""SQLAlchemy persistence models for jobs, analyses, runs, and applications."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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

    analyses: Mapped[list[AnalysisResult]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    application: Mapped[Application | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
