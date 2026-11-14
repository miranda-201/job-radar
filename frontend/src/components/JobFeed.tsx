import { useEffect, useState } from "react";
import { api } from "../api";
import { dateTooltip, isFresh, postedLabel } from "../dates";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  SOURCE_LABEL,
  type Category,
  type Job,
  type JobSort,
  type Page,
} from "../types";

const HOUR = 3_600_000;
const UNDERGRAD_KEY = "jobradar.undergradOnly";

function loadUndergradOnly(): boolean {
  try {
    return localStorage.getItem(UNDERGRAD_KEY) === "true";
  } catch {
    return false;
  }
}

const WINDOWS: { days: number; label: string }[] = [
  { days: 0, label: "Any time" },
  { days: 1, label: "Past 24 hours" },
  { days: 3, label: "Past 3 days" },
  { days: 7, label: "Past week" },
  { days: 30, label: "Past month" },
];

function ago(iso: string): string {
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / HOUR);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function JobFeed() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [within, setWithin] = useState(0);
  const [sort, setSort] = useState<JobSort>("posted");
  const [undergradOnly, setUndergradOnly] = useState(loadUndergradOnly);
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Page<Job> | null>(null);
  const [counts, setCounts] = useState<Partial<Record<Category, number>>>({});
  const [error, setError] = useState<string | null>(null);

  // Debounce typing so we don't query on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    api
      .categories()
      .then((cs) => setCounts(Object.fromEntries(cs.map((c) => [c.category, c.jobs]))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api
      .jobs({ q: query, category, postedWithinDays: within, sort, undergradOnly, page })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [query, category, within, sort, undergradOnly, page]);

  function toggleUndergrad() {
    const next = !undergradOnly;
    setUndergradOnly(next);
    setPage(0);
    try {
      localStorage.setItem(UNDERGRAD_KEY, String(next));
    } catch {
      /* preference just won't persist */
    }
  }

  async function track(job: Job) {
    try {
      await api.trackJob(job.id);
      setData((d) => d && { ...d, items: d.items.map((j) => (j.id === job.id ? { ...j, tracked: true } : j)) });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const reset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(0);
  };

  return (
    <section>
      <div className="toolbar">
        <input
          className="search"
          placeholder="Search role, company or location (e.g. backend, Visa, Chicago)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={within} onChange={(e) => reset(setWithin)(Number(e.target.value))} aria-label="Posted within">
          {WINDOWS.map((w) => (
            <option key={w.days} value={w.days}>
              {w.label}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(e) => reset(setSort)(e.target.value as JobSort)} aria-label="Sort">
          <option value="posted">Most recently posted</option>
          <option value="discovered">Most recently found</option>
        </select>
      </div>

      <div className="chips" role="group" aria-label="Role category">
        <button className={category === "" ? "chip active" : "chip"} onClick={() => reset(setCategory)("")}>
          All CS roles
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            className={category === c ? "chip active" : "chip"}
            onClick={() => reset(setCategory)(c)}
          >
            {CATEGORY_LABEL[c]}
            {counts[c] != null && <span className="chip-count">{counts[c]!.toLocaleString()}</span>}
          </button>
        ))}
        <span className="chip-divider" aria-hidden />
        <button
          className={undergradOnly ? "chip active" : "chip"}
          aria-pressed={undergradOnly}
          onClick={toggleUndergrad}
          title="Hide internships open only to Master's, PhD or MBA students"
        >
          {undergradOnly ? "✓ " : ""}Undergrad only
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {data && (
        <p className="muted small result-count">
          {data.totalItems.toLocaleString()} {undergradOnly ? "undergrad-eligible " : ""}internships
          {sort === "posted" ? ", newest posting first" : ", most recently found first"}
        </p>
      )}
      {data && data.items.length === 0 && (
        <div className="empty-state">
          <p>No postings match.</p>
          <p className="muted">
            Try widening the date range or clearing filters. New postings arrive every sweep; you can also{" "}
            <a href="#targets">watch more companies</a>.
          </p>
        </div>
      )}
      <ul className="feed">
        {data?.items.map((job) => (
          <li key={job.id} className="feed-row">
            <div className="feed-main">
              <div className="feed-title">
                {isFresh(job.postedAt) && job.postedDateSource !== "list" && <span className="badge new">NEW</span>}
                <a href={job.url} target="_blank" rel="noreferrer">
                  {job.title}
                </a>
              </div>
              <div className="muted small">
                <strong>{job.company}</strong>
                {job.location && ` · ${job.location}`}
              </div>
              <div className="feed-meta small">
                <span
                  className={job.postedDateSource === "list" ? "posted unverified" : "posted"}
                  title={dateTooltip(job.postedAt, job.postedDateSource)}
                >
                  {postedLabel(job.postedAt, job.postedDateSource)}
                </span>
                {job.category && <span className={`tag cat-${job.category}`}>{CATEGORY_LABEL[job.category]}</span>}
                {job.term && <span className="tag">{job.term}</span>}
                {job.degreeLevel === "graduate" && <span className="tag grad">Master's / PhD</span>}
                <span className="muted">
                  via {SOURCE_LABEL[job.source] ?? job.source} · found {ago(job.discoveredAt)}
                </span>
              </div>
            </div>
            {job.tracked ? (
              <span className="tracked">✓ On board</span>
            ) : (
              <button className="primary small" onClick={() => track(job)}>
                Track
              </button>
            )}
          </li>
        ))}
      </ul>
      {data && data.totalPages > 1 && (
        <div className="pager">
          <button className="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>
            ← Newer
          </button>
          <span className="muted">
            Page {page + 1} of {data.totalPages.toLocaleString()}
          </span>
          <button className="ghost" disabled={page + 1 >= data.totalPages} onClick={() => setPage(page + 1)}>
            Older →
          </button>
        </div>
      )}
    </section>
  );
}
