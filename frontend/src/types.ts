export type ApplicationStatus =
  | "Saved"
  | "Interested"
  | "Applied"
  | "Interviewing"
  | "Offer"
  | "Rejected"
  | "Withdrawn"
  | "Archived";

export type RunType = "scraper" | "analyzer" | "full";
export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface AnalysisResult {
  id: number;
  job_id: number;
  run_id: string;
  created_at: string;
  candidate_profile_snapshot: string;
  candidate_profile_version: number;
  is_good_match: boolean | null;
  seniority_ok: boolean | null;
  verdict: string;
  gemini_model: string;
  error_message: string | null;
}

export interface Application {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  application_date: string | null;
  next_follow_up_date: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: number;
  title: string;
  company: string;
  url: string | null;
  location: string | null;
  source: string;
  first_seen: string;
  last_seen: string;
  archived: boolean;
  latest_analysis: AnalysisResult | null;
  application: Application | null;
}

export interface JobDetail extends Job {
  description: string;
  content_hash: string;
  analyses: AnalysisResult[];
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface Run {
  id: string;
  run_type: RunType;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  jobs_discovered: number;
  jobs_queued: number;
  jobs_analyzed: number;
  good_matches: number;
  failures: number;
  error_details: string | null;
}

export interface RunResult {
  job: Job;
  analysis: AnalysisResult;
}

export interface CandidateProfile {
  content: string;
  version: number;
  updated_at: string;
  is_default: boolean;
}

export interface DashboardSummary {
  total_jobs: number;
  good_matches: number;
  waiting_for_analysis: number;
  applications_submitted: number;
  follow_ups_due: number;
  recent_good_matches: Job[];
  application_statuses: { status: string; count: number }[];
  active_run: Run | null;
}

export interface Settings {
  default_role: string;
  default_location: string;
  default_max_jobs: number;
  gemini_model: string;
}

export interface ApplicationBoardItem {
  job: Job;
  application: Application;
}

export interface RunRequest {
  role: string;
  location: string;
  max_jobs: number;
}
