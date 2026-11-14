import { describe, expect, it } from "vitest";
import { applyMove, daysSince, groupByStatus } from "./board";
import type { Application, Status } from "./types";

const card = (id: number, status: Status, position: number): Application => ({
  id,
  jobId: null,
  company: `Co${id}`,
  roleTitle: "SWE Intern",
  url: null,
  location: null,
  status,
  position,
  notes: null,
  appliedAt: status === "SAVED" ? null : "2026-11-01T00:00:00Z",
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
});

const order = (apps: Application[], s: Status) => groupByStatus(apps)[s].map((a) => a.id);

describe("board", () => {
  const apps = [card(1, "SAVED", 0), card(2, "SAVED", 1), card(3, "APPLIED", 0), card(4, "APPLIED", 1)];

  it("groups cards into every column sorted by position", () => {
    const cols = groupByStatus([card(9, "OFFER", 1), card(8, "OFFER", 0)]);
    expect(cols.OFFER.map((a) => a.id)).toEqual([8, 9]);
    expect(cols.SAVED).toEqual([]);
  });

  it("moves a card across columns and renumbers both densely", () => {
    const next = applyMove(apps, 1, "APPLIED", 1);
    expect(order(next, "SAVED")).toEqual([2]);
    expect(order(next, "APPLIED")).toEqual([3, 1, 4]);
    expect(groupByStatus(next).APPLIED.map((a) => a.position)).toEqual([0, 1, 2]);
    expect(next.find((a) => a.id === 1)!.appliedAt).not.toBeNull();
  });

  it("reorders within a column and clamps out-of-range positions", () => {
    expect(order(applyMove(apps, 3, "APPLIED", 99), "APPLIED")).toEqual([4, 3]);
    expect(order(applyMove(apps, 4, "APPLIED", -5), "APPLIED")).toEqual([4, 3]);
  });

  it("computes days since a date", () => {
    expect(daysSince("2026-11-01T00:00:00Z", new Date("2026-11-14T12:00:00Z"))).toBe(13);
    expect(daysSince(null)).toBeNull();
  });
});
