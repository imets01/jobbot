import { Bot, Database, MapPin, Play, Radar, ShieldCheck, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/ToastProvider";
import { ErrorState, LoadingState, PageHeader, RunStatusBadge } from "../components/Ui";
import type { Run, RunType, Settings } from "../types";
import { formatDate, runProgress } from "../utils";

export function ControlsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [recentRuns, setRecentRuns] = useState<Run[]>([]);
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [maxJobs, setMaxJobs] = useState(0);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<RunType | null>(null);
  const [error, setError] = useState("");
  const { showToast } = useToast();

  const load = useCallback(async () => {
    setError("");
    try {
      const [currentSettings, active, history] = await Promise.all([api.settings(), api.activeRun(), api.runs({ page: 1, page_size: 5 })]);
      setSettings(currentSettings);
      setActiveRun(active);
      setRecentRuns(history.items);
      setRole((current) => current || currentSettings.default_role);
      setLocation((current) => current || currentSettings.default_location);
      setMaxJobs((current) => current || currentSettings.default_max_jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load controls");
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
    setStarting(type);
    try {
      const payload = { role: role.trim(), location: location.trim(), max_jobs: maxJobs };
      const run = type === "scraper" ? await api.startScraper(payload) : type === "full" ? await api.startFull(payload) : await api.startAnalyzer();
      setActiveRun(run);
      showToast(`${type} run queued`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not start run", "error");
    } finally {
      setStarting(null);
    }
  };

  if (loading) return <LoadingState label="Loading run controls" />;
  if (error || !settings) return <ErrorState message={error || "Settings unavailable"} onRetry={load} />;
  const disabled = Boolean(activeRun || starting || !role.trim() || !location.trim());

  return (
    <>
      <PageHeader eyebrow="Operations" title="Settings & run controls" description="Launch the existing scraper and Gemini analyzer safely in background jobs." />
      <div className="controls-layout">
        <section className="panel controls-panel">
          <div className="section-heading"><div><p className="eyebrow">Search scope</p><h2>Configure this run</h2></div><Radar size={20} /></div>
          <div className="form-grid">
            <label>Role or keywords<div className="input-with-icon"><Sparkles size={16} /><input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Security Engineer" /></div></label>
            <label>Location<div className="input-with-icon"><MapPin size={16} /><input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Zurich, Switzerland" /></div></label>
            <label>Maximum jobs<input type="number" min={1} max={100} value={maxJobs} onChange={(e) => setMaxJobs(Math.max(1, Math.min(100, Number(e.target.value))))} /></label>
          </div>
          <p className="inline-note">Use a fully qualified location including the country so LinkedIn applies the correct geography.</p>
          <div className="run-choice-grid">
            <button className="run-choice" disabled={disabled} onClick={() => start("scraper")}><span><Radar size={20} /></span><strong>Scraper only</strong><small>Discover and import jobs</small><Play size={16} /></button>
            <button className="run-choice" disabled={disabled} onClick={() => start("analyzer")}><span><Bot size={20} /></span><strong>Analyze new</strong><small>Current profile, unseen jobs</small><Play size={16} /></button>
            <button className="run-choice featured" disabled={disabled} onClick={() => start("full")}><span><Sparkles size={20} /></span><strong>Full pipeline</strong><small>Discover then evaluate</small><Play size={16} /></button>
          </div>
        </section>

        <aside className="controls-sidebar">
          <article className="panel model-card"><span className="guidance-icon"><Bot size={20} /></span><p className="eyebrow">Analysis model</p><h3>{settings.gemini_model}</h3><p>Requests are paced server-side to respect the configured free-tier RPM.</p></article>
          <article className="panel model-card"><span className="guidance-icon"><ShieldCheck size={20} /></span><p className="eyebrow">Credential boundary</p><h3>Server-side only</h3><p>The frontend never reads or receives <code>GEMINI_API_KEY</code>.</p></article>
          <article className="panel model-card"><span className="guidance-icon"><Database size={20} /></span><p className="eyebrow">Persistence</p><h3>SQLite + raw JSON</h3><p>JSON remains an import source; deduplicated state and history live in SQLite.</p></article>
        </aside>
      </div>

      {activeRun && (
        <section className="panel current-run-panel">
          <div className="section-heading"><div><p className="eyebrow">Current activity</p><h2>{activeRun.run_type} run</h2></div><RunStatusBadge status={activeRun.status} /></div>
          <div className="progress-track large"><span style={{ width: `${runProgress(activeRun)}%` }} /></div>
          <div className="run-kpis"><span><strong>{activeRun.jobs_discovered}</strong> discovered</span><span><strong>{activeRun.jobs_analyzed}/{activeRun.jobs_queued}</strong> analyzed</span><span><strong>{activeRun.good_matches}</strong> matches</span><span><strong>{activeRun.failures}</strong> failures</span></div>
        </section>
      )}

      <section className="panel recent-runs-compact">
        <div className="section-heading"><div><p className="eyebrow">Recent activity</p><h2>Latest runs</h2></div></div>
        {recentRuns.map((run) => <div className="compact-run-row" key={run.id}><div><strong>{run.run_type}</strong><span>{formatDate(run.created_at, true)}</span></div><RunStatusBadge status={run.status} /><span>{run.jobs_analyzed} analyzed</span><span>{run.good_matches} matches</span></div>)}
      </section>
    </>
  );
}
