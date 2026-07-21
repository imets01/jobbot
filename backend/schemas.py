"""Pydantic request and response schemas for the Jobbot API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationStatus(str, Enum):
    SAVED = "Saved"
    INTERESTED = "Interested"
    APPLIED = "Applied"
    INTERVIEWING = "Interviewing"
    OFFER = "Offer"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"
    ARCHIVED = "Archived"


class RunType(str, Enum):
    SCRAPER = "scraper"
    ANALYZER = "analyzer"
    FULL = "full"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    run_id: str
    created_at: datetime
    candidate_profile_snapshot: str
    candidate_profile_version: int
    is_good_match: bool | None
    seniority_ok: bool | None
    verdict: str
    gemini_model: str
    error_message: str | None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: ApplicationStatus
    application_date: date | None
    next_follow_up_date: date | None
    notes: str
    created_at: datetime
    updated_at: datetime


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus = ApplicationStatus.SAVED
    application_date: date | None = None
    next_follow_up_date: date | None = None
    notes: str = Field(default="", max_length=20_000)


class JobListItem(BaseModel):
    id: int
    title: str
    company: str
    url: str | None
    location: str | None
    source: str
    first_seen: datetime
    last_seen: datetime
    archived: bool
    latest_analysis: AnalysisResultOut | None = None
    application: ApplicationOut | None = None


class JobDetail(JobListItem):
    description: str
    content_hash: str
    analyses: list[AnalysisResultOut] = Field(default_factory=list)


class PaginatedJobs(BaseModel):
    items: list[JobListItem]
    page: int
    page_size: int
    total: int
    pages: int


class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content: str
    version: int
    updated_at: datetime
    is_default: bool


class CandidateProfileUpdate(BaseModel):
    content: str = Field(min_length=20, max_length=30_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Candidate profile cannot be empty")
        return cleaned


class RunRequest(BaseModel):
    role: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=200)
    max_jobs: int = Field(ge=1, le=100)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_type: RunType
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    jobs_discovered: int
    jobs_queued: int
    jobs_analyzed: int
    good_matches: int
    failures: int
    error_details: str | None


class PaginatedRuns(BaseModel):
    items: list[RunOut]
    page: int
    page_size: int
    total: int
    pages: int


class RunResultItem(BaseModel):
    job: JobListItem
    analysis: AnalysisResultOut


class ApplicationBoardItem(BaseModel):
    job: JobListItem
    application: ApplicationOut


class StatusCount(BaseModel):
    status: str
    count: int


class DashboardSummary(BaseModel):
    total_jobs: int
    good_matches: int
    waiting_for_analysis: int
    applications_submitted: int
    follow_ups_due: int
    recent_good_matches: list[JobListItem]
    application_statuses: list[StatusCount]
    active_run: RunOut | None


class ArchiveUpdate(BaseModel):
    archived: bool


class SettingsOut(BaseModel):
    default_role: str
    default_location: str
    default_max_jobs: int
    gemini_model: str
