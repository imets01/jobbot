"""Pydantic request and response schemas for the Jobbot API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_string_list(values: list[str]) -> list[str]:
    """Trim and deduplicate strings while preserving their order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


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
    SEARCH = "search"
    SCRAPER = "scraper"
    ANALYZER = "analyzer"
    FULL = "full"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LanguageEntry(BaseModel):
    language: str = Field(min_length=1, max_length=100)
    proficiency: str = Field(default="", max_length=100)


class MentionPreferences(BaseModel):
    education: bool = True
    certifications: bool = True
    internships: bool = True
    projects: bool = True
    customer_facing_experience: bool = True
    technical_skills: bool = True
    career_motivation: bool = True


class StructuredCandidateProfile(BaseModel):
    full_name: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=320)
    current_location: str = Field(default="", max_length=300)
    linkedin_url: str = Field(default="", max_length=1000)
    portfolio_url: str = Field(default="", max_length=1000)
    education: list[str] = Field(default_factory=list, max_length=100)
    work_experience: list[str] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=300)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    languages: list[LanguageEntry] = Field(default_factory=list, max_length=100)
    projects: list[str] = Field(default_factory=list, max_length=100)
    professional_summary: str = Field(default="", max_length=20_000)
    role_keywords: list[str] = Field(default_factory=list, max_length=100)
    preferred_seniority: str = Field(default="", max_length=200)
    preferred_industries: list[str] = Field(default_factory=list, max_length=100)
    preferred_locations: list[str] = Field(default_factory=list, max_length=100)
    work_model_preferences: list[str] = Field(default_factory=list, max_length=10)
    years_total_experience: float = Field(default=0, ge=0, le=80)
    years_software_engineering: float = Field(default=0, ge=0, le=80)
    years_cloud_experience: float = Field(default=0, ge=0, le=80)
    years_customer_facing: float = Field(default=0, ge=0, le=80)
    base_cover_letter: str = Field(default="", max_length=40_000)
    career_motivation: str = Field(default="", max_length=20_000)
    key_achievements: list[str] = Field(default_factory=list, max_length=100)
    projects_to_highlight: list[str] = Field(default_factory=list, max_length=100)
    writing_tone: str = Field(default="Professional", max_length=100)
    mention_preferences: MentionPreferences = Field(default_factory=MentionPreferences)

    @field_validator(
        "education",
        "work_experience",
        "skills",
        "certifications",
        "projects",
        "role_keywords",
        "preferred_industries",
        "preferred_locations",
        "work_model_preferences",
        "key_achievements",
        "projects_to_highlight",
    )
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean_string_list(value)


class SearchControls(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=30)
    target_locations: list[str] = Field(min_length=1, max_length=30)
    work_models: list[str] = Field(default_factory=list, max_length=10)
    minimum_match_score: int = Field(default=60, ge=0, le=100)
    number_of_jobs: int = Field(default=20, ge=1, le=100)
    include_stretch_roles: bool = False
    max_required_experience_years: float | None = Field(default=4, ge=0, le=80)
    exclude_unavailable_languages: bool = False
    exclude_outside_locations: bool = True
    sources: list[str] = Field(min_length=1, max_length=20)

    @field_validator("keywords", "target_locations", "work_models", "sources")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean_string_list(value)


class AnalysisResultOut(BaseModel):
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
    match_score: int | None = None
    qualifies: bool | None = None
    recommendation_label: str | None = None
    short_explanation: str = ""
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    matched_strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    potential_concerns: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    suggested_resume_keywords: list[str] = Field(default_factory=list)
    application_strategy: str = ""
    work_model: str | None = None
    required_experience_years: float | None = None
    required_languages: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)


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
    dismissed: bool = False
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


class CVDocumentOut(BaseModel):
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    extracted_at: datetime | None
    has_raw_text: bool


class CandidateProfileOut(BaseModel):
    profile: StructuredCandidateProfile
    version: int
    updated_at: datetime
    cv: CVDocumentOut | None = None


class CandidateProfileUpdate(BaseModel):
    profile: StructuredCandidateProfile


class CVExtractionOut(BaseModel):
    extracted_profile: StructuredCandidateProfile
    cv: CVDocumentOut


class SearchControlsOut(SearchControls):
    updated_at: datetime


class SearchSourceCapability(BaseModel):
    name: str
    available: bool
    note: str


class SearchRunRequest(BaseModel):
    controls: SearchControls | None = None


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


class DismissUpdate(BaseModel):
    dismissed: bool


class CoverLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    analysis_result_id: int | None
    candidate_profile_version: int
    content: str
    gemini_model: str
    created_at: datetime
    updated_at: datetime


class CoverLetterUpdate(BaseModel):
    content: str = Field(min_length=20, max_length=40_000)
