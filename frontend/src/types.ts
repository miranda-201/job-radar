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

export interface Job {
  id: number;
  source: "greenhouse" | "lever" | "workday";
  company: string;
  title: string;
  location: string | null;
  url: string;
  postedAt: string | null;
  discoveredAt: string;
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
  source: "greenhouse" | "lever" | "workday";
  board: string;
  keywords: string[];
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
