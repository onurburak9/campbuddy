import type { SearchWindow } from "../types";
import { toISODate } from "./searchWindows";

/** The slice of scan config a quick-pick template replaces wholesale. */
export interface DateTemplateResult {
  windows: SearchWindow[];
  nights: number;
  weekendsOnly: boolean;
  daysOfWeek: number[];
}

const FRIDAY = 5;
const WEEKEND_NIGHTS = 2;

function addDays(d: Date, days: number): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() + days);
  return out;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

// A Fri-Sun span that has already begun is half unusable, so Fri/Sat/Sun roll
// forward to the next one rather than offering a partial weekend.
function upcomingFriday(now: Date): Date {
  const delta = (FRIDAY - now.getDay() + 7) % 7;
  return addDays(now, delta === 0 ? 7 : delta);
}

function weekendWindow(friday: Date): SearchWindow {
  return {
    start_date: toISODate(friday),
    end_date: toISODate(addDays(friday, WEEKEND_NIGHTS)),
  };
}

/** Whole calendar month, clamped so the current month never starts in the past. */
function monthWindow(monthKey: string, now: Date): SearchWindow {
  const [year, month] = monthKey.split("-").map(Number);
  const first = new Date(year, month - 1, 1);
  // end_date is the check-out day, not a night: camply's get_date_range() is
  // exclusive of it. Checking out on the 1st of the next month is what makes
  // the month's final night - and so its final weekend - searchable at all.
  const checkout = new Date(year, month, 1);
  const today = startOfDay(now);
  return {
    start_date: toISODate(first < today ? today : first),
    end_date: toISODate(checkout),
  };
}

export function nextWeekend(now: Date): DateTemplateResult {
  return {
    windows: [weekendWindow(upcomingFriday(now))],
    nights: WEEKEND_NIGHTS,
    weekendsOnly: false,
    daysOfWeek: [],
  };
}

export function nextTwoWeekends(now: Date): DateTemplateResult {
  const first = upcomingFriday(now);
  return {
    windows: [weekendWindow(first), weekendWindow(addDays(first, 7))],
    nights: WEEKEND_NIGHTS,
    weekendsOnly: false,
    daysOfWeek: [],
  };
}

export function wholeMonth(monthKey: string, now: Date): DateTemplateResult {
  return { windows: [monthWindow(monthKey, now)], nights: 1, weekendsOnly: false, daysOfWeek: [] };
}

// One month-long window plus the scan-level weekends_only filter, rather than a
// window per weekend: nights/weekends_only are global to the scan, not per-window.
export function weekendsInMonth(monthKey: string, now: Date): DateTemplateResult {
  return {
    windows: [monthWindow(monthKey, now)],
    nights: WEEKEND_NIGHTS,
    weekendsOnly: true,
    daysOfWeek: [],
  };
}

// Same weekend restriction, but one night: catches the single-night
// cancellations that a 2-night Fri+Sat requirement silently skips over.
export function anyWeekendNightInMonth(monthKey: string, now: Date): DateTemplateResult {
  return { windows: [monthWindow(monthKey, now)], nights: 1, weekendsOnly: true, daysOfWeek: [] };
}

export function upcomingMonths(
  now: Date,
  count = 12,
): { key: string; label: string; name: string }[] {
  // The current month always stays on offer: its start clamps to today and it
  // checks out on the 1st of the next month, so even its last day is one night.
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    return {
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: d.toLocaleDateString(undefined, { month: "long", year: "numeric" }),
      name: d.toLocaleDateString(undefined, { month: "long" }),
    };
  });
}
