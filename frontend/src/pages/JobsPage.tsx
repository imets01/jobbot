import { ChevronLeft, ChevronRight, Filter, Search, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import { ApplicationBadge, EmptyState, ErrorState, LoadingState, MatchBadges, PageHeader } from "../components/Ui";
import type { ApplicationStatus, Job, Paginated } from "../types";
import { APPLICATION_STATUSES, formatDate } from "../utils";

const initialFilters = {
  match: "",
  seniority: "",
  analyzed: "",
  application_status: "",
  company: "",
  archived: "active",
  sort: "newest",
  direction: "desc",
};

export function JobsPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<Paginated<Job> | null>(null);
  const [companies, setCompanies] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [filters, setFilters] = useState({
    ...initialFilters,
    match: searchParams.get("match") ?? "",
  });
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.jobs({ page, page_size: 20, search, ...filters });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load jobs");
    } finally {
      setLoading(false);
    }
  }, [filters, page, search]);

  useEffect(() => {
    load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  useEffect(() => {
    api.companies().then(setCompanies).catch(() => setCompanies([]));
  }, []);

  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([key, value]) => key !== "sort" && key !== "direction" && key !== "archived" && value).length + (filters.archived !== "active" ? 1 : 0),
    [filters],
  );

  const updateFilter = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters(initialFilters);
    setSearchInput("");
    setPage(1);
  };

  return (
    <>
      <PageHeader
        eyebrow="Opportunity library"
        title="Jobs"
        description="One row per unique job, enriched with the latest Gemini verdict and application state."
        actions={
          <button className="button button-secondary filter-toggle" onClick={() => setFilterOpen((value) => !value)}>
            <Filter size={16} /> Filters {activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}
          </button>
        }
      />

      <section className="panel jobs-panel">
        <div className="jobs-toolbar">
          <label className="search-field">
            <Search size={17} />
            <span className="sr-only">Search jobs</span>
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Search title or company…" />
            {searchInput && <button className="icon-button" onClick={() => setSearchInput("")} aria-label="Clear search"><X size={15} /></button>}
          </label>
          <label className="compact-select">
            <span>Sort</span>
            <select value={filters.sort} onChange={(e) => updateFilter("sort", e.target.value)}>
              <option value="newest">Newest</option>
              <option value="last_analyzed">Last analyzed</option>
              <option value="company">Company</option>
              <option value="match_quality">Match quality</option>
            </select>
          </label>
          <button className="button button-ghost" onClick={() => updateFilter("direction", filters.direction === "desc" ? "asc" : "desc")}>
            {filters.direction === "desc" ? "Descending" : "Ascending"}
          </button>
        </div>

        <div className={`filter-drawer ${filterOpen ? "is-open" : ""}`}>
          <div className="filter-grid">
            <label>Match<select value={filters.match} onChange={(e) => updateFilter("match", e.target.value)}><option value="">All</option><option value="good">Good match</option><option value="not">Not a match</option></select></label>
            <label>Seniority<select value={filters.seniority} onChange={(e) => updateFilter("seniority", e.target.value)}><option value="">All</option><option value="suitable">Suitable</option><option value="unsuitable">Unsuitable</option></select></label>
            <label>Analysis<select value={filters.analyzed} onChange={(e) => updateFilter("analyzed", e.target.value)}><option value="">All</option><option value="yes">Analyzed</option><option value="no">Not analyzed</option></select></label>
            <label>Application<select value={filters.application_status} onChange={(e) => updateFilter("application_status", e.target.value)}><option value="">All statuses</option>{APPLICATION_STATUSES.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Company<select value={filters.company} onChange={(e) => updateFilter("company", e.target.value)}><option value="">All companies</option>{companies.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Archive<select value={filters.archived} onChange={(e) => updateFilter("archived", e.target.value)}><option value="active">Active jobs</option><option value="archived">Archived only</option><option value="all">All jobs</option></select></label>
          </div>
          <button className="text-link" onClick={clearFilters}><SlidersHorizontal size={14} /> Reset filters</button>
        </div>

        {loading && !data ? (
          <LoadingState label="Loading jobs" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data?.items.length ? (
          <EmptyState title="No jobs match these filters" description="Clear a filter or run the scraper to discover more roles." />
        ) : (
          <>
            <div className="desktop-job-table">
              <table>
                <thead><tr><th>Role</th><th>Assessment</th><th>Application</th><th>Last seen</th></tr></thead>
                <tbody>
                  {data.items.map((job) => (
                    <tr key={job.id} tabIndex={0} onClick={() => setSelectedJob(job.id)} onKeyDown={(e) => e.key === "Enter" && setSelectedJob(job.id)}>
                      <td><div className="job-title-cell"><span className="company-avatar">{job.company.slice(0, 1).toUpperCase()}</span><div><strong>{job.title}</strong><span>{job.company} · {job.location ?? "Location unavailable"}</span></div></div></td>
                      <td><MatchBadges job={job} /></td>
                      <td><ApplicationBadge status={job.application?.status as ApplicationStatus | undefined} /></td>
                      <td><span className="muted">{formatDate(job.last_seen)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mobile-job-list">
              {data.items.map((job) => (
                <button className="mobile-job-card" key={job.id} onClick={() => setSelectedJob(job.id)}>
                  <div className="job-card-top"><span className="company-avatar">{job.company.slice(0, 1).toUpperCase()}</span><ApplicationBadge status={job.application?.status} /></div>
                  <h3>{job.title}</h3><p>{job.company}</p>
                  <MatchBadges job={job} />
                  <span className="muted">Last seen {formatDate(job.last_seen)}</span>
                </button>
              ))}
            </div>
            <footer className="pagination">
              <span>Showing {(data.page - 1) * data.page_size + 1}–{Math.min(data.total, data.page * data.page_size)} of {data.total}</span>
              <div>
                <button className="icon-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous page"><ChevronLeft size={18} /></button>
                <span>Page {data.page} of {data.pages}</span>
                <button className="icon-button" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)} aria-label="Next page"><ChevronRight size={18} /></button>
              </div>
            </footer>
          </>
        )}
      </section>

      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={load} />
    </>
  );
}
