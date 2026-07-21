import type { ApplicationStatus, Job, Run } from "./types";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "Saved",
  "Interested",
  "Applied",
  "Interviewing",
  "Offer",
  "Rejected",
  "Withdrawn",
  "Archived",
];

export function formatDate(value: string | null | undefined, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function relativeDate(value: string | null | undefined) {
  if (!value) return "Never";
  const delta = new Date(value).getTime() - Date.now();
  const days = Math.round(delta / 86_400_000);
  if (days === 0) return "Today";
  if (days === -1) return "Yesterday";
  if (days === 1) return "Tomorrow";
  return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(days, "day");
}

export function isGoodMatch(job: Job) {
  return Boolean(
    job.latest_analysis?.error_message === null &&
      job.latest_analysis?.is_good_match &&
      job.latest_analysis?.seniority_ok,
  );
}

export function runProgress(run: Run) {
  if (run.jobs_queued > 0) {
    return Math.min(100, Math.round((run.jobs_analyzed / run.jobs_queued) * 100));
  }
  return run.status === "completed" ? 100 : 12;
}

export function todayInput() {
  return new Date().toISOString().slice(0, 10);
}
