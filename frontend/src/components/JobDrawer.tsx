import {
  Archive,
  CalendarDays,
  Clipboard,
  ExternalLink,
  FileText,
  History,
  RotateCcw,
  Save,
  ThumbsDown,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ApplicationStatus, CoverLetter, JobDetail } from "../types";
import { APPLICATION_STATUSES, formatDate, todayInput } from "../utils";
import { useToast } from "./ToastProvider";
import { ApplicationBadge, ErrorState, LoadingState, MatchBadges } from "./Ui";

const SCORE_MAXIMUMS: Record<string, number> = {
  role_title_alignment: 15,
  skills_match: 20,
  experience_level_match: 15,
  location_match: 10,
  work_model_match: 5,
  education_match: 5,
  certification_match: 5,
  language_match: 5,
  career_goal_alignment: 10,
  cover_letter_relevance: 5,
  critical_requirements: 5,
};

export function JobDrawer({
  jobId,
  analysisId,
  onClose,
  onChanged,
}: {
  jobId: number | null;
  analysisId?: number | null;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<ApplicationStatus>("Saved");
  const [applicationDate, setApplicationDate] = useState("");
  const [followUpDate, setFollowUpDate] = useState("");
  const [notes, setNotes] = useState("");
  const [coverLetter, setCoverLetter] = useState<CoverLetter | null>(null);
  const [coverDraft, setCoverDraft] = useState("");
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [savingLetter, setSavingLetter] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);
  const { showToast } = useToast();

  const load = async () => {
    if (jobId === null) return;
    setLoading(true);
    setError("");
    try {
      const [value, letter] = await Promise.all([api.job(jobId), api.coverLetter(jobId)]);
      setJob(value);
      setCoverLetter(letter);
      setCoverDraft(letter?.content ?? "");
      setStatus(value.application?.status ?? "Saved");
      setApplicationDate(value.application?.application_date ?? "");
      setFollowUpDate(value.application?.next_follow_up_date ?? "");
      setNotes(value.application?.notes ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load job");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (jobId === null) return;
    void load();
    restoreFocus.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    document.body.classList.add("drawer-open");
    window.setTimeout(() => closeButton.current?.focus(), 40);
    const handleKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawer.current) return;
      const focusable = Array.from(
        drawer.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), details > summary, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.getClientRects().length > 0);
      if (!focusable.length) {
        event.preventDefault();
        closeButton.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyboard);
    return () => {
      document.body.classList.remove("drawer-open");
      window.removeEventListener("keydown", handleKeyboard);
      restoreFocus.current?.focus();
    };
  }, [jobId]);

  if (jobId === null) return null;

  const saveApplication = async () => {
    setSaving(true);
    try {
      await api.saveApplication(jobId, {
        status,
        application_date: applicationDate || null,
        next_follow_up_date: followUpDate || null,
        notes,
      });
      showToast("Application details saved", "success");
      await load();
      onChanged?.();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not save application", "error");
    } finally {
      setSaving(false);
    }
  };

  const stopTracking = async () => {
    if (!job?.application) return;
    const hasDetails = Boolean(notes.trim() || applicationDate || followUpDate);
    if (hasDetails && !window.confirm("Stop tracking this job and delete its application notes and dates?")) return;
    setSaving(true);
    try {
      await api.untrackApplication(job.id);
      showToast("Job removed from the application board", "success");
      await load();
      onChanged?.();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not remove application tracking", "error");
    } finally {
      setSaving(false);
    }
  };

  const reanalyze = async () => {
    try {
      await api.reanalyze(jobId);
      showToast("Reanalysis queued", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not start reanalysis", "error");
    }
  };

  const toggleArchive = async () => {
    if (!job) return;
    try {
      await api.archiveJob(job.id, !job.archived);
      showToast(job.archived ? "Job restored" : "Job archived", "success");
      await load();
      onChanged?.();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not update archive", "error");
    }
  };

  const toggleDismiss = async () => {
    if (!job) return;
    try {
      await api.dismissJob(job.id, !job.dismissed);
      showToast(job.dismissed ? "Match restored" : "Match dismissed", "success");
      await load();
      onChanged?.();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not update match", "error");
    }
  };

  const generateLetter = async () => {
    if (!job) return;
    setGeneratingLetter(true);
    try {
      const letter = await api.generateCoverLetter(job.id);
      setCoverLetter(letter);
      setCoverDraft(letter.content);
      showToast("Tailored cover letter generated", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not generate cover letter", "error");
    } finally {
      setGeneratingLetter(false);
    }
  };

  const saveLetter = async () => {
    if (!job || !coverLetter) return;
    setSavingLetter(true);
    try {
      const letter = await api.saveCoverLetter(job.id, coverLetter.id, coverDraft);
      setCoverLetter(letter);
      setCoverDraft(letter.content);
      showToast("Cover letter saved", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not save cover letter", "error");
    } finally {
      setSavingLetter(false);
    }
  };

  const copyLetter = async () => {
    try {
      await navigator.clipboard.writeText(coverDraft);
      showToast("Cover letter copied", "success");
    } catch {
      showToast("The browser could not copy the cover letter", "error");
    }
  };

  const displayedAnalysis = analysisId
    ? job?.analyses.find((analysis) => analysis.id === analysisId) ?? job?.latest_analysis
    : job?.latest_analysis;
  const showingHistoricalAnalysis = Boolean(
    displayedAnalysis
    && job?.latest_analysis
    && displayedAnalysis.id !== job.latest_analysis.id,
  );
  const displayJob = job ? { ...job, latest_analysis: displayedAnalysis ?? null } : null;

  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside ref={drawer} className="job-drawer" role="dialog" aria-modal="true" aria-labelledby="job-drawer-title">
        <div className="drawer-toolbar">
          <span className="eyebrow">Job detail</span>
          <button ref={closeButton} className="icon-button" onClick={onClose} aria-label="Close job details">
            <X size={20} />
          </button>
        </div>
        {loading ? (
          <LoadingState label="Loading job" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : job ? (
          <div className="drawer-content">
            <header className="job-detail-header">
              <div>
                <h2 id="job-drawer-title">{job.title}</h2>
                <p>{job.company} · {job.location ?? "Location not specified"}</p>
              </div>
              <MatchBadges job={displayJob ?? job} />
              <div className="job-meta-row">
                <ApplicationBadge status={job.application?.status} />
                <span>First seen {formatDate(job.first_seen)}</span>
                <span>Last seen {formatDate(job.last_seen)}</span>
              </div>
              <div className="button-row">
                {job.url && (
                  <a className="button button-primary" href={job.url} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} /> Open original
                  </a>
                )}
                <button className="button button-secondary" onClick={reanalyze}>
                  <RotateCcw size={16} /> Reanalyze
                </button>
                <button className="button button-ghost" onClick={toggleArchive}>
                  <Archive size={16} /> {job.archived ? "Restore" : "Archive"}
                </button>
                <button className="button button-ghost" onClick={toggleDismiss}>
                  <ThumbsDown size={16} /> {job.dismissed ? "Restore match" : "Dismiss"}
                </button>
              </div>
            </header>

            <section className="detail-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">{showingHistoricalAnalysis ? "Selected historical evaluation" : "Latest evaluation"}</p>
                  <h3>Gemini verdict</h3>
                </div>
              </div>
              {showingHistoricalAnalysis && <p className="inline-note">This is the evaluation from the selected past search. Cover-letter generation and reanalysis use the latest saved evaluation.</p>}
              {displayedAnalysis ? displayedAnalysis.error_message ? (
                <p className="inline-error">{displayedAnalysis.error_message}</p>
              ) : displayedAnalysis.match_score !== null ? (
                <div className="match-detail-analysis">
                  <div className="detail-score-hero"><strong>{displayedAnalysis.match_score}</strong><span><b>{displayedAnalysis.recommendation_label}</b><small>{displayedAnalysis.short_explanation || displayedAnalysis.verdict}</small></span></div>
                  <div className="score-breakdown" aria-label="Match score breakdown">
                    {Object.entries(displayedAnalysis.score_breakdown).map(([criterion, score]) => <div key={criterion}><span>{criterion.replaceAll("_", " ")}</span><strong>{score}</strong><i><b style={{ width: `${Math.min(100, (score / (SCORE_MAXIMUMS[criterion] ?? 20)) * 100)}%` }} /></i></div>)}
                  </div>
                  <div className="analysis-detail-grid">
                    <div><h4>Why this job fits</h4>{displayedAnalysis.matched_strengths.length ? <ul>{displayedAnalysis.matched_strengths.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">No matched strengths recorded.</p>}</div>
                    <div><h4>Potential concerns</h4>{displayedAnalysis.potential_concerns.length ? <ul>{displayedAnalysis.potential_concerns.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">No material concerns identified.</p>}</div>
                    <div><h4>Missing requirements</h4>{displayedAnalysis.missing_requirements.length ? <ul>{displayedAnalysis.missing_requirements.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">No explicit missing requirements.</p>}</div>
                    <div><h4>Suggested resume keywords</h4><div className="keyword-cloud">{displayedAnalysis.suggested_resume_keywords.map((value) => <span key={value}>{value}</span>)}</div></div>
                  </div>
                  <div className="application-strategy"><strong>Suggested application strategy</strong><p>{displayedAnalysis.application_strategy || "Emphasize the strongest verified matches and address gaps accurately."}</p></div>
                  <span className="analysis-model-note">{displayedAnalysis.gemini_model} · {formatDate(displayedAnalysis.created_at, true)}</span>
                </div>
              ) : (
                <div className="verdict-card"><p>{displayedAnalysis.verdict || "No verdict returned."}</p><span>{displayedAnalysis.gemini_model} · {formatDate(displayedAnalysis.created_at, true)}</span></div>
              ) : (
                <p className="muted">This job has not been analyzed yet.</p>
              )}
            </section>

            <section className="detail-section cover-letter-editor">
              <div className="section-heading">
                <div><p className="eyebrow">Tailored application</p><h3>Cover letter</h3></div>
                <FileText size={19} />
              </div>
              {coverLetter ? (
                <>
                  <textarea rows={18} value={coverDraft} onChange={(event) => setCoverDraft(event.target.value)} aria-label="Editable tailored cover letter" />
                  <div className="cover-letter-meta">Generated with profile v{coverLetter.candidate_profile_version} · Last saved {formatDate(coverLetter.updated_at, true)}</div>
                  <div className="button-row">
                    <button className="button button-secondary" onClick={copyLetter}><Clipboard size={16} /> Copy</button>
                    <button className="button button-secondary" disabled={generatingLetter} onClick={generateLetter}><RotateCcw size={16} /> {generatingLetter ? "Regenerating…" : "Regenerate"}</button>
                    <button className="button button-primary" disabled={savingLetter || coverDraft.trim() === coverLetter.content.trim()} onClick={saveLetter}><Save size={16} /> {savingLetter ? "Saving…" : "Save edits"}</button>
                  </div>
                </>
              ) : (
                <div className="cover-letter-empty"><p>Generate a concise letter grounded in your structured profile, CV, base letter, and this match analysis.</p><button className="button button-primary" disabled={generatingLetter || !job.latest_analysis} onClick={generateLetter}><WandSparkles size={16} /> {generatingLetter ? "Generating…" : "Generate Cover Letter"}</button></div>
              )}
            </section>

            <section className="detail-section application-editor">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Workflow</p>
                  <h3>Application tracking</h3>
                </div>
              </div>
              <div className="form-grid two-column">
                <label>
                  Status
                  <select value={status} onChange={(event) => {
                    const nextStatus = event.target.value as ApplicationStatus;
                    setStatus(nextStatus);
                    if (nextStatus === "Applied" && !applicationDate) setApplicationDate(todayInput());
                  }}>
                    {APPLICATION_STATUSES.map((value) => <option key={value}>{value}</option>)}
                  </select>
                </label>
                <label>
                  Application date
                  <div className="input-with-icon">
                    <CalendarDays size={16} />
                    <input
                      type="date"
                      value={applicationDate}
                      max={todayInput()}
                      onChange={(e) => setApplicationDate(e.target.value)}
                    />
                  </div>
                </label>
                <label>
                  Next follow-up
                  <input type="date" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)} />
                </label>
              </div>
              <label>
                Notes
                <textarea
                  rows={5}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Contacts, interview notes, next steps…"
                />
              </label>
              <div className="button-row">
                <button className="button button-primary" onClick={saveApplication} disabled={saving}>
                  <Save size={16} /> {saving ? "Saving…" : "Save application"}
                </button>
                {job.application && <button className="button button-ghost" onClick={stopTracking} disabled={saving}><Trash2 size={16} /> Remove from board</button>}
              </div>
            </section>

            <section className="detail-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Source content</p>
                  <h3>Full description</h3>
                </div>
              </div>
              <div className="job-description">{job.description || "No description was available from the source."}</div>
            </section>

            <section className="detail-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Audit trail</p>
                  <h3>Prior analyses</h3>
                </div>
                <History size={19} />
              </div>
              {job.analyses.length ? (
                <div className="timeline">
                  {job.analyses.map((analysis) => (
                    <details key={analysis.id} className="timeline-item">
                      <summary>
                        <span>{formatDate(analysis.created_at, true)}</span>
                        <strong>{analysis.error_message ? "Failed" : analysis.match_score !== null ? `${analysis.match_score}/100 · ${analysis.recommendation_label}` : analysis.is_good_match && analysis.seniority_ok ? "Good match" : "Not suitable"}</strong>
                      </summary>
                      <p>{analysis.verdict || analysis.error_message}</p>
                      <dl className="compact-dl">
                        <div><dt>Model</dt><dd>{analysis.gemini_model}</dd></div>
                        <div><dt>Profile version</dt><dd>v{analysis.candidate_profile_version}</dd></div>
                      </dl>
                      <details className="profile-snapshot">
                        <summary>Candidate profile snapshot</summary>
                        <pre>{analysis.candidate_profile_snapshot}</pre>
                      </details>
                    </details>
                  ))}
                </div>
              ) : (
                <p className="muted">No historical analyses yet.</p>
              )}
            </section>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
