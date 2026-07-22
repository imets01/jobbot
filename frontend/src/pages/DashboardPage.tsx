import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarClock,
  ClipboardCheck,
  Search,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import {
  ApplicationBadge,
  EmptyState,
  ErrorState,
  LoadingState,
  MatchBadges,
  PageHeader,
  RunStatusBadge,
  StatCard,
} from "../components/Ui";
import type { DashboardSummary } from "../types";
import { formatDate, runProgress } from "../utils";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedJob, setSelectedJob] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      setSummary(await api.dashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load search results");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  if (loading) return <LoadingState label="Loading search results" />;
  if (error || !summary) return <ErrorState message={error || "Results unavailable"} onRetry={load} />;

  const maxStatus = Math.max(1, ...summary.application_statuses.map((item) => item.count));
  const active = summary.active_run;

  return (
    <>
      <PageHeader
        eyebrow="Results"
        title="Search results dashboard"
        description="A secondary overview of your qualifying matches and application progress."
        actions={<div className="button-row"><Link className="button button-primary" to="/"><Search size={16} /> Start a new search</Link><Link className="button button-secondary" to="/jobs">View all matches <ArrowRight size={16} /></Link></div>}
      />

      {active && (
        <section className="panel search-progress-panel">
          <div className="section-heading"><div><p className="eyebrow">Search in progress</p><h2>Discovering and scoring jobs</h2></div><RunStatusBadge status={active.status} /></div>
          <p className="section-description">Jobbot is completing one end-to-end search. Matches will appear as soon as scoring finishes.</p>
          <div className="progress-track large"><span style={{ width: `${runProgress(active)}%` }} /></div>
          <div className="run-kpis"><span><strong>{active.jobs_discovered}</strong> discovered</span><span><strong>{active.jobs_analyzed}/{active.jobs_queued}</strong> scored</span><span><strong>{active.good_matches}</strong> qualified</span><span><strong>{active.failures}</strong> failures</span></div>
        </section>
      )}

      <section className="stat-grid results-stat-grid" aria-label="Search result statistics">
        <StatCard label="Discovered jobs" value={summary.total_jobs} detail="Unique listings retained" icon={BriefcaseBusiness} />
        <StatCard label="Qualified matches" value={summary.good_matches} detail="Above your current threshold" icon={Sparkles} tone="success" />
        <StatCard label="Applications" value={summary.applications_submitted} detail="Submitted or progressed" icon={ClipboardCheck} tone="accent" />
        <StatCard label="Follow-ups due" value={summary.follow_ups_due} detail="Action needed today" icon={CalendarClock} tone={summary.follow_ups_due ? "warning" : "default"} />
      </section>

      <section className="dashboard-grid results-dashboard-grid">
        <article className="panel recent-panel">
          <div className="section-heading"><div><p className="eyebrow">Top recommendations</p><h2>Best current matches</h2></div><Link className="text-link" to="/jobs">View all <ArrowRight size={14} /></Link></div>
          {summary.recent_good_matches.length ? (
            <div className="job-card-grid dashboard-match-grid">
              {summary.recent_good_matches.map((job) => (
                <button className="job-card" key={job.id} onClick={() => setSelectedJob(job.id)}>
                  <div className="job-card-top"><span className="company-avatar">{job.company.slice(0, 1).toUpperCase()}</span><MatchBadges job={job} /></div>
                  <div><h3>{job.title}</h3><p>{job.company}</p></div>
                  <p className="job-verdict">{job.latest_analysis?.short_explanation || job.latest_analysis?.verdict}</p>
                  <footer><span>{job.latest_analysis?.match_score ?? "—"}/100 · {formatDate(job.last_seen)}</span><ArrowRight size={16} /></footer>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title={active ? "Your search is still running" : "No qualifying matches yet"}
              description={active ? "Jobbot is discovering and scoring listings now." : "Start a job search to discover and rank new opportunities."}
              icon={Sparkles}
              action={!active ? <Link className="button button-primary" to="/"><Search size={16} /> Start Job Search</Link> : undefined}
            />
          )}
        </article>

        <article className="panel status-panel">
          <div className="section-heading"><div><p className="eyebrow">Application funnel</p><h2>Status overview</h2></div><ClipboardCheck size={20} /></div>
          {summary.application_statuses.length ? (
            <div className="status-bars">{summary.application_statuses.map((item) => <div className="status-bar" key={item.status}><div><ApplicationBadge status={item.status as never} /><strong>{item.count}</strong></div><div className="mini-track"><span style={{ width: `${(item.count / maxStatus) * 100}%` }} /></div></div>)}</div>
          ) : (
            <EmptyState title="No applications tracked" description="Open a match and move it to Interested or Applied." icon={ClipboardCheck} />
          )}
          <Link className="text-link" to="/applications">Open application board <ArrowRight size={14} /></Link>
        </article>
      </section>

      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={load} />
    </>
  );
}
