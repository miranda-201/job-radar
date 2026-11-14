import { describe, expect, it } from "vitest";
import { dateTooltip, isFresh, postedLabel } from "./dates";

describe("postedLabel", () => {
  const now = new Date(2026, 10, 14, 15, 0); // Nov 14 2026, 3pm local
  const at = (...a: [number, number, number, number?]) => new Date(a[0], a[1], a[2], a[3] ?? 12).toISOString();

  it("uses relative labels for recent employer dates", () => {
    expect(postedLabel(at(2026, 10, 14, 1), "employer", now)).toBe("Posted today");
    expect(postedLabel(at(2026, 10, 13, 23), "employer", now)).toBe("Posted yesterday");
    expect(postedLabel(at(2026, 10, 5), "employer", now)).toBe("Posted 9d ago");
  });

  it("uses calendar dates for older postings", () => {
    expect(postedLabel(at(2026, 8, 3), "employer", now)).toBe("Posted Sep 3");
    expect(postedLabel(at(2025, 11, 1), "employer", now)).toBe("Posted Dec 1, 2025");
    expect(postedLabel(null, "employer", now)).toBe("Post date unknown");
  });

  it("never presents a list date as the employer's posting date", () => {
    expect(postedLabel(at(2026, 10, 13), "list", now)).toBe("Listed yesterday");
    expect(dateTooltip(at(2026, 10, 13), "list")).toMatch(/GitHub internship list/);
  });

  it("marks coarse Workday dates as approximate", () => {
    expect(postedLabel(at(2026, 10, 5), "approximate", now)).toBe("Posted ~9d ago");
    expect(postedLabel(at(2026, 10, 14), "approximate", now)).toBe("Posted today");
  });

  it("flags postings from the last 48 hours as fresh", () => {
    expect(isFresh(at(2026, 10, 13, 9), now)).toBe(true);
    expect(isFresh(at(2026, 10, 11, 9), now)).toBe(false);
  });
});
