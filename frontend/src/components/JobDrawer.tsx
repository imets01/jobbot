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
  onClose,
  onChanged,
}: {
  jobId: number | null;
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
    load();
    document.body.classList.add("drawer-open");
    window.setTimeout(() => closeButton.current?.focus(), 40);
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", escape);
    return () => {
      document.body.classList.remove("drawer-open");
      window.removeEventListener("keydown", escape);
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

  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="job-drawer" role="dialog" aria-modal="true" aria-labelledby="job-drawer-title">
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
              <MatchBadges job={job} />
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
                  <p className="eyebrow">Latest evaluation</p>
                  <h3>Gemini verdict</h3>
                </div>
              </div>
              {job.latest_analysis ? job.latest_analysis.error_message ? (
                <p className="inline-error">{job.latest_analysis.error_message}</p>
              ) : job.latest_analysis.match_score !== null ? (
                <div className="match-detail-analysis">
                  <div className="detail-score-hero"><strong>{job.latest_analysis.match_score}</strong><span><b>{job.latest_analysis.recommendation_label}</b><small>{job.latest_analysis.short_explanation || job.latest_analysis.verdict}</small></span></div>
                  <div className="score-breakdown" aria-label="Match score breakdown">
                    {Object.entries(job.latest_analysis.score_breakdown).map(([criterion, score]) => <div key={criterion}><span>{criterion.replaceAll("_", " ")}</span><strong>{score}</strong><i><b style={{ width: `${Math.min(100, (score / (SCORE_MAXIMUMS[criterion] ?? 20)) * 100)}%` }} /></i></div>)}
                  </div>
                  <div className="analysis-detail-grid">
                    <div><h4>Why this job fits</h4><ul>{job.latest_analysis.matched_strengths.map((value) => <li key={value}>{value}</li>)}</ul></div>
                    <div><h4>Potential concerns</h4>{job.latest_analysis.potential_concerns.length ? <ul>{job.latest_analysis.potential_concerns.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">No material concerns identified.</p>}</div>
                    <div><h4>Missing requirements</h4>{job.latest_analysis.missing_requirements.length ? <ul>{job.latest_analysis.missing_requirements.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">No explicit missing requirements.</p>}</div>
                    <div><h4>Suggested resume keywords</h4><div className="keyword-cloud">{job.latest_analysis.suggested_resume_keywords.map((value) => <span key={value}>{value}</span>)}</div></div>
                  </div>
                  <div className="application-strategy"><strong>Suggested application strategy</strong><p>{job.latest_analysis.application_strategy || "Emphasize the strongest verified matches and address gaps accurately."}</p></div>
                  <span className="analysis-model-note">{job.latest_analysis.gemini_model} · {formatDate(job.latest_analysis.created_at, true)}</span>
                </div>
              ) : (
                <div className="verdict-card"><p>{job.latest_analysis.verdict || "No verdict returned."}</p><span>{job.latest_analysis.gemini_model} · {formatDate(job.latest_analysis.created_at, true)}</span></div>
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
                  <select value={status} onChange={(e) => setStatus(e.target.value as ApplicationStatus)}>
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
              <button className="button button-primary" onClick={saveApplication} disabled={saving}>
                <Save size={16} /> {saving ? "Saving…" : "Save application"}
              </button>
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
