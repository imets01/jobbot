import {
  Archive,
  CalendarDays,
  ExternalLink,
  History,
  RotateCcw,
  Save,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ApplicationStatus, JobDetail } from "../types";
import { APPLICATION_STATUSES, formatDate, todayInput } from "../utils";
import { useToast } from "./ToastProvider";
import { ApplicationBadge, ErrorState, LoadingState, MatchBadges } from "./Ui";

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
  const closeButton = useRef<HTMLButtonElement>(null);
  const { showToast } = useToast();

  const load = async () => {
    if (jobId === null) return;
    setLoading(true);
    setError("");
    try {
      const value = await api.job(jobId);
      setJob(value);
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
              </div>
            </header>

            <section className="detail-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Latest evaluation</p>
                  <h3>Gemini verdict</h3>
                </div>
              </div>
              {job.latest_analysis ? (
                <div className="verdict-card">
                  <p>{job.latest_analysis.verdict || job.latest_analysis.error_message || "No verdict returned."}</p>
                  <span>{job.latest_analysis.gemini_model} · {formatDate(job.latest_analysis.created_at, true)}</span>
                </div>
              ) : (
                <p className="muted">This job has not been analyzed yet.</p>
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
                        <strong>{analysis.error_message ? "Failed" : analysis.is_good_match && analysis.seniority_ok ? "Good match" : "Not suitable"}</strong>
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
