import { describe, it, expect } from "vitest";
import {
  anyWeekendNightInMonth,
  nextWeekend,
  nextTwoWeekends,
  upcomingMonths,
  weekendsInMonth,
  wholeMonth,
} from "./dateTemplates";

// Weekday reference for September 2026: the 1st is a Tuesday, so
// Fri 4th, Fri 11th, Fri 18th, Fri 25th. The 30th is a Wednesday.
const WED_SEP_16 = new Date(2026, 8, 16, 12);
const THU_SEP_17 = new Date(2026, 8, 17, 12);
const FRI_SEP_18 = new Date(2026, 8, 18, 12);
const SAT_SEP_19 = new Date(2026, 8, 19, 12);
const SUN_SEP_20 = new Date(2026, 8, 20, 12);

describe("nextWeekend", () => {
  it("picks the coming Friday to Sunday midweek", () => {
    expect(nextWeekend(WED_SEP_16).windows).toEqual([
      { start_date: "2026-09-18", end_date: "2026-09-20" },
    ]);
  });

  it("picks tomorrow's Friday when today is Thursday", () => {
    expect(nextWeekend(THU_SEP_17).windows).toEqual([
      { start_date: "2026-09-18", end_date: "2026-09-20" },
    ]);
  });

  it("skips to the following weekend when today is Friday", () => {
    expect(nextWeekend(FRI_SEP_18).windows).toEqual([
      { start_date: "2026-09-25", end_date: "2026-09-27" },
    ]);
  });

  it("skips to the following weekend when today is Saturday", () => {
    expect(nextWeekend(SAT_SEP_19).windows).toEqual([
      { start_date: "2026-09-25", end_date: "2026-09-27" },
    ]);
  });

  it("skips to the following weekend when today is Sunday", () => {
    expect(nextWeekend(SUN_SEP_20).windows).toEqual([
      { start_date: "2026-09-25", end_date: "2026-09-27" },
    ]);
  });

  it("sets two nights and leaves the weekends-only filter off", () => {
    const result = nextWeekend(WED_SEP_16);
    expect(result.nights).toBe(2);
    expect(result.weekendsOnly).toBe(false);
    expect(result.daysOfWeek).toEqual([]);
  });

  it("crosses a month boundary without distorting the window", () => {
    // Wed 30 Sep 2026 -> the coming Friday is 2 Oct.
    expect(nextWeekend(new Date(2026, 8, 30, 12)).windows).toEqual([
      { start_date: "2026-10-02", end_date: "2026-10-04" },
    ]);
  });
});

describe("nextTwoWeekends", () => {
  it("returns two separate Friday-to-Sunday windows a week apart", () => {
    expect(nextTwoWeekends(WED_SEP_16).windows).toEqual([
      { start_date: "2026-09-18", end_date: "2026-09-20" },
      { start_date: "2026-09-25", end_date: "2026-09-27" },
    ]);
  });

  it("applies the same skip rule as nextWeekend when today is Saturday", () => {
    expect(nextTwoWeekends(SAT_SEP_19).windows).toEqual([
      { start_date: "2026-09-25", end_date: "2026-09-27" },
      { start_date: "2026-10-02", end_date: "2026-10-04" },
    ]);
  });
});

describe("wholeMonth", () => {
  it("spans a future month end to end, checking out on the 1st of the next", () => {
    expect(wholeMonth("2026-10", SUN_SEP_20)).toEqual({
      windows: [{ start_date: "2026-10-01", end_date: "2026-11-01" }],
      nights: 1,
      weekendsOnly: false,
      daysOfWeek: [],
    });
  });

  it("clamps the current month's start to today so it never emits a past date", () => {
    expect(wholeMonth("2026-09", SUN_SEP_20).windows).toEqual([
      { start_date: "2026-09-20", end_date: "2026-10-01" },
    ]);
  });

  it("handles a 28-day February", () => {
    expect(wholeMonth("2027-02", SUN_SEP_20).windows).toEqual([
      { start_date: "2027-02-01", end_date: "2027-03-01" },
    ]);
  });

  it("handles a leap-year February", () => {
    expect(wholeMonth("2028-02", SUN_SEP_20).windows).toEqual([
      { start_date: "2028-02-01", end_date: "2028-03-01" },
    ]);
  });
});

describe("weekendsInMonth", () => {
  it("uses one month-long window plus the weekends-only filter, not one window per weekend", () => {
    expect(weekendsInMonth("2026-10", SUN_SEP_20)).toEqual({
      windows: [{ start_date: "2026-10-01", end_date: "2026-11-01" }],
      nights: 2,
      weekendsOnly: true,
      daysOfWeek: [],
    });
  });

  it("still produces exactly one window for a month containing five Fridays", () => {
    // January 2027 has Fridays on the 1st, 8th, 15th, 22nd and 29th.
    expect(weekendsInMonth("2027-01", SUN_SEP_20).windows).toEqual([
      { start_date: "2027-01-01", end_date: "2027-02-01" },
    ]);
  });

  it("clamps the current month's start to today", () => {
    expect(weekendsInMonth("2026-09", SUN_SEP_20).windows).toEqual([
      { start_date: "2026-09-20", end_date: "2026-10-01" },
    ]);
  });
});

describe("anyWeekendNightInMonth", () => {
  it("keeps the weekends-only filter but drops to a single night", () => {
    expect(anyWeekendNightInMonth("2026-10", SUN_SEP_20)).toEqual({
      windows: [{ start_date: "2026-10-01", end_date: "2026-11-01" }],
      nights: 1,
      weekendsOnly: true,
      daysOfWeek: [],
    });
  });

  it("clamps the current month's start to today", () => {
    expect(anyWeekendNightInMonth("2026-09", SUN_SEP_20).windows).toEqual([
      { start_date: "2026-09-20", end_date: "2026-10-01" },
    ]);
  });
});

describe("upcomingMonths", () => {
  it("starts at the current month and rolls into the next year", () => {
    const keys = upcomingMonths(SUN_SEP_20).map((m) => m.key);
    expect(keys).toHaveLength(12);
    expect(keys[0]).toBe("2026-09");
    expect(keys[3]).toBe("2026-12");
    expect(keys[4]).toBe("2027-01");
    expect(keys[keys.length - 1]).toBe("2027-08");
  });

  it("offers a month already in progress as this year, not next", () => {
    expect(upcomingMonths(SUN_SEP_20)[0].key).toBe("2026-09");
  });

  it("still offers the current month on its last day, when one night remains", () => {
    // Wed 30 Sep 2026 is the last day, but 30 Sep -> 1 Oct is a bookable night.
    const keys = upcomingMonths(new Date(2026, 8, 30, 12)).map((m) => m.key);
    expect(keys[0]).toBe("2026-09");
    expect(keys).toHaveLength(12);
  });

  it("keeps the last day of the month bookable as a single night", () => {
    expect(wholeMonth("2026-09", new Date(2026, 8, 30, 12)).windows).toEqual([
      { start_date: "2026-09-30", end_date: "2026-10-01" },
    ]);
  });

  it("exposes a bare month name for button labels alongside the full label", () => {
    const october = upcomingMonths(SUN_SEP_20).find((m) => m.key === "2026-10");
    expect(october?.name).toMatch(/^oct/i);
    expect(october?.name).not.toMatch(/2026/);
  });

  it("labels each month with its name and year", () => {
    expect(upcomingMonths(SUN_SEP_20)[0].label).toMatch(/2026/);
    expect(upcomingMonths(SUN_SEP_20)[0].label).toMatch(/sep/i);
  });
});
