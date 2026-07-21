import type {
  Application,
  ApplicationBoardItem,
  ApplicationStatus,
  CandidateProfile,
  DashboardSummary,
  Job,
  JobDetail,
  Paginated,
  Run,
  RunRequest,
  RunResult,
  Settings,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? body?.message ?? `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function toQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const api = {
  dashboard: () => request<DashboardSummary>("/api/dashboard"),
  settings: () => request<Settings>("/api/settings"),
  jobs: (params: Record<string, string | number | null | undefined>) =>
    request<Paginated<Job>>(`/api/jobs${toQuery(params)}`),
  companies: () => request<string[]>("/api/jobs/companies"),
  job: (id: number) => request<JobDetail>(`/api/jobs/${id}`),
  archiveJob: (id: number, archived: boolean) =>
    request<Job>(`/api/jobs/${id}/archive`, {
      method: "PATCH",
      body: JSON.stringify({ archived }),
    }),
  saveApplication: (
    id: number,
    payload: {
      status: ApplicationStatus;
      application_date: string | null;
      next_follow_up_date: string | null;
      notes: string;
    },
  ) =>
    request<Application>(`/api/jobs/${id}/application`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  applications: () => request<ApplicationBoardItem[]>("/api/applications"),
  profile: () => request<CandidateProfile>("/api/profile"),
  saveProfile: (content: string) =>
    request<CandidateProfile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  resetProfile: () =>
    request<CandidateProfile>("/api/profile/reset", { method: "POST" }),
  startScraper: (payload: RunRequest) =>
    request<Run>("/api/runs/scraper", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startAnalyzer: () => request<Run>("/api/runs/analyzer", { method: "POST" }),
  startFull: (payload: RunRequest) =>
    request<Run>("/api/runs/full", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reanalyze: (id: number) =>
    request<Run>(`/api/jobs/${id}/reanalyze`, { method: "POST" }),
  activeRun: () => request<Run | null>("/api/runs/active"),
  run: (id: string) => request<Run>(`/api/runs/${id}`),
  runs: (params: Record<string, string | number | null | undefined>) =>
    request<Paginated<Run>>(`/api/runs${toQuery(params)}`),
  runResults: (id: string) => request<RunResult[]>(`/api/runs/${id}/results`),
};
