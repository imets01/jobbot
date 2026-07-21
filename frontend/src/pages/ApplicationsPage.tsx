import { ChevronRight, ClipboardList } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { JobDrawer } from "../components/JobDrawer";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/Ui";
import type { ApplicationBoardItem, ApplicationStatus } from "../types";
import { APPLICATION_STATUSES } from "../utils";

function ApplicationCard({ item, onOpen }: { item: ApplicationBoardItem; onOpen: () => void }) {
  return (
    <article className="application-card">
      <button className="application-card-title" onClick={onOpen}>
        <span><strong>{item.job.title}</strong><small>{item.job.company}</small></span>
        <ChevronRight size={16} />
      </button>
    </article>
  );
}

export function ApplicationsPage() {
  const [items, setItems] = useState<ApplicationBoardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedJob, setSelectedJob] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      setItems(await api.applications());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load applications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("jobbot:refresh", load);
    return () => window.removeEventListener("jobbot:refresh", load);
  }, [load]);

  const grouped = useMemo(() => {
    const groups = new Map<ApplicationStatus, ApplicationBoardItem[]>(APPLICATION_STATUSES.map((status) => [status, []]));
    items.forEach((item) => groups.get(item.application.status)?.push(item));
    return groups;
  }, [items]);

  return (
    <>
      <PageHeader eyebrow="Application workflow" title="Applications" description="Scan your pipeline at a glance. Open a job to update its status and details." />
      {loading ? <LoadingState label="Loading application board" /> : error ? <ErrorState message={error} onRetry={load} /> : !items.length ? (
        <div className="panel"><EmptyState title="Your board is empty" description="Open a job, set its status to Saved or Interested, and it will appear here." icon={ClipboardList} /></div>
      ) : (
        <div className="kanban-board" aria-label="Application workflow board">
          {APPLICATION_STATUSES.map((status) => (
            <section className="kanban-column" key={status}>
              <header><span>{status}</span><strong>{grouped.get(status)?.length ?? 0}</strong></header>
              <div className="kanban-cards">
                {grouped.get(status)?.length ? grouped.get(status)!.map((item) => <ApplicationCard key={item.application.id} item={item} onOpen={() => setSelectedJob(item.job.id)} />) : <p className="kanban-empty">No jobs here</p>}
              </div>
            </section>
          ))}
        </div>
      )}
      <JobDrawer jobId={selectedJob} onClose={() => setSelectedJob(null)} onChanged={load} />
    </>
  );
}
