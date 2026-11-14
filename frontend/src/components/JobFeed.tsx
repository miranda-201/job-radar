import { useEffect, useState } from "react";
import { api } from "../api";
import type { Job, Page } from "../types";

const HOUR = 3_600_000;

function ago(iso: string): string {
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / HOUR);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function JobFeed() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Page<Job> | null>(null);
  const [companies, setCompanies] = useState<{ company: string; jobs: number }[]>([]);
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
    api.companies().then(setCompanies).catch(() => {});
  }, []);

  useEffect(() => {
    api
      .jobs({ q: query, company, page })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [query, company, page]);

  async function track(job: Job) {
    try {
      await api.trackJob(job.id);
      setData((d) => d && { ...d, items: d.items.map((j) => (j.id === job.id ? { ...j, tracked: true } : j)) });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section>
      <div className="toolbar">
        <input
          className="search"
          placeholder="Search titles or locations (e.g. backend, Chicago, 2027)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All companies</option>
          {companies.map((c) => (
            <option key={c.company} value={c.company}>
              {c.company} ({c.jobs})
            </option>
          ))}
        </select>
      </div>
      {error && <div className="error">{error}</div>}
      {data && data.items.length === 0 && (
        <div className="empty-state">
          <p>No postings yet.</p>
          <p className="muted">
            The scraper sweeps every watched company on a schedule. Add companies or trigger a scan from{" "}
            <a href="#targets">Watched Companies</a>.
          </p>
        </div>
      )}
      <ul className="feed">
        {data?.items.map((job) => {
          const fresh = Date.now() - new Date(job.discoveredAt).getTime() < 24 * HOUR;
          return (
            <li key={job.id} className="feed-row">
              <div className="feed-main">
                <div className="feed-title">
                  {fresh && <span className="badge new">NEW</span>}
                  <a href={job.url} target="_blank" rel="noreferrer">
                    {job.title}
                  </a>
                </div>
                <div className="muted small">
                  <strong>{job.company}</strong>
                  {job.location && ` · ${job.location}`} · found {ago(job.discoveredAt)} ·{" "}
                  <span className={`src src-${job.source}`}>{job.source}</span>
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
          );
        })}
      </ul>
      {data && data.totalPages > 1 && (
        <div className="pager">
          <button className="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>
            ← Newer
          </button>
          <span className="muted">
            Page {page + 1} of {data.totalPages} · {data.totalItems} postings
          </span>
          <button className="ghost" disabled={page + 1 >= data.totalPages} onClick={() => setPage(page + 1)}>
            Older →
          </button>
        </div>
      )}
    </section>
  );
}
