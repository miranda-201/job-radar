import { describe, expect, it } from "vitest";
import { isFresh, postedLabel } from "./dates";

describe("postedLabel", () => {
  const now = new Date(2026, 10, 14, 15, 0); // Nov 14 2026, 3pm local

  it("uses relative labels for recent postings", () => {
    expect(postedLabel(new Date(2026, 10, 14, 1, 0).toISOString(), now)).toBe("Posted today");
    expect(postedLabel(new Date(2026, 10, 13, 23, 0).toISOString(), now)).toBe("Posted yesterday");
    expect(postedLabel(new Date(2026, 10, 9, 12, 0).toISOString(), now)).toBe("Posted 5d ago");
  });

  it("uses calendar dates for older postings", () => {
    expect(postedLabel(new Date(2026, 8, 3).toISOString(), now)).toBe("Posted Sep 3");
    expect(postedLabel(new Date(2025, 11, 1).toISOString(), now)).toBe("Posted Dec 1, 2025");
    expect(postedLabel(null, now)).toBe("Post date unknown");
  });

  it("flags postings from the last 48 hours as fresh", () => {
    expect(isFresh(new Date(2026, 10, 13, 9, 0).toISOString(), now)).toBe(true);
    expect(isFresh(new Date(2026, 10, 11, 9, 0).toISOString(), now)).toBe(false);
  });
});
