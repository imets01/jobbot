import { ExternalLink, FileText, Filter, Search, SlidersHorizontal, Sparkles, ThumbsDown, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import { useToast } from "../components/ToastProvider";
import { ApplicationBadge, EmptyState, ErrorState, LoadingState, MatchBadges, PageHeader } from "../components/Ui";
import type { ApplicationStatus, Job, Paginated, SearchControls } from "../types";
import { APPLICATION_STATUSES, formatDate } from "../utils";

const initialFilters = {
  application_status: "",
  company: "",
  archived: "active",
  dismissed: "active",
  sort: "match_quality",
  direction: "desc",
};

export function JobsPage() {
  const [data, setData] = useState<Paginated<Job> | null>(null);
  const [controls, setControls] = useState<SearchControls | null>(null);
  const [companies, setCompanies] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [filters, setFilters] = useState(initialFilters);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);
  const [generating, setGenerating] = useState<number | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async () => {
    if (!controls) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.jobs({
        page: 1,
        page_size: controls.number_of_jobs,
        search,
        minimum_score: controls.minimum_match_score,
        ...filters,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load matches");
    } finally {
      setLoading(false);
    }
  }, [controls, filters, search]);

  useEffect(() => {
    Promise.all([api.searchControls(), api.companies()])
      .then(([saved, companyValues]) => { setControls(saved); setCompanies(companyValues); })
      .catch((err) => { setError(err instanceof Error ? err.message : "Unable to load matching settings"); setLoading(false); });
  }, []);

  useEffect(() => {
    void load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  const activeFilterCount = useMemo(() => Object.entries(filters).filter(([key, value]) => !["sort", "direction", "archived", "dismissed"].includes(key) && value).length + (filters.archived !== "active" ? 1 : 0) + (filters.dismissed !== "active" ? 1 : 0), [filters]);
  const updateFilter = (key: keyof typeof filters, value: string) => setFilters((current) => ({ ...current, [key]: value }));

  const dismiss = async (job: Job) => {
    try {
      await api.dismissJob(job.id, !job.dismissed);
      showToast(job.dismissed ? "Match restored" : "Match dismissed", "success");
      await load();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to update match", "error");
    }
  };

  const generate = async (job: Job) => {
    setGenerating(job.id);
    try {
      await api.generateCoverLetter(job.id);
      showToast("Tailored cover letter generated", "success");
      setSelectedJob(job.id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to generate cover letter", "error");
    } finally {
      setGenerating(null);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Ranked opportunities"
        title="Job matches"
        description={controls ? `Showing up to ${controls.number_of_jobs} top matches scoring ${controls.minimum_match_score} or higher.` : "Only qualifying jobs appear here."}
        actions={<Link className="button button-secondary" to="/"><SlidersHorizontal size={16} /> Start a new search</Link>}
      />

      <section className="panel match-results-panel">
        <div className="jobs-toolbar">
          <label className="search-field"><Search size={17} /><span className="sr-only">Search matches</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search role or company…" />{searchInput && <button className="icon-button" onClick={() => setSearchInput("")} aria-label="Clear search"><X size={15} /></button>}</label>
          <label className="compact-select"><span>Sort</span><select value={filters.sort} onChange={(event) => updateFilter("sort", event.target.value)}><option value="match_quality">Match score</option><option value="newest">Newest</option><option value="last_analyzed">Last analyzed</option><option value="company">Company</option></select></label>
          <button className="button button-ghost" onClick={() => updateFilter("direction", filters.direction === "desc" ? "asc" : "desc")}>{filters.direction === "desc" ? "Descending" : "Ascending"}</button>
          <button className="button button-secondary filter-toggle visible-filter-toggle" onClick={() => setFilterOpen((value) => !value)}><Filter size={16} /> Filters {activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}</button>
        </div>
        <div className={`filter-drawer ${filterOpen ? "is-open" : ""}`}>
          <div className="filter-grid match-filter-grid">
            <label>Application<select value={filters.application_status} onChange={(event) => updateFilter("application_status", event.target.value)}><option value="">All statuses</option>{APPLICATION_STATUSES.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Company<select value={filters.company} onChange={(event) => updateFilter("company", event.target.value)}><option value="">All companies</option>{companies.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Archive<select value={filters.archived} onChange={(event) => updateFilter("archived", event.target.value)}><option value="active">Active jobs</option><option value="archived">Archived only</option><option value="all">All jobs</option></select></label>
            <label>Dismissal<select value={filters.dismissed} onChange={(event) => updateFilter("dismissed", event.target.value)}><option value="active">Current matches</option><option value="dismissed">Dismissed only</option><option value="all">All matches</option></select></label>
          </div>
          <button className="text-link" onClick={() => { setFilters(initialFilters); setSearchInput(""); }}><SlidersHorizontal size={14} /> Reset filters</button>
        </div>

        {loading && !data ? <LoadingState label="Loading scored matches" /> : error ? <ErrorState message={error} onRetry={load} /> : !data?.items.length ? (
          <EmptyState title="No qualifying matches" description="Start a job search or adjust the score threshold and filters in the guided search setup." icon={Sparkles} action={<Link className="button button-primary" to="/">Start Job Search</Link>} />
        ) : (
          <div className="match-result-list">
            {data.items.map((job) => {
              const analysis = job.latest_analysis!;
              return (
                <article className="match-result-card" key={job.id}>
                  <div className="match-score-block"><strong>{analysis.match_score ?? "—"}</strong><span>/ 100</span><small>{analysis.recommendation_label}</small></div>
                  <div className="match-result-main">
                    <div className="match-result-heading"><div><h2>{job.title}</h2><p>{job.company} · {job.location ?? "Location unavailable"}</p></div><MatchBadges job={job} /></div>
                    <div className="match-meta-row"><span>{analysis.work_model ?? "Work model unknown"}</span><span>{job.source}</span><span>Analyzed {formatDate(analysis.created_at)}</span><ApplicationBadge status={job.application?.status as ApplicationStatus | undefined} /></div>
                    <p className="match-explanation">{analysis.short_explanation || analysis.verdict}</p>
                    <div className="match-evidence-grid">
                      <div><strong>Matched strengths</strong><ul>{analysis.matched_strengths.slice(0, 3).map((value) => <li key={value}>{value}</li>)}</ul></div>
                      <div><strong>Missing or weak areas</strong>{analysis.weak_areas.length || analysis.missing_requirements.length ? <ul>{[...analysis.weak_areas, ...analysis.missing_requirements].slice(0, 3).map((value) => <li key={value}>{value}</li>)}</ul> : <p>No material gaps identified.</p>}</div>
                    </div>
                    <div className="match-card-actions">
                      <button className="button button-secondary" onClick={() => setSelectedJob(job.id)}>View Details</button>
                      <button className="button button-primary" disabled={generating === job.id} onClick={() => void generate(job)}><FileText size={16} /> {generating === job.id ? "Generating…" : "Generate Cover Letter"}</button>
                      {job.url && <a className="button button-ghost" href={job.url} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Original</a>}
                      <button className="button button-ghost dismiss-button" onClick={() => void dismiss(job)}>{job.dismissed ? <Undo2 size={16} /> : <ThumbsDown size={16} />} {job.dismissed ? "Restore" : "Dismiss"}</button>
                    </div>
                  </div>
                </article>
              );
            })}
            {data.total > data.items.length && <p className="results-limit-note">Showing the top {data.items.length} of {data.total} qualifying matches. Increase “Number of top matches” to display more.</p>}
          </div>
        )}
      </section>
      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={load} />
    </>
  );
}
