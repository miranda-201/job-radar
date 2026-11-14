import type {
  Application,
  Category,
  JobSort,
  AuthResponse,
  Job,
  Page,
  ScrapeReport,
  Stats,
  Status,
  Target,
  TargetResult,
  User,
} from "./types";

const TOKEN_KEY = "jobradar.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  const res = await fetch(path, { ...init, headers });
  if (res.status === 401 && token) {
    setToken(null);
    onUnauthorized();
  }
  if (!res.ok) {
    // Spring returns problem+json ({detail}); FastAPI returns {detail}.
    let message = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  register: (email: string, displayName: string, password: string) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: json({ email, displayName, password }) }),
  login: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: json({ email, password }) }),
  me: () => request<User>("/api/auth/me"),

  board: () => request<Application[]>("/api/applications"),
  stats: () => request<Stats>("/api/applications/stats"),
  trackJob: (jobId: number) => request<Application>("/api/applications", { method: "POST", body: json({ jobId }) }),
  createManual: (a: { company: string; roleTitle: string; url?: string; status?: Status; notes?: string }) =>
    request<Application>("/api/applications", { method: "POST", body: json(a) }),
  updateApplication: (id: number, patch: Partial<Pick<Application, "notes" | "url" | "location">>) =>
    request<Application>(`/api/applications/${id}`, { method: "PATCH", body: json(patch) }),
  move: (id: number, status: Status, position: number) =>
    request<Application>(`/api/applications/${id}/move`, { method: "PUT", body: json({ status, position }) }),
  deleteApplication: (id: number) => request<void>(`/api/applications/${id}`, { method: "DELETE" }),

  jobs: (params: {
    q?: string;
    category?: Category | "";
    postedWithinDays?: number;
    sort?: JobSort;
    undergradOnly?: boolean;
    page?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.category) qs.set("category", params.category);
    if (params.postedWithinDays) qs.set("postedWithinDays", String(params.postedWithinDays));
    qs.set("sort", params.sort ?? "posted");
    if (params.undergradOnly) qs.set("undergradOnly", "true");
    qs.set("page", String(params.page ?? 0));
    return request<Page<Job>>(`/api/jobs?${qs}`);
  },
  companies: () => request<{ company: string; jobs: number }[]>("/api/jobs/companies"),
  categories: () => request<{ category: Category; jobs: number }[]>("/api/jobs/categories"),

  targets: () => request<Target[]>("/api/scraper/targets"),
  createTarget: (t: Target) => request<Target>("/api/scraper/targets", { method: "POST", body: json(t) }),
  updateTarget: (t: Target) => request<Target>(`/api/scraper/targets/${t.id}`, { method: "PUT", body: json(t) }),
  deleteTarget: (id: string) => request<void>(`/api/scraper/targets/${id}`, { method: "DELETE" }),
  scrapeAll: () => request<ScrapeReport>("/api/scraper/scrape", { method: "POST" }),
  scrapeOne: (id: string) => request<TargetResult>(`/api/scraper/targets/${id}/scrape`, { method: "POST" }),
  lastReport: () => request<ScrapeReport | null>("/api/scraper/scrape/last"),
};
