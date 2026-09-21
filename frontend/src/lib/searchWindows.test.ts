import { describe, it, expect } from "vitest";
import { toISODate, windowsBlockingReason } from "./searchWindows";
import type { SearchWindow } from "../types";

const NOW = new Date(2026, 8, 20, 12, 0, 0); // Sun 20 Sep 2026, local noon

describe("toISODate", () => {
  it("formats a date from its local parts", () => {
    expect(toISODate(new Date(2026, 0, 5, 12, 0, 0))).toBe("2026-01-05");
  });

  it("does not roll over to the next day late in the evening", () => {
    // toISOString() would report 2026-09-21 for this instant in any UTC-negative zone.
    expect(toISODate(new Date(2026, 8, 20, 23, 30, 0))).toBe("2026-09-20");
  });
});

describe("windowsBlockingReason", () => {
  const future: SearchWindow = { start_date: "2026-10-02", end_date: "2026-10-04" };
  const past: SearchWindow = { start_date: "2026-08-07", end_date: "2026-08-09" };

  it("blocks when there are no windows at all", () => {
    expect(windowsBlockingReason([], NOW)).toBe(
      "Add at least one search window with start and end dates.",
    );
  });

  it("blocks when a window is missing its end date", () => {
    expect(windowsBlockingReason([{ start_date: "2026-10-02", end_date: "" }], NOW)).toBe(
      "Add at least one search window with start and end dates.",
    );
  });

  it("blocks when a window is missing its start date", () => {
    expect(windowsBlockingReason([{ start_date: "", end_date: "2026-10-04" }], NOW)).toBe(
      "Add at least one search window with start and end dates.",
    );
  });

  it("blocks an incomplete window even when a complete future one is present", () => {
    expect(windowsBlockingReason([future, { start_date: "2026-11-01", end_date: "" }], NOW)).toBe(
      "Add at least one search window with start and end dates.",
    );
  });

  it("blocks when every window has already ended", () => {
    expect(windowsBlockingReason([past], NOW)).toBe(
      "At least one search window must end today or later.",
    );
  });

  it("allows a window that ends today, matching the backend's expiry rule", () => {
    // core/availability.py treats a window as passed only when end_date < today.
    expect(windowsBlockingReason([{ start_date: "2026-09-18", end_date: "2026-09-20" }], NOW))
      .toBeNull();
  });

  it("allows a mix of past and future windows", () => {
    expect(windowsBlockingReason([past, future], NOW)).toBeNull();
  });

  it("allows a single future window", () => {
    expect(windowsBlockingReason([future], NOW)).toBeNull();
  });
});
