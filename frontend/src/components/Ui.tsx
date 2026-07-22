import {
  Archive,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Inbox,
  LoaderCircle,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import type { ApplicationStatus, Job, RunStatus } from "../types";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state-panel" role="status">
      <LoaderCircle className="spin" size={28} />
      <p>{label}…</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={24} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-panel state-error" role="alert">
      <CircleAlert size={26} />
      <div>
        <strong>Something went wrong</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button className="button button-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: number | string;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "accent" | "success" | "warning";
}) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <div className="stat-icon">
        <Icon size={20} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>{detail}</span>
      </div>
    </article>
  );
}

export function MatchBadges({ job }: { job: Job }) {
  const result = job.latest_analysis;
  if (!result) return <span className="badge badge-neutral">Needs review</span>;
  if (result.error_message) return <span className="badge badge-danger">Analysis failed</span>;
  if (result.match_score !== null) {
    const tone = result.match_score >= 90 ? "success" : result.match_score >= 75 ? "info" : result.match_score >= 60 ? "warning" : "neutral";
    return (
      <span className="badge-row">
        <span className={`badge badge-${tone}`}><Sparkles size={13} /> {result.recommendation_label ?? `${result.match_score} match`}</span>
        {!result.qualifies && <span className="badge badge-neutral">Filtered</span>}
      </span>
    );
  }
  return (
    <span className="badge-row">
      {result.is_good_match && result.seniority_ok ? (
        <span className="badge badge-success"><Sparkles size={13} /> Good match</span>
      ) : (
        <span className="badge badge-neutral">Not suitable</span>
      )}
      {result.seniority_ok ? (
        <span className="badge badge-info"><CheckCircle2 size={13} /> Seniority OK</span>
      ) : (
        <span className="badge badge-warning"><Clock3 size={13} /> Seniority high</span>
      )}
    </span>
  );
}

export function ApplicationBadge({ status }: { status?: ApplicationStatus | null }) {
  if (!status) return <span className="badge badge-neutral">Untracked</span>;
  const slug = status.toLowerCase().replaceAll(" ", "-");
  return (
    <span className={`badge application-${slug}`}>
      {status === "Archived" && <Archive size={13} />}
      {status}
    </span>
  );
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <span className={`badge run-${status}`}>{status}</span>;
}
