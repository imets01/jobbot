import { CalendarRange, ChevronDown, ChevronRight, CircleAlert, Clock3, History } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState, PageHeader, RunStatusBadge } from "../components/Ui";
import type { Paginated, Run, RunResult } from "../types";
import { formatDate } from "../utils";

function RunResults({ runId }: { runId: string }) {
  const [results, setResults] = useState<RunResult[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.runResults(runId).then(setResults).catch((err) => setError(err instanceof Error ? err.message : "Unable to load results"));
  }, [runId]);
  if (error) return <p className="inline-error">{error}</p>;
  if (!results) return <div className="inline-loader"><span className="spinner-dot" /> Loading results…</div>;
  if (!results.length) return <p className="muted run-empty">This run did not create analysis results.</p>;
  return (
    <div className="run-results-list">
      {results.map(({ job, analysis }) => (
        <div className="run-result-row" key={analysis.id}>
          <span className={`result-dot ${analysis.error_message ? "error" : analysis.is_good_match && analysis.seniority_ok ? "match" : "skip"}`} />
          <div><strong>{job.title}</strong><span>{job.company}</span></div>
          <p>{analysis.error_message ?? analysis.verdict}</p>
        </div>
      ))}
    </div>
  );
}

export function HistoryPage() {
  const [data, setData] = useState<Paginated<Run> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filters, setFilters] = useState({ run_type: "", status: "", date_from: "", date_to: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.runs({ page, page_size: 15, ...filters }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load run history");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  const update = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };

  return (
    <>
      <PageHeader eyebrow="Audit trail" title="Analysis history" description="Every scraper and Gemini run remains visible, including prior profile snapshots and failures." />
      <section className="panel history-panel">
        <div className="filter-grid history-filters">
          <label>Run type<select value={filters.run_type} onChange={(e) => update("run_type", e.target.value)}><option value="">All types</option><option value="scraper">Scraper</option><option value="analyzer">Analyzer</option><option value="full">Full pipeline</option></select></label>
          <label>Status<select value={filters.status} onChange={(e) => update("status", e.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option></select></label>
          <label>From<input type="date" value={filters.date_from} onChange={(e) => update("date_from", e.target.value)} /></label>
          <label>To<input type="date" value={filters.date_to} onChange={(e) => update("date_to", e.target.value)} /></label>
        </div>

        {loading && !data ? <LoadingState label="Loading run history" /> : error ? <ErrorState message={error} onRetry={load} /> : !data?.items.length ? (
          <EmptyState title="No runs found" description="Start the scraper or analyzer to create your first history entry." icon={History} />
        ) : (
          <div className="run-list">
            {data.items.map((run) => {
              const isExpanded = expanded === run.id;
              return (
                <article className="run-card" key={run.id}>
                  <button className="run-card-summary" onClick={() => setExpanded(isExpanded ? null : run.id)} aria-expanded={isExpanded}>
                    <span className="run-type-icon">{run.run_type === "full" ? <History size={18} /> : run.run_type === "scraper" ? <CalendarRange size={18} /> : <Clock3 size={18} />}</span>
                    <div className="run-primary"><strong>{run.run_type === "full" ? "Full pipeline" : run.run_type[0].toUpperCase() + run.run_type.slice(1)}</strong><span>{formatDate(run.created_at, true)}</span></div>
                    <RunStatusBadge status={run.status} />
                    <div className="run-metrics"><span><strong>{run.jobs_discovered}</strong> discovered</span><span><strong>{run.jobs_analyzed}</strong> analyzed</span><span><strong>{run.good_matches}</strong> matches</span>{run.failures > 0 && <span className="danger-text"><CircleAlert size={14} /> {run.failures} failed</span>}</div>
                    {isExpanded ? <ChevronDown size={19} /> : <ChevronRight size={19} />}
                  </button>
                  {isExpanded && (
                    <div className="run-card-details">
                      {run.error_details && <p className="inline-error">{run.error_details}</p>}
                      <RunResults runId={run.id} />
                    </div>
                  )}
                </article>
              );
            })}
            <footer className="pagination"><span>{data.total} runs</span><div><button className="button button-ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {data.page} of {data.pages}</span><button className="button button-ghost" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></footer>
          </div>
        )}
      </section>
    </>
  );
}
