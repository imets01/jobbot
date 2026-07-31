import { Activity, CheckCircle2, CircleAlert, LoaderCircle, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Run } from "../types";
import { runProgress } from "../utils";
import { useToast } from "./ToastProvider";

export function ActiveRunBanner() {
  const [run, setRun] = useState<Run | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const seenRun = useRef<string | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let requestController: AbortController | null = null;
    let clearTimer: number | null = null;
    const poll = async () => {
      if (inFlight) return;
      inFlight = true;
      requestController = new AbortController();
      try {
        const active = await api.activeRun(requestController.signal);
        if (disposed) return;
        if (active) {
          seenRun.current = active.id;
          setRun(active);
          window.dispatchEvent(new CustomEvent("jobbot:run-progress", { detail: active }));
        } else if (seenRun.current) {
          const completed = await api.run(seenRun.current, requestController.signal);
          if (disposed) return;
          setRun(completed);
          if (completed.status === "completed") {
            showToast("Job search completed", "success");
          } else if (completed.status === "cancelled") {
            showToast("Job search cancelled", "info");
          } else {
            showToast(completed.error_details ?? "Run failed", "error");
          }
          setCancelling(false);
          window.dispatchEvent(new CustomEvent("jobbot:refresh"));
          seenRun.current = null;
          clearTimer = window.setTimeout(() => setRun(null), 4000);
        }
      } catch {
        // The page-level error state handles API availability.
      } finally {
        inFlight = false;
      }
    };
    void poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      disposed = true;
      requestController?.abort();
      window.clearInterval(timer);
      if (clearTimer !== null) window.clearTimeout(clearTimer);
    };
  }, [showToast]);

  if (!run) return null;
  const running = run.status === "pending" || run.status === "running";
  const progress = runProgress(run);
  const Icon = running ? LoaderCircle : run.status === "completed" ? CheckCircle2 : CircleAlert;
  const cancel = async () => {
    setCancelling(true);
    try {
      await api.cancelRun(run.id);
      showToast("Cancellation requested", "info");
    } catch (err) {
      setCancelling(false);
      showToast(err instanceof Error ? err.message : "Could not cancel the search", "error");
    }
  };
  return (
    <div className={`run-banner ${running ? "is-running" : `is-${run.status}`}`} role="status">
      <div className="run-banner-copy">
        <span className="run-banner-icon">
          <Icon className={running ? "spin" : ""} size={18} />
        </span>
        <div>
          <strong>{running ? "Job search in progress" : `Job search ${run.status}`}</strong>
          <span>
            {run.jobs_analyzed}/{run.jobs_queued || run.jobs_discovered || 0} scored · {run.good_matches} qualifying matches
          </span>
        </div>
      </div>
      <div className="progress-track" aria-label={`${progress}% complete`}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="run-banner-actions">
        {running && <button className="button button-ghost button-small" disabled={cancelling} onClick={() => void cancel()}><Square size={13} /> {cancelling ? "Stopping…" : "Stop"}</button>}
        <Activity size={17} aria-hidden="true" />
      </div>
    </div>
  );
}
