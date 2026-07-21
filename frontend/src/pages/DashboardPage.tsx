import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarClock,
  ChartNoAxesCombined,
  ClipboardCheck,
  Play,
  Radar,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import { useToast } from "../components/ToastProvider";
import { ApplicationBadge, EmptyState, ErrorState, LoadingState, MatchBadges, PageHeader, StatCard } from "../components/Ui";
import type { DashboardSummary, RunType, Settings } from "../types";
import { formatDate } from "../utils";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState<RunType | null>(null);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    setError("");
    try {
      const [dashboard, currentSettings] = await Promise.all([api.dashboard(), api.settings()]);
      setSummary(dashboard);
      setSettings(currentSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  const start = async (type: RunType) => {
    if (!settings) return;
    setStarting(type);
    try {
      const payload = {
        role: settings.default_role,
        location: settings.default_location,
        max_jobs: settings.default_max_jobs,
      };
      if (type === "scraper") await api.startScraper(payload);
      else if (type === "analyzer") await api.startAnalyzer();
      else await api.startFull(payload);
      showToast(`${type} run started`, "success");
      await load();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to start run", "error");
    } finally {
      setStarting(null);
    }
  };

  if (loading) return <LoadingState label="Loading your workspace" />;
  if (error || !summary) return <ErrorState message={error || "No dashboard data"} onRetry={load} />;
  const runDisabled = Boolean(summary.active_run || starting);
  const maxStatus = Math.max(1, ...summary.application_statuses.map((item) => item.count));

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Your job search, in one place"
        description="Discover technical roles, let Gemini assess fit, and keep every application moving."
        actions={<Link className="button button-secondary" to="/jobs">Browse all jobs <ArrowRight size={16} /></Link>}
      />

      <section className="stat-grid" aria-label="Dashboard statistics">
        <StatCard label="Unique jobs" value={summary.total_jobs} detail="Deduplicated listings" icon={BriefcaseBusiness} />
        <StatCard label="Good matches" value={summary.good_matches} detail="Technical + seniority fit" icon={Sparkles} tone="success" />
        <StatCard label="Waiting" value={summary.waiting_for_analysis} detail="Need current profile analysis" icon={Radar} tone="warning" />
        <StatCard label="Applications" value={summary.applications_submitted} detail="Submitted or progressed" icon={ClipboardCheck} tone="accent" />
        <StatCard label="Follow-ups due" value={summary.follow_ups_due} detail="Action needed today" icon={CalendarClock} tone={summary.follow_ups_due ? "warning" : "default"} />
      </section>

      <section className="dashboard-grid">
        <article className="panel quick-actions-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Quick actions</p><h2>Run the pipeline</h2></div>
            <Play size={20} />
          </div>
          <p className="section-description">Using {settings?.default_role} in {settings?.default_location}.</p>
          <div className="quick-action-list">
            <button className="quick-action" disabled={runDisabled} onClick={() => start("scraper")}>
              <span className="quick-action-icon"><Radar size={20} /></span>
              <span><strong>Run scraper</strong><small>Find and deduplicate fresh listings</small></span>
              <ArrowRight size={17} />
            </button>
            <button className="quick-action" disabled={runDisabled} onClick={() => start("analyzer")}>
              <span className="quick-action-icon"><WandSparkles size={20} /></span>
              <span><strong>Analyze new jobs</strong><small>Only jobs unseen by this profile</small></span>
              <ArrowRight size={17} />
            </button>
            <button className="quick-action featured" disabled={runDisabled} onClick={() => start("full")}>
              <span className="quick-action-icon"><ChartNoAxesCombined size={20} /></span>
              <span><strong>Run full pipeline</strong><small>Scrape, import, and evaluate</small></span>
              <ArrowRight size={17} />
            </button>
          </div>
          {summary.active_run && <p className="inline-note">A {summary.active_run.run_type} run is already in progress.</p>}
          <Link className="text-link" to="/controls">Customize run settings <ArrowRight size={14} /></Link>
        </article>

        <article className="panel status-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Application funnel</p><h2>Status overview</h2></div>
            <ClipboardCheck size={20} />
          </div>
          {summary.application_statuses.length ? (
            <div className="status-bars">
              {summary.application_statuses.map((item) => (
                <div className="status-bar" key={item.status}>
                  <div><ApplicationBadge status={item.status as never} /><strong>{item.count}</strong></div>
                  <div className="mini-track"><span style={{ width: `${(item.count / maxStatus) * 100}%` }} /></div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No applications tracked" description="Open a job and move it to Interested or Applied." icon={ClipboardCheck} />
          )}
          <Link className="text-link" to="/applications">Open application board <ArrowRight size={14} /></Link>
        </article>
      </section>

      <section className="panel recent-panel">
        <div className="section-heading">
          <div><p className="eyebrow">Recommended</p><h2>Recent good matches</h2></div>
          <Link className="text-link" to="/jobs?match=good">View all <ArrowRight size={14} /></Link>
        </div>
        {summary.recent_good_matches.length ? (
          <div className="job-card-grid">
            {summary.recent_good_matches.map((job) => (
              <button className="job-card" key={job.id} onClick={() => setSelectedJob(job.id)}>
                <div className="job-card-top"><span className="company-avatar">{job.company.slice(0, 1).toUpperCase()}</span><MatchBadges job={job} /></div>
                <div><h3>{job.title}</h3><p>{job.company}</p></div>
                <p className="job-verdict">{job.latest_analysis?.verdict}</p>
                <footer><span>{formatDate(job.last_seen)}</span><ArrowRight size={16} /></footer>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No matches yet" description="Analyze new jobs to surface roles that fit your profile." icon={Sparkles} />
        )}
      </section>

      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={load} />
    </>
  );
}
