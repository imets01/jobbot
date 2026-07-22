export type ApplicationStatus =
  | "Saved"
  | "Interested"
  | "Applied"
  | "Interviewing"
  | "Offer"
  | "Rejected"
  | "Withdrawn"
  | "Archived";

export type RunType = "search" | "scraper" | "analyzer" | "full";
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
  match_score: number | null;
  qualifies: boolean | null;
  recommendation_label: string | null;
  short_explanation: string;
  score_breakdown: Record<string, number>;
  matched_strengths: string[];
  weak_areas: string[];
  potential_concerns: string[];
  missing_requirements: string[];
  suggested_resume_keywords: string[];
  application_strategy: string;
  work_model: string | null;
  required_experience_years: number | null;
  required_languages: string[];
  critical_gaps: string[];
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
  dismissed: boolean;
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

export interface LanguageEntry {
  language: string;
  proficiency: string;
}

export interface MentionPreferences {
  education: boolean;
  certifications: boolean;
  internships: boolean;
  projects: boolean;
  customer_facing_experience: boolean;
  technical_skills: boolean;
  career_motivation: boolean;
}

export interface StructuredCandidateProfile {
  full_name: string;
  email: string;
  current_location: string;
  linkedin_url: string;
  portfolio_url: string;
  education: string[];
  work_experience: string[];
  skills: string[];
  certifications: string[];
  languages: LanguageEntry[];
  projects: string[];
  professional_summary: string;
  role_keywords: string[];
  preferred_seniority: string;
  preferred_industries: string[];
  preferred_locations: string[];
  work_model_preferences: string[];
  years_total_experience: number;
  years_software_engineering: number;
  years_cloud_experience: number;
  years_customer_facing: number;
  base_cover_letter: string;
  career_motivation: string;
  key_achievements: string[];
  projects_to_highlight: string[];
  writing_tone: string;
  mention_preferences: MentionPreferences;
}

export interface CVDocument {
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  extracted_at: string | null;
  has_raw_text: boolean;
}

export interface CandidateProfile {
  profile: StructuredCandidateProfile;
  version: number;
  updated_at: string;
  cv: CVDocument | null;
}

export interface CVExtraction {
  extracted_profile: StructuredCandidateProfile;
  cv: CVDocument;
}

export interface SearchControls {
  keywords: string[];
  target_locations: string[];
  work_models: string[];
  minimum_match_score: number;
  number_of_jobs: number;
  include_stretch_roles: boolean;
  max_required_experience_years: number | null;
  exclude_unavailable_languages: boolean;
  exclude_outside_locations: boolean;
  sources: string[];
  updated_at?: string;
}

export interface SearchSourceCapability {
  name: string;
  available: boolean;
  note: string;
}

export interface CoverLetter {
  id: number;
  job_id: number;
  analysis_result_id: number | null;
  candidate_profile_version: number;
  content: string;
  gemini_model: string;
  created_at: string;
  updated_at: string;
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

export interface ApplicationBoardItem {
  job: Job;
  application: Application;
}
