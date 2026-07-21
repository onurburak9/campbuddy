import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { relativeTime, dateRange, duration, dateTime, relativeFuture, formatSeconds } from "./format";
import { formatInterval } from "./format";

describe("format", () => {
  beforeEach(() => vi.useFakeTimers().setSystemTime(new Date("2026-06-24T12:00:00Z")));
  afterEach(() => vi.useRealTimers());

  it("relativeTime renders minutes ago", () => {
    expect(relativeTime("2026-06-24T11:57:00Z")).toMatch(/3 min/);
  });
  it("dateTime renders a month-day fragment", () => {
    expect(dateTime("2026-06-24T17:03:00Z")).toMatch(/[A-Z][a-z]{2} \d{1,2}/);
  });
  it("dateRange renders a compact range", () => {
    expect(dateRange("2026-05-12", "2026-05-14")).toMatch(/May 12.*May 14/);
  });
  it("duration returns em dash when unfinished", () => {
    expect(duration("2026-06-24T12:00:00Z", null)).toBe("—");
  });
  it("duration renders seconds", () => {
    expect(duration("2026-06-24T11:59:48Z", "2026-06-24T12:00:00Z")).toBe("12s");
  });
  it("relativeFuture renders \"due now\" for a due or overdue time", () => {
    expect(relativeFuture("2026-06-24T12:00:00Z")).toBe("due now");
    expect(relativeFuture("2026-06-24T11:59:00Z")).toBe("due now");
  });
  it("relativeFuture renders minutes ahead", () => {
    expect(relativeFuture("2026-06-24T12:05:00Z")).toMatch(/in 5 min/);
  });
  it("relativeFuture renders hours ahead", () => {
    expect(relativeFuture("2026-06-24T15:00:00Z")).toMatch(/in 3 hr/);
  });
  it("formatSeconds renders sub-minute and multi-minute durations", () => {
    expect(formatSeconds(12)).toBe("12s");
    expect(formatSeconds(75)).toBe("1m 15s");
  });
});

describe("formatInterval", () => {
  it("formats minutes and hours", () => {
    expect(formatInterval(300)).toBe("5 min");
    expect(formatInterval(3600)).toBe("1 hour");
    expect(formatInterval(7200)).toBe("2 hours");
  });
});
