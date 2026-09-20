import type { SearchWindow } from "../types";

// Built from local parts on purpose: toISOString() reports the next day for any
// evening instant in a UTC-negative zone, which would silently expire a window.
export function toISODate(d: Date): string {
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export function windowsBlockingReason(windows: SearchWindow[], now: Date): string | null {
  if (windows.length === 0 || windows.some((w) => !w.start_date || !w.end_date)) {
    return "Add at least one search window with start and end dates.";
  }
  // Mirrors core/availability.py: a window has passed only once end_date < today.
  const today = toISODate(now);
  if (windows.every((w) => w.end_date < today)) {
    return "At least one search window must end today or later.";
  }
  return null;
}
