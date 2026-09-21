import { describe, it, expect } from "vitest";
import { describeSearch } from "./describeSearch";

const NEXT_WEEKEND = [{ start_date: "2026-09-25", end_date: "2026-09-27" }];
const ALL_OCTOBER = [{ start_date: "2026-10-01", end_date: "2026-11-01" }];

describe("describeSearch", () => {
  it("says nothing when there are no windows", () => {
    expect(describeSearch([], 1, false, [])).toBeNull();
  });

  it("says nothing while a window is still incomplete", () => {
    expect(describeSearch([{ start_date: "2026-10-01", end_date: "" }], 1, false, [])).toBeNull();
  });

  it("describes a window that is exactly the length of the stay as the trip itself", () => {
    expect(describeSearch(NEXT_WEEKEND, 2, false, [])).toMatch(/^2 nights — Sep 25.*Sep 27, 2026$/);
  });

  it("describes a wider window as a hunt for a stay inside it", () => {
    // Ends on Oct 31, the last night - never Nov 1, which is only the range bound.
    expect(describeSearch(ALL_OCTOBER, 1, false, [])).toMatch(/^Any 1 night between Oct 1 and Oct 31, 2026$/);
  });

  it("never shows the exclusive end date to the user", () => {
    expect(describeSearch(ALL_OCTOBER, 1, false, [])).not.toMatch(/Nov/);
  });

  it("calls out a Fri-Sun weekend when weekends-only pairs with two nights", () => {
    expect(describeSearch(ALL_OCTOBER, 2, true, [])).toMatch(
      /^Any 2 nights over a Fri–Sun weekend, between Oct 1 and Oct 31, 2026$/,
    );
  });

  it("falls back to Fri/Sat nights when weekends-only is used with another length", () => {
    expect(describeSearch(ALL_OCTOBER, 3, true, [])).toMatch(/on Fri\/Sat nights/);
  });

  it("lists selected days of the week", () => {
    expect(describeSearch(ALL_OCTOBER, 1, false, [0, 1])).toMatch(/on Mon, Tue/);
  });

  it("summarises multiple windows by count rather than listing them", () => {
    const twoWeekends = [
      { start_date: "2026-09-25", end_date: "2026-09-27" },
      { start_date: "2026-10-02", end_date: "2026-10-04" },
    ];
    expect(describeSearch(twoWeekends, 2, false, [])).toBe("2 nights in any of 2 date ranges");
  });

  it("uses the singular for a one-night stay", () => {
    expect(describeSearch(ALL_OCTOBER, 1, false, [])).toContain("1 night ");
  });

  it("shows both years when the range crosses a new year", () => {
    const crossing = [{ start_date: "2026-12-20", end_date: "2027-01-05" }];
    const text = describeSearch(crossing, 1, false, [])!;
    expect(text).toMatch(/2026/);
    expect(text).toMatch(/2027/);
  });
});
