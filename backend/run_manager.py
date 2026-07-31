"""Single-process background run coordinator for scraping and Gemini analysis."""

from __future__ import annotations

import threading
import time
import traceback
import uuid
import json
import math
from typing import Any

from sqlalchemy import select

import config
from analyzer import analyze_job, build_client
from backend.database import SessionLocal, session_scope
from backend.models import AnalysisResult, AnalysisRun, Job, utc_now
from backend.repository import (
    active_run,
    create_run,
    get_cv_document,
    get_or_create_profile,
    get_or_create_search_settings,
    get_structured_profile,
    import_json_files,
    jobs_needing_analysis,
    search_settings_dict,
)
from backend.profile_service import (
    build_analysis_context,
    build_profile_snapshot,
    profile_for_search,
)
from backend.sources import DiscoveryRequest, get_source_adapter
from scraper import scrape_jobs


class RunConflictError(RuntimeError):
    """Raised when a second pipeline is requested while one is active."""


class RunManager:
    """Run scraper/analyzer work in one guarded background thread.

    The application is intentionally local-first and should be started with one
    Uvicorn worker. The database still records every transition, while the
    in-process lock prevents accidental duplicate runs from repeated UI clicks.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_run_id: str | None = None

    def recover_stale_runs(self) -> None:
        """Mark interrupted pending/running runs as failed after a restart."""
        with session_scope() as session:
            runs = list(
                session.scalars(
                    select(AnalysisRun).where(
                        AnalysisRun.status.in_(("pending", "running"))
                    )
                )
            )
            for run in runs:
                run.status = "failed"
                run.ended_at = utc_now()
                run.error_details = "Application restarted before this run completed."

    def start(
        self,
        run_type: str,
        parameters: dict[str, Any],
        *,
        job_id: int | None = None,
    ) -> AnalysisRun:
        """Create and launch a run, rejecting concurrent duplicate work."""
        with self._lock:
            with session_scope() as session:
                running = active_run(session)
                if self._active_run_id or running:
                    active_id = self._active_run_id or (running.id if running else "unknown")
                    raise RunConflictError(
                        f"Run {active_id} is already pending or running."
                    )
                run_id = str(uuid.uuid4())
                payload = dict(parameters)
                if job_id is not None:
                    payload["job_id"] = job_id
                run = create_run(session, run_id, run_type, payload)
                self._active_run_id = run_id

            thread = threading.Thread(
                target=self._execute,
                args=(run_id, run_type, payload),
                name=f"jobbot-{run_type}-{run_id[:8]}",
                daemon=True,
            )
            thread.start()
            return run

    def _execute(
        self,
        run_id: str,
        run_type: str,
        parameters: dict[str, Any],
    ) -> None:
        self._update_run(
            run_id,
            status="running",
            started_at=utc_now(),
            error_details=None,
        )
        try:
            if run_type == "scraper":
                self._scrape(run_id, parameters)
            elif run_type == "analyzer":
                requested_job_id = parameters.get("job_id")
                self._analyze(
                    run_id,
                    job_ids=[int(requested_job_id)] if requested_job_id else None,
                    force=bool(requested_job_id),
                )
            elif run_type in {"search", "full"}:
                job_ids = self._scrape(run_id, parameters)
                self._analyze(run_id, job_ids=job_ids, force=False)
            else:
                raise ValueError(f"Unsupported run type: {run_type}")

            self._update_run(run_id, status="completed", ended_at=utc_now())
        except Exception as exc:  # noqa: BLE001 - persist background failures
            details = f"{type(exc).__name__}: {exc}"
            self._update_run(
                run_id,
                status="failed",
                ended_at=utc_now(),
                error_details=details[:20_000],
            )
            traceback.print_exc()
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None

    def _scrape(self, run_id: str, parameters: dict[str, Any]) -> list[int]:
        controls = parameters.get("search_controls")
        paths = []
        source_errors: list[str] = []
        successful_sources = 0
        if controls:
            sources = [str(value) for value in controls.get("sources", [])]
            keywords = [str(value) for value in controls.get("keywords", [])]
            locations = [str(value) for value in controls.get("target_locations", [])]
            work_models = [str(value) for value in controls.get("work_models", [])]
            if not sources or not keywords or not locations:
                raise ValueError(
                    "At least one source, keyword, and target location are required."
                )
            discovery_budget = min(
                100,
                max(25, int(controls.get("number_of_jobs", config.MAX_JOBS)) * 3),
            )
            per_source = max(1, math.ceil(discovery_budget / len(sources)))
            for source_name in sources:
                try:
                    adapter = get_source_adapter(source_name)
                    targets = (
                        [str(value) for value in controls.get(adapter.target_field, [])]
                        if adapter.target_field
                        else []
                    )
                    result = adapter.discover(
                        DiscoveryRequest(
                            keywords=keywords,
                            locations=locations,
                            work_models=work_models,
                            max_jobs=per_source,
                            targets=targets,
                            data_dir=config.ensure_data_dir(),
                        )
                    )
                    paths.extend(result.paths)
                    source_errors.extend(
                        f"{adapter.name}: {message}" for message in result.errors
                    )
                    if result.completed_targets > 0 or not result.errors:
                        successful_sources += 1
                except Exception as exc:
                    source_errors.append(
                        f"{source_name}: {type(exc).__name__}: {exc}"
                    )
        else:
            paths = scrape_jobs(
                role=str(parameters.get("role") or config.DEFAULT_ROLE),
                location=str(parameters.get("location") or config.DEFAULT_LOCATION),
                max_jobs=int(parameters.get("max_jobs") or config.MAX_JOBS),
            )
        with session_scope() as session:
            stats = import_json_files(session, paths)
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise RuntimeError(f"Run {run_id} disappeared")
            run.jobs_discovered = len(stats.job_ids)
            run.failures += stats.files_failed + len(source_errors)
            if source_errors:
                run.error_details = "Source warnings:\n" + "\n".join(source_errors)
            job_ids = list(stats.job_ids)

        if controls and successful_sources == 0:
            details = "; ".join(source_errors) or "No source completed discovery."
            raise RuntimeError(f"All selected search sources failed: {details}")
        return job_ids

    def _analyze(
        self,
        run_id: str,
        *,
        job_ids: list[int] | None,
        force: bool,
    ) -> None:
        with session_scope() as session:
            profile = get_or_create_profile(session)
            structured_profile = get_structured_profile(session)
            stored_settings = get_or_create_search_settings(session)
            settings = parameters_settings = None
            run = session.get(AnalysisRun, run_id)
            if run is not None:
                try:
                    run_parameters = json.loads(run.parameters_json or "{}")
                    parameters_settings = run_parameters.get("search_controls")
                except (json.JSONDecodeError, TypeError):
                    parameters_settings = None
            settings = parameters_settings or search_settings_dict(stored_settings)
            structured_profile = profile_for_search(structured_profile, settings)
            cv = get_cv_document(session)
            raw_cv_text = cv.raw_text if cv else ""
            profile_snapshot = build_profile_snapshot(
                structured_profile,
                settings,
                raw_cv_text,
            )
            analysis_context = build_analysis_context(
                structured_profile,
                settings,
                raw_cv_text,
            )
            profile_version = profile.version
            if force and job_ids:
                jobs = list(
                    session.scalars(
                        select(Job)
                        .where(Job.id.in_(job_ids), Job.archived.is_(False))
                        .order_by(Job.last_seen.desc())
                    )
                )
            else:
                jobs = jobs_needing_analysis(
                    session,
                    profile_snapshot,
                    job_ids=job_ids,
                )
            payloads = [
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "link": job.url,
                    "description": job.description,
                    "location": job.location,
                }
                for job in jobs
            ]
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise RuntimeError(f"Run {run_id} disappeared")
            run.jobs_queued = len(payloads)

        if not payloads:
            return

        client = build_client()
        for index, payload in enumerate(payloads):
            if index > 0 and config.ANALYZER_DELAY_SECONDS > 0:
                time.sleep(config.ANALYZER_DELAY_SECONDS)

            evaluation: dict[str, Any] | None = None
            error_message: str | None = None
            try:
                evaluation = analyze_job(
                    client,
                    payload,
                    candidate_profile=analysis_context,
                )
                evaluation["job_location"] = payload.get("location")
            except Exception as exc:  # noqa: BLE001 - persist per-job API errors
                error_message = f"{type(exc).__name__}: {exc}"[:20_000]

            with session_scope() as session:
                qualifies = (
                    self._qualifies(evaluation, structured_profile, settings)
                    if evaluation
                    else None
                )
                result = AnalysisResult(
                    job_id=int(payload["id"]),
                    run_id=run_id,
                    candidate_profile_snapshot=profile_snapshot,
                    candidate_profile_version=profile_version,
                    is_good_match=(
                        bool(evaluation["is_good_match"]) if evaluation else None
                    ),
                    seniority_ok=(
                        bool(evaluation["seniority_ok"]) if evaluation else None
                    ),
                    verdict=str(evaluation["verdict"]) if evaluation else "",
                    gemini_model=config.GEMINI_MODEL,
                    error_message=error_message,
                    match_score=(int(evaluation["match_score"]) if evaluation else None),
                    qualifies=qualifies,
                    recommendation_label=(
                        str(evaluation["recommendation_label"]) if evaluation else None
                    ),
                    short_explanation=(
                        str(evaluation["short_explanation"]) if evaluation else ""
                    ),
                    score_breakdown_json=json.dumps(
                        evaluation["score_breakdown"] if evaluation else {}
                    ),
                    matched_strengths_json=json.dumps(
                        evaluation["matched_strengths"] if evaluation else []
                    ),
                    weak_areas_json=json.dumps(
                        evaluation["weak_areas"] if evaluation else []
                    ),
                    potential_concerns_json=json.dumps(
                        evaluation["potential_concerns"] if evaluation else []
                    ),
                    missing_requirements_json=json.dumps(
                        evaluation["missing_requirements"] if evaluation else []
                    ),
                    resume_keywords_json=json.dumps(
                        evaluation["suggested_resume_keywords"] if evaluation else []
                    ),
                    application_strategy=(
                        str(evaluation["application_strategy"]) if evaluation else ""
                    ),
                    work_model=(str(evaluation["work_model"]) if evaluation else None),
                    required_experience_years=(
                        float(evaluation["required_experience_years"])
                        if evaluation
                        else None
                    ),
                    required_languages_json=json.dumps(
                        evaluation["required_languages"] if evaluation else []
                    ),
                    critical_gaps_json=json.dumps(
                        evaluation["critical_gaps"] if evaluation else []
                    ),
                )
                session.add(result)
                run = session.get(AnalysisRun, run_id)
                if run is None:
                    raise RuntimeError(f"Run {run_id} disappeared")
                run.jobs_analyzed += 1
                if error_message:
                    run.failures += 1
                elif qualifies:
                    run.good_matches += 1

    @staticmethod
    def _qualifies(
        evaluation: dict[str, Any],
        profile: dict[str, Any],
        settings: dict[str, Any],
    ) -> bool:
        """Apply deterministic threshold and explicit hard-filter controls."""
        if int(evaluation.get("match_score", 0)) < int(
            settings.get("minimum_match_score", 60)
        ):
            return False
        if not settings.get("include_stretch_roles", False):
            if not evaluation.get("seniority_ok", False) or evaluation.get("critical_gaps"):
                return False

        maximum_years = settings.get("max_required_experience_years")
        required_years = float(evaluation.get("required_experience_years", 0) or 0)
        if maximum_years is not None and required_years > float(maximum_years):
            return False

        allowed_models = {
            str(value).casefold() for value in settings.get("work_models", [])
        }
        work_model = str(evaluation.get("work_model") or "Unknown").casefold()
        if allowed_models and work_model not in {"unknown", "flexible"}:
            if work_model not in allowed_models:
                return False

        if settings.get("exclude_unavailable_languages"):
            available = {
                str(item.get("language", "")).casefold()
                for item in profile.get("languages", [])
                if isinstance(item, dict) and item.get("language")
            }
            required = {
                str(value).casefold()
                for value in evaluation.get("required_languages", [])
            }
            for requirement in required:
                if not any(
                    language in requirement or requirement in language
                    for language in available
                ):
                    return False

        if settings.get("exclude_outside_locations"):
            target_locations = [
                str(value).casefold()
                for value in settings.get("target_locations", [])
            ]
            job_location = str(evaluation.get("job_location") or "").casefold()
            if job_location and target_locations:
                if not any(
                    target in job_location or job_location in target
                    for target in target_locations
                ):
                    return False
        return True

    @staticmethod
    def _update_run(run_id: str, **values: Any) -> None:
        with session_scope() as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise RuntimeError(f"Run {run_id} not found")
            for key, value in values.items():
                setattr(run, key, value)


run_manager = RunManager()
