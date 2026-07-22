import { Activity, CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Run } from "../types";
import { runProgress } from "../utils";
import { useToast } from "./ToastProvider";

export function ActiveRunBanner() {
  const [run, setRun] = useState<Run | null>(null);
  const seenRun = useRef<string | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    let disposed = false;
    const poll = async () => {
      try {
        const active = await api.activeRun();
        if (disposed) return;
        if (active) {
          seenRun.current = active.id;
          setRun(active);
        } else if (seenRun.current) {
          const completed = await api.run(seenRun.current);
          if (disposed) return;
          setRun(completed);
          showToast(
            completed.status === "completed"
              ? "Job search completed"
              : completed.error_details ?? "Run failed",
            completed.status === "completed" ? "success" : "error",
          );
          window.dispatchEvent(new CustomEvent("jobbot:refresh"));
          seenRun.current = null;
          window.setTimeout(() => setRun(null), 4000);
        }
      } catch {
        // The page-level error state handles API availability.
      }
    };
    poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [showToast]);

  if (!run) return null;
  const running = run.status === "pending" || run.status === "running";
  const progress = runProgress(run);
  const Icon = running ? LoaderCircle : run.status === "completed" ? CheckCircle2 : CircleAlert;
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
      <Activity size={17} aria-hidden="true" />
    </div>
  );
}
