import { useCallback, useEffect, useMemo, useState, type DragEvent, type FormEvent } from "react";
import { api } from "../api";
import { applyMove, daysSince, groupByStatus } from "../board";
import { STATUSES, STATUS_LABEL, type Application, type Status } from "../types";

interface DropTarget {
  status: Status;
  index: number;
}

export default function Board() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);
  const [drop, setDrop] = useState<DropTarget | null>(null);
  const [adding, setAdding] = useState(false);

  const reload = useCallback(async () => {
    try {
      setApps(await api.board());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const columns = useMemo(() => groupByStatus(apps), [apps]);
  const applied = apps.filter((a) => a.status !== "SAVED").length;
  const responded = apps.filter((a) => ["ONLINE_ASSESSMENT", "INTERVIEWING", "OFFER"].includes(a.status)).length;

  async function commitMove(id: number, to: Status, index: number) {
    const previous = apps;
    setApps(applyMove(apps, id, to, index)); // optimistic
    try {
      await api.move(id, to, index);
    } catch (e) {
      setApps(previous);
      setError(`Move failed: ${(e as Error).message}`);
    }
  }

  function onDragOverCard(e: DragEvent, status: Status, index: number) {
    e.preventDefault();
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    setDrop({ status, index: index + (after ? 1 : 0) });
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    if (dragId != null && drop) {
      const card = apps.find((a) => a.id === dragId)!;
      // Dropping below itself in the same column shifts the index by one once it's removed.
      const index = card.status === drop.status && drop.index > card.position ? drop.index - 1 : drop.index;
      if (card.status !== drop.status || index !== card.position) commitMove(dragId, drop.status, index);
    }
    setDragId(null);
    setDrop(null);
  }

  async function remove(id: number) {
    if (!confirm("Remove this application from your board?")) return;
    setApps(apps.filter((a) => a.id !== id));
    await api.deleteApplication(id).catch(() => reload());
    reload();
  }

  async function saveNotes(id: number, notes: string) {
    const updated = await api.updateApplication(id, { notes });
    setApps((cur) => cur.map((a) => (a.id === id ? updated : a)));
  }

  return (
    <section>
      <div className="toolbar">
        <div className="stats">
          <Stat label="Tracked" value={apps.length} />
          <Stat label="Applied" value={applied} />
          <Stat label="Interviewing" value={columns.INTERVIEWING.length} />
          <Stat label="Offers" value={columns.OFFER.length} />
          <Stat label="Response rate" value={applied ? `${Math.round((responded / applied) * 100)}%` : "—"} />
        </div>
        <button className="primary" onClick={() => setAdding(true)}>
          + Add application
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      {adding && (
        <AddForm
          onClose={() => setAdding(false)}
          onCreated={(a) => {
            setApps((cur) => [...cur, a]);
            setAdding(false);
          }}
        />
      )}
      {loading ? (
        <p className="muted">Loading board…</p>
      ) : (
        <div className="board">
          {STATUSES.map((status) => (
            <div
              key={status}
              className={`column col-${status.toLowerCase()} ${drop?.status === status ? "drop-active" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                if (drop?.status !== status) setDrop({ status, index: columns[status].length });
              }}
              onDrop={onDrop}
            >
              <div className="column-head">
                <span>{STATUS_LABEL[status]}</span>
                <span className="count">{columns[status].length}</span>
              </div>
              {columns[status].map((a, i) => (
                <div key={a.id}>
                  {drop?.status === status && drop.index === i && dragId !== a.id && <div className="drop-line" />}
                  <Card
                    app={a}
                    dragging={dragId === a.id}
                    onDragStart={() => setDragId(a.id)}
                    onDragEnd={() => {
                      setDragId(null);
                      setDrop(null);
                    }}
                    onDragOver={(e) => onDragOverCard(e, status, i)}
                    onDelete={() => remove(a.id)}
                    onSaveNotes={(n) => saveNotes(a.id, n)}
                  />
                </div>
              ))}
              {drop?.status === status && drop.index >= columns[status].length && dragId != null && (
                <div className="drop-line" />
              )}
              {columns[status].length === 0 && <div className="empty">Drop cards here</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function Card(props: {
  app: Application;
  dragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (e: DragEvent) => void;
  onDelete: () => void;
  onSaveNotes: (notes: string) => Promise<void>;
}) {
  const { app } = props;
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(app.notes ?? "");
  const age = daysSince(app.appliedAt);

  return (
    <article
      className={`card ${props.dragging ? "dragging" : ""}`}
      draggable={!editing}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        props.onDragStart();
      }}
      onDragEnd={props.onDragEnd}
      onDragOver={props.onDragOver}
    >
      <div className="card-top">
        <strong>{app.company}</strong>
        <button className="icon" title="Remove" onClick={props.onDelete}>
          ×
        </button>
      </div>
      <div className="card-title">
        {app.url ? (
          <a href={app.url} target="_blank" rel="noreferrer">
            {app.roleTitle}
          </a>
        ) : (
          app.roleTitle
        )}
      </div>
      <div className="card-meta">
        {app.location && <span>{app.location}</span>}
        {age != null && <span>{age === 0 ? "applied today" : `applied ${age}d ago`}</span>}
        {app.jobId && <span className="badge">from radar</span>}
      </div>
      {editing ? (
        <textarea
          autoFocus
          value={notes}
          maxLength={4000}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={async () => {
            setEditing(false);
            if (notes !== (app.notes ?? "")) await props.onSaveNotes(notes);
          }}
        />
      ) : (
        <button className="notes" onClick={() => setEditing(true)}>
          {app.notes || <span className="muted">+ notes</span>}
        </button>
      )}
    </article>
  );
}

function AddForm({ onClose, onCreated }: { onClose: () => void; onCreated: (a: Application) => void }) {
  const [company, setCompany] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("APPLIED");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      onCreated(await api.createManual({ company, roleTitle, url: url || undefined, status }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="inline-form" onSubmit={submit}>
      <input placeholder="Company" required value={company} onChange={(e) => setCompany(e.target.value)} />
      <input placeholder="Role" required value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} />
      <input placeholder="Posting URL (optional)" value={url} onChange={(e) => setUrl(e.target.value)} />
      <select value={status} onChange={(e) => setStatus(e.target.value as Status)}>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABEL[s]}
          </option>
        ))}
      </select>
      <button className="primary">Add</button>
      <button type="button" className="ghost" onClick={onClose}>
        Cancel
      </button>
      {error && <div className="error">{error}</div>}
    </form>
  );
}
