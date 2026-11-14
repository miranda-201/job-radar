import { STATUSES, type Application, type Status } from "./types";

export type Columns = Record<Status, Application[]>;

export function groupByStatus(apps: Application[]): Columns {
  const cols = Object.fromEntries(STATUSES.map((s) => [s, [] as Application[]])) as Columns;
  for (const a of apps) cols[a.status].push(a);
  for (const s of STATUSES) cols[s].sort((a, b) => a.position - b.position);
  return cols;
}

/**
 * Optimistic client-side version of the server's move: same rules (insert at index, dense
 * renumbering of both columns), so the board doesn't flicker while the PUT is in flight.
 */
export function applyMove(apps: Application[], id: number, to: Status, position: number): Application[] {
  const card = apps.find((a) => a.id === id);
  if (!card) return apps;
  const cols = groupByStatus(apps.filter((a) => a.id !== id));
  const target = cols[to];
  const moved: Application = {
    ...card,
    status: to,
    appliedAt: card.appliedAt ?? (to !== "SAVED" ? new Date().toISOString() : null),
  };
  target.splice(Math.min(Math.max(position, 0), target.length), 0, moved);
  return STATUSES.flatMap((s) => cols[s].map((a, i) => ({ ...a, position: i })));
}

export function daysSince(iso: string | null, now: Date = new Date()): number | null {
  if (!iso) return null;
  return Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
}
