import {
  ChevronDown,
  ChevronRight,
  CircleAlert,
  EyeOff,
  History,
  Search,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import { useToast } from "../components/ToastProvider";
import {
  ApplicationBadge,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  RunStatusBadge,
} from "../components/Ui";
import type { AnalysisResult, Paginated, Run, RunResult } from "../types";
import { formatDate } from "../utils";

type ResultView = "matches" | "all" | "not_matches" | "errors";

function isMatch(analysis: AnalysisResult) {
  return !analysis.error_message
    && Boolean(analysis.qualifies ?? (analysis.is_good_match && analysis.seniority_ok));
}

function compactList(values: string[], limit = 2) {
  if (!values.length) return "Not specified";
  const visible = values.slice(0, limit).join(" · ");
  return values.length > limit ? `${visible} +${values.length - limit}` : visible;
}

function RunResults({
  runId,
  onSelectJob,
  refreshToken,
}: {
  runId: string;
  onSelectJob: (jobId: number) => void;
  refreshToken: number;
}) {
  const [results, setResults] = useState<RunResult[] | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<ResultView>("matches");
  const [query, setQuery] = useState("");

  useEffect(() => {
    setResults(null);
    setError("");
    api.runResults(runId)
      .then(setResults)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load results"));
  }, [refreshToken, runId]);

  const groups = useMemo(() => {
    const all = results ?? [];
    return {
      all,
      matches: all.filter(({ analysis }) => isMatch(analysis)),
      not_matches: all.filter(({ analysis }) => !analysis.error_message && !isMatch(analysis)),
      errors: all.filter(({ analysis }) => Boolean(analysis.error_message)),
    };
  }, [results]);

  const visibleResults = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return [...groups[view]]
      .filter(({ job }) => !term || `${job.title} ${job.company} ${job.location ?? ""}`.toLocaleLowerCase().includes(term))
      .sort((left, right) => (right.analysis.match_score ?? -1) - (left.analysis.match_score ?? -1));
  }, [groups, query, view]);

  if (error) return <p className="inline-error">{error}</p>;
  if (!results) return <div className="inline-loader"><span className="spinner-dot" /> Loading results…</div>;
  if (!results.length) return <p className="muted run-empty">This search did not create analysis results.</p>;

  const tabs: { value: ResultView; label: string; count: number }[] = [
    { value: "matches", label: "Matches", count: groups.matches.length },
    { value: "all", label: "All analyzed", count: groups.all.length },
    { value: "not_matches", label: "Not matched", count: groups.not_matches.length },
    { value: "errors", label: "Errors", count: groups.errors.length },
  ];

  return (
    <>
      <div className="run-results-toolbar">
        <div className="history-result-tabs" role="tablist" aria-label="Filter search results">
          {tabs.map((tab) => (
            <button
              type="button"
              role="tab"
              aria-selected={view === tab.value}
              className={view === tab.value ? "is-active" : ""}
              key={tab.value}
              onClick={() => setView(tab.value)}
            >
              {tab.label} <span>{tab.count}</span>
            </button>
          ))}
        </div>
        <label className="search-field run-result-search">
          <Search size={15} />
          <span className="sr-only">Search results from this run</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a role or company…" />
        </label>
      </div>

      {!visibleResults.length ? (
        <p className="muted run-empty">No results in this view{query.trim() ? " match your search" : ""}.</p>
      ) : (
        <div className="run-results-list">
          {visibleResults.map(({ job, analysis }) => (
            <button className="run-result-row" type="button" key={analysis.id} onClick={() => onSelectJob(job.id)}>
              <span className={`result-dot ${analysis.error_message ? "error" : isMatch(analysis) ? "match" : "skip"}`} />
              <div className="run-result-title"><strong>{job.title}</strong><span>{job.company} · {job.location ?? "Location unavailable"}</span></div>
              <p>{analysis.error_message ?? `${analysis.match_score !== null ? `${analysis.match_score}/100 · ` : ""}${analysis.short_explanation || analysis.verdict}`}</p>
              <div className="run-result-state">
                <ApplicationBadge status={job.application?.status} />
                <strong className="run-result-score">{analysis.match_score !== null ? `${analysis.match_score}/100` : "—"}</strong>
                <ChevronRight size={17} aria-hidden="true" />
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export function HistoryPage() {
  const [data, setData] = useState<Paginated<Run> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);
  const [resultsRefresh, setResultsRefresh] = useState(0);
  const [removing, setRemoving] = useState<string | null>(null);
  const [filters, setFilters] = useState({ status: "", date_from: "", date_to: "" });
  const { showToast } = useToast();

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
    void load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  const update = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };

  const remove = async (run: Run) => {
    const permanentlyDeleted = run.status === "failed" || run.jobs_analyzed === 0;
    const message = permanentlyDeleted
      ? "Permanently delete this failed or empty search and any analysis records it created? Jobs, application tracking, and cover letters will remain."
      : "Remove this search from history? Its job analyses and application tracking will be preserved.";
    if (!window.confirm(message)) return;

    setRemoving(run.id);
    try {
      const result = await api.removeRun(run.id);
      setExpanded((current) => current === run.id ? null : current);
      showToast(result.disposition === "hidden" ? "Search removed from history" : "Search deleted", "success");
      if ((data?.items.length ?? 0) === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        await load();
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to remove search", "error");
    } finally {
      setRemoving(null);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Past searches"
        title="Search history"
        description="Revisit the exact results from any search, inspect job details, and continue application tracking."
      />
      <section className="panel history-panel">
        <div className="filter-grid history-filters">
          <label>Status<select value={filters.status} onChange={(event) => update("status", event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option></select></label>
          <label>From<input type="date" value={filters.date_from} onChange={(event) => update("date_from", event.target.value)} /></label>
          <label>To<input type="date" value={filters.date_to} onChange={(event) => update("date_to", event.target.value)} /></label>
        </div>

        {loading && !data ? <LoadingState label="Loading run history" /> : error ? <ErrorState message={error} onRetry={load} /> : !data?.items.length ? (
          <EmptyState title="No searches found" description="Start a job search to create your first history entry." icon={History} />
        ) : (
          <div className="run-list">
            {data.items.map((run) => {
              const isExpanded = expanded === run.id;
              const controls = run.search_controls;
              const isSearchRun = run.run_type === "search" || run.run_type === "full";
              const canRemove = run.status === "completed" || run.status === "failed";
              const permanentlyDeleted = run.status === "failed" || run.jobs_analyzed === 0;
              return (
                <article className="run-card" key={run.id}>
                  <div className="run-card-header">
                    <button className="run-card-summary" onClick={() => setExpanded(isExpanded ? null : run.id)} aria-expanded={isExpanded}>
                      <span className="run-type-icon">{isSearchRun ? <Search size={18} /> : <History size={18} />}</span>
                      <div className="run-primary">
                        <strong>{controls ? compactList(controls.keywords) : isSearchRun ? "Job search" : "Previous activity"}</strong>
                        <span>{controls ? `${compactList(controls.target_locations, 1)} · ` : ""}{formatDate(run.created_at, true)}</span>
                      </div>
                      <RunStatusBadge status={run.status} />
                      <div className="run-metrics"><span><strong>{run.jobs_discovered}</strong> discovered</span><span><strong>{run.jobs_analyzed}</strong> analyzed</span><span><strong>{run.good_matches}</strong> matches</span>{run.failures > 0 && <span className="danger-text"><CircleAlert size={14} /> {run.failures} failed</span>}</div>
                      {isExpanded ? <ChevronDown size={19} /> : <ChevronRight size={19} />}
                    </button>
                    {canRemove && (
                      <button
                        className="button button-ghost run-remove-button"
                        disabled={removing === run.id}
                        onClick={() => void remove(run)}
                        aria-label={permanentlyDeleted ? "Delete search" : "Remove search from history"}
                      >
                        {permanentlyDeleted ? <Trash2 size={15} /> : <EyeOff size={15} />}
                        <span>{removing === run.id ? "Removing…" : permanentlyDeleted ? "Delete" : "Remove"}</span>
                      </button>
                    )}
                  </div>
                  {isExpanded && (
                    <div className="run-card-details">
                      {run.error_details && <p className="inline-error">{run.error_details}</p>}
                      {controls && (
                        <dl className="run-criteria-summary">
                          <div><dt>Roles</dt><dd>{controls.keywords.join(", ")}</dd></div>
                          <div><dt>Locations</dt><dd>{controls.target_locations.join(", ")}</dd></div>
                          <div><dt>Work model</dt><dd>{controls.work_models.join(", ") || "Any"}</dd></div>
                          <div><dt>Threshold</dt><dd>{controls.minimum_match_score}/100</dd></div>
                          <div><dt>Requested</dt><dd>Top {controls.number_of_jobs}</dd></div>
                          <div><dt>Experience limit</dt><dd>{controls.max_required_experience_years === null ? "None" : `${controls.max_required_experience_years} years`}</dd></div>
                          <div><dt>Sources</dt><dd>{controls.sources.join(", ")}</dd></div>
                          <div><dt>Company boards</dt><dd>{controls.greenhouse_boards.length + controls.lever_sites.length || "None"}</dd></div>
                        </dl>
                      )}
                      <RunResults runId={run.id} onSelectJob={setSelectedJob} refreshToken={resultsRefresh} />
                    </div>
                  )}
                </article>
              );
            })}
            <footer className="pagination"><span>{data.total} searches</span><div><button className="button button-ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {data.page} of {data.pages}</span><button className="button button-ghost" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></footer>
          </div>
        )}
      </section>
      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={() => setResultsRefresh((current) => current + 1)} />
    </>
  );
}
