import type { DateSource } from "./types";

const DAY = 86_400_000;

function relative(iso: string, now: Date): string {
  const posted = new Date(iso);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const days = Math.ceil((startOfToday - posted.getTime()) / DAY);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days}d ago`;
  const sameYear = posted.getFullYear() === now.getFullYear();
  return posted.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
}

/**
 * "Posted 9d ago" when the employer published the date; "Posted ~9d ago" for Workday's
 * coarse "Posted N Days Ago"; "Listed 1d ago" when the only date is when a GitHub list
 * added the role (the real posting may be older).
 */
export function postedLabel(iso: string | null, source: DateSource | null = "employer", now: Date = new Date()): string {
  if (!iso) return "Post date unknown";
  const when = relative(iso, now);
  if (source === "list") return `Listed ${when}`;
  if (source === "approximate" && when !== "today" && when !== "yesterday") return `Posted ~${when}`;
  return `Posted ${when}`;
}

export function dateTooltip(iso: string | null, source: DateSource | null): string | undefined {
  if (!iso) return undefined;
  const full = new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  if (source === "list")
    return `${full}: when this role was added to a GitHub internship list. The employer didn't publish a date we could verify, so it may have been posted earlier.`;
  if (source === "approximate") return `${full}: approximate; the employer's site only says "Posted N days ago".`;
  return `${full}: posting date from the employer's job board.`;
}

export function isFresh(iso: string | null, now: Date = new Date(), hours = 48): boolean {
  return iso != null && now.getTime() - new Date(iso).getTime() < hours * 3_600_000;
}
