import type { SearchWindow } from "../types";

export const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const WEEKEND_NIGHTS = 2;

function atNoon(iso: string): Date {
  return new Date(`${iso}T12:00:00`);
}

function fmt(iso: string, withYear: boolean): string {
  return atNoon(iso).toLocaleDateString(
    undefined,
    withYear ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", day: "numeric" },
  );
}

// end_date is the exclusive range bound, so the last night a user could sleep
// there is the day before it. Showing the bound itself reads as a stay that
// runs a day longer than it does.
function lastNight(endDate: string): string {
  const d = atNoon(endDate);
  d.setDate(d.getDate() - 1);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

function span(from: string, to: string): string {
  const sameYear = from.slice(0, 4) === to.slice(0, 4);
  return `${fmt(from, !sameYear)} and ${fmt(to, true)}`;
}

function qualifier(nights: number, weekendsOnly: boolean, daysOfWeek: number[]): string {
  if (weekendsOnly) {
    return nights === WEEKEND_NIGHTS ? " over a Fri–Sun weekend" : " on Fri/Sat nights";
  }
  if (daysOfWeek.length > 0) {
    return ` on ${[...daysOfWeek].sort((a, b) => a - b).map((d) => DAY_NAMES[d]).join(", ")}`;
  }
  return "";
}

/** Plain-English summary of what the current date config will actually search. */
export function describeSearch(
  windows: SearchWindow[],
  nights: number,
  weekendsOnly: boolean,
  daysOfWeek: number[],
): string | null {
  const complete = windows.filter((w) => w.start_date && w.end_date && w.end_date > w.start_date);
  if (complete.length === 0) return null;

  const unit = `${nights} night${nights === 1 ? "" : "s"}`;
  const extra = qualifier(nights, weekendsOnly, daysOfWeek);

  if (complete.length > 1) {
    return `${unit}${extra} in any of ${complete.length} date ranges`;
  }

  const [only] = complete;
  const windowNights = Math.round(
    (atNoon(only.end_date).getTime() - atNoon(only.start_date).getTime()) / 86_400_000,
  );

  // When the window is exactly the stay, end_date really is the check-out day.
  if (windowNights === nights) {
    const sameYear = only.start_date.slice(0, 4) === only.end_date.slice(0, 4);
    return `${unit}${extra} — ${fmt(only.start_date, !sameYear)} to ${fmt(only.end_date, true)}`;
  }

  const separator = extra ? ", between " : " between ";
  return `Any ${unit}${extra}${separator}${span(only.start_date, lastNight(only.end_date))}`;
}
