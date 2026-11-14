export const STATUSES = [
  "SAVED",
  "APPLIED",
  "ONLINE_ASSESSMENT",
  "INTERVIEWING",
  "OFFER",
  "REJECTED",
] as const;

export type Status = (typeof STATUSES)[number];

export const STATUS_LABEL: Record<Status, string> = {
  SAVED: "Saved",
  APPLIED: "Applied",
  ONLINE_ASSESSMENT: "Online Assessment",
  INTERVIEWING: "Interviewing",
  OFFER: "Offer",
  REJECTED: "Rejected",
};

export interface User {
  id: number;
  email: string;
  displayName: string;
}

export interface AuthResponse {
  token: string;
  expiresAt: string;
  user: User;
}

export interface Application {
  id: number;
  jobId: number | null;
  company: string;
  roleTitle: string;
  url: string | null;
  location: string | null;
  status: Status;
  position: number;
  notes: string | null;
  appliedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export type SourceType = "greenhouse" | "lever" | "workday" | "ashby" | "github_list";

export const SOURCE_LABEL: Record<SourceType, string> = {
  greenhouse: "Greenhouse",
  lever: "Lever",
  workday: "Workday",
  ashby: "Ashby",
  github_list: "GitHub list",
};

export const CATEGORIES = ["software", "data_ml", "cloud_infra", "security"] as const;
export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_LABEL: Record<Category, string> = {
  software: "Software",
  data_ml: "Data / AI / ML",
  cloud_infra: "Cloud / Infra",
  security: "Security",
};

export type JobSort = "posted" | "discovered";

/** employer = published by the company's ATS; approximate = "Posted N days ago"; list = added to a GitHub list. */
export type DateSource = "employer" | "approximate" | "list";

export interface Job {
  id: number;
  source: SourceType;
  company: string;
  title: string;
  location: string | null;
  url: string;
  postedAt: string | null;
  postedDateSource: DateSource | null;
  discoveredAt: string;
  category: Category | null;
  term: string | null;
  degreeLevel: "undergrad" | "graduate" | null;
  tracked: boolean;
}

export interface Page<T> {
  items: T[];
  page: number;
  size: number;
  totalItems: number;
  totalPages: number;
}

export interface Stats {
  total: number;
  applied: number;
  byStatus: Record<Status, number>;
}

export interface Target {
  id: string;
  company: string;
  source: SourceType;
  board: string;
  keywords: string[];
  cs_only: boolean;
  enabled: boolean;
}

export interface TargetResult {
  target_id: string;
  fetched: number;
  matched: number;
  new: number;
  error: string | null;
  duration_ms: number;
}

export interface ScrapeReport {
  started_at: string;
  finished_at: string;
  results: TargetResult[];
}
