import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { relativeTime, dateRange, duration } from "./format";
import { formatInterval } from "./format";

describe("format", () => {
  beforeEach(() => vi.useFakeTimers().setSystemTime(new Date("2026-06-24T12:00:00Z")));
  afterEach(() => vi.useRealTimers());

  it("relativeTime renders minutes ago", () => {
    expect(relativeTime("2026-06-24T11:57:00Z")).toMatch(/3 min/);
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
});

describe("formatInterval", () => {
  it("formats minutes and hours", () => {
    expect(formatInterval(300)).toBe("5 min");
    expect(formatInterval(3600)).toBe("1 hour");
    expect(formatInterval(7200)).toBe("2 hours");
  });
});
