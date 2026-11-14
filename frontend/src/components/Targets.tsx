import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import type { Target, TargetResult } from "../types";

const BOARD_HINT: Record<Target["source"], string> = {
  greenhouse: "board token, e.g. stripe (from boards.greenhouse.io/stripe)",
  lever: "company slug, e.g. palantir (from jobs.lever.co/palantir)",
  workday: "career site URL, e.g. https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
};

const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 63);

export default function Targets() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [results, setResults] = useState<Record<string, TargetResult>>({});
  const [scanning, setScanning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [company, setCompany] = useState("");
  const [source, setSource] = useState<Target["source"]>("greenhouse");
  const [board, setBoard] = useState("");
  const [keywords, setKeywords] = useState("intern, new grad");

  async function load() {
    try {
      setTargets(await api.targets());
      const last = await api.lastReport();
      if (last) setResults(Object.fromEntries(last.results.map((r) => [r.target_id, r])));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function scanAll() {
    setScanning("*");
    try {
      const report = await api.scrapeAll();
      setResults(Object.fromEntries(report.results.map((r) => [r.target_id, r])));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(null);
    }
  }

  async function scanOne(id: string) {
    setScanning(id);
    try {
      const r = await api.scrapeOne(id);
      setResults((cur) => ({ ...cur, [id]: r }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(null);
    }
  }

  async function toggle(t: Target) {
    const updated = await api.updateTarget({ ...t, enabled: !t.enabled });
    setTargets((cur) => cur.map((x) => (x.id === t.id ? updated : x)));
  }

  async function remove(t: Target) {
    if (!confirm(`Stop watching ${t.company}?`)) return;
    await api.deleteTarget(t.id);
    setTargets((cur) => cur.filter((x) => x.id !== t.id));
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.createTarget({
        id: slugify(`${company}-${source}`),
        company: company.trim(),
        source,
        board: board.trim(),
        keywords: keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
        enabled: true,
      });
      setTargets((cur) => [...cur, created].sort((a, b) => a.id.localeCompare(b.id)));
      setCompany("");
      setBoard("");
      scanOne(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <div className="toolbar">
        <p className="muted">
          The scraper polls these career pages on a schedule and publishes new matches to the Job Radar.
        </p>
        <button className="primary" onClick={scanAll} disabled={scanning !== null}>
          {scanning === "*" ? "Scanning…" : "Scan all now"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}

      <form className="inline-form" onSubmit={add}>
        <input placeholder="Company name" required value={company} onChange={(e) => setCompany(e.target.value)} />
        <select value={source} onChange={(e) => setSource(e.target.value as Target["source"])}>
          <option value="greenhouse">Greenhouse</option>
          <option value="lever">Lever</option>
          <option value="workday">Workday</option>
        </select>
        <input
          className="grow"
          placeholder={BOARD_HINT[source]}
          required
          value={board}
          onChange={(e) => setBoard(e.target.value)}
        />
        <input
          placeholder="Keywords (comma separated)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />
        <button className="primary">Watch</button>
      </form>

      <table className="targets">
        <thead>
          <tr>
            <th>Company</th>
            <th>Source</th>
            <th>Keywords</th>
            <th>Last scan</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {targets.map((t) => {
            const r = results[t.id];
            return (
              <tr key={t.id} className={t.enabled ? "" : "disabled"}>
                <td>
                  <strong>{t.company}</strong>
                </td>
                <td>
                  <span className={`src src-${t.source}`}>{t.source}</span>
                </td>
                <td className="small">{t.keywords.length ? t.keywords.join(", ") : <em>all postings</em>}</td>
                <td className="small">
                  {!r ? (
                    <span className="muted">—</span>
                  ) : r.error ? (
                    <span className="error-text" title={r.error}>
                      failed
                    </span>
                  ) : (
                    <span>
                      {r.matched} matching of {r.fetched} · <strong>{r.new} new</strong> · {r.duration_ms} ms
                    </span>
                  )}
                </td>
                <td className="actions">
                  <button className="ghost small" onClick={() => scanOne(t.id)} disabled={scanning !== null}>
                    {scanning === t.id ? "…" : "Scan"}
                  </button>
                  <button className="ghost small" onClick={() => toggle(t)}>
                    {t.enabled ? "Pause" : "Resume"}
                  </button>
                  <button className="ghost small danger" onClick={() => remove(t)}>
                    Remove
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
