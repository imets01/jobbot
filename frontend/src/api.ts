import type {
  Application,
  ApplicationBoardItem,
  ApplicationStatus,
  CandidateProfile,
  CoverLetter,
  CVDocument,
  CVExtraction,
  DashboardSummary,
  Job,
  JobDetail,
  Paginated,
  Run,
  RunResult,
  SearchControls,
  SearchSourceCapability,
  StructuredCandidateProfile,
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

function errorMessage(body: unknown, status: number) {
  if (!body || typeof body !== "object") return `Request failed (${status})`;
  const record = body as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const message = (detail as Record<string, unknown>).message;
    if (typeof message === "string") return message;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const issue = item as Record<string, unknown>;
        const message = typeof issue.msg === "string" ? issue.msg : "Invalid value";
        const location = Array.isArray(issue.loc)
          ? issue.loc.filter((part) => part !== "body").join(" → ")
          : "";
        return location ? `${location}: ${message}` : message;
      })
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (typeof record.message === "string") return record.message;
  return `Request failed (${status})`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(errorMessage(body, response.status), response.status);
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
  dashboard: (signal?: AbortSignal) => request<DashboardSummary>("/api/dashboard", { signal }),
  jobs: (params: Record<string, string | number | null | undefined>) =>
    request<Paginated<Job>>(`/api/jobs${toQuery(params)}`),
  companies: () => request<string[]>("/api/jobs/companies"),
  job: (id: number) => request<JobDetail>(`/api/jobs/${id}`),
  archiveJob: (id: number, archived: boolean) =>
    request<Job>(`/api/jobs/${id}/archive`, {
      method: "PATCH",
      body: JSON.stringify({ archived }),
    }),
  dismissJob: (id: number, dismissed: boolean) =>
    request<Job>(`/api/jobs/${id}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify({ dismissed }),
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
  untrackApplication: (id: number) =>
    request<void>(`/api/jobs/${id}/application`, { method: "DELETE" }),
  applications: () => request<ApplicationBoardItem[]>("/api/applications"),
  profile: () => request<CandidateProfile>("/api/profile"),
  saveProfile: (profile: StructuredCandidateProfile) =>
    request<CandidateProfile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ profile }),
    }),
  resetProfile: () =>
    request<CandidateProfile>("/api/profile/reset", { method: "POST" }),
  uploadCV: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<CVDocument>("/api/profile/cv", { method: "POST", body });
  },
  extractProfileFromCV: () =>
    request<CVExtraction>("/api/profile/cv/extract", { method: "POST" }),
  searchControls: () => request<SearchControls>("/api/search-controls"),
  saveSearchControls: (controls: SearchControls) =>
    request<SearchControls>("/api/search-controls", {
      method: "PUT",
      body: JSON.stringify(controls),
    }),
  searchSources: () => request<SearchSourceCapability[]>("/api/search-controls/sources"),
  startSearch: (controls?: SearchControls) =>
    request<Run>("/api/runs/search", {
      method: "POST",
      body: JSON.stringify({ controls: controls ?? null }),
    }),
  reanalyze: (id: number) =>
    request<Run>(`/api/jobs/${id}/reanalyze`, { method: "POST" }),
  coverLetter: (id: number) => request<CoverLetter | null>(`/api/jobs/${id}/cover-letter`),
  generateCoverLetter: (id: number) =>
    request<CoverLetter>(`/api/jobs/${id}/cover-letter`, { method: "POST" }),
  saveCoverLetter: (jobId: number, letterId: number, content: string) =>
    request<CoverLetter>(`/api/jobs/${jobId}/cover-letter/${letterId}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  activeRun: (signal?: AbortSignal) => request<Run | null>("/api/runs/active", { signal }),
  run: (id: string, signal?: AbortSignal) => request<Run>(`/api/runs/${id}`, { signal }),
  cancelRun: (id: string) =>
    request<Run>(`/api/runs/${id}/cancel`, { method: "POST" }),
  runs: (params: Record<string, string | number | null | undefined>) =>
    request<Paginated<Run>>(`/api/runs${toQuery(params)}`),
  runResults: (id: string) => request<RunResult[]>(`/api/runs/${id}/results`),
  removeRun: (id: string) =>
    request<{ disposition: "hidden" | "deleted" }>(`/api/runs/${id}`, {
      method: "DELETE",
    }),
};
