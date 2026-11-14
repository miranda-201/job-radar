const DAY = 86_400_000;

/** "Posted today" / "Posted yesterday" / "Posted 5d ago" / "Posted Sep 3" (older than 2 weeks). */
export function postedLabel(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "Post date unknown";
  const posted = new Date(iso);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const days = Math.ceil((startOfToday - posted.getTime()) / DAY);
  if (days <= 0) return "Posted today";
  if (days === 1) return "Posted yesterday";
  if (days < 14) return `Posted ${days}d ago`;
  const sameYear = posted.getFullYear() === now.getFullYear();
  return `Posted ${posted.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) })}`;
}

export function isFresh(iso: string | null, now: Date = new Date(), hours = 48): boolean {
  return iso != null && now.getTime() - new Date(iso).getTime() < hours * 3_600_000;
}

export function fullDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : "";
}
