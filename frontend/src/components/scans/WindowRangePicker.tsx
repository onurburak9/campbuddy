import { useMemo, useState } from "react";
import { Button } from "../ui/Button";
import { cn } from "../../lib/cn";
import type { SearchWindow } from "../../types";
import { toISODate } from "../../lib/searchWindows";
import {
  WEEKDAY_LABELS,
  addMonths,
  isBefore,
  isSameDay,
  monthLabel,
  monthMatrix,
  shortLabel,
  startOfDay,
} from "../../lib/calendarRange";

type CellState = "start" | "end" | "in-range" | "none";

// Local "which end are we filling in" cursor: two filled dates read as done,
// so the next click always starts a fresh range rather than nudging one end.
function useRangeSelection(w: SearchWindow, onChange: (patch: Partial<SearchWindow>) => void) {
  const picking = !w.start_date || (w.start_date && w.end_date) ? "start" : "end";
  const [hoverIso, setHoverIso] = useState<string | null>(null);

  const pick = (d: Date) => {
    const iso = toISODate(d);
    if (picking === "start") {
      onChange({ start_date: iso, end_date: "" });
      return;
    }
    if (iso <= w.start_date) {
      onChange({ start_date: iso, end_date: "" });
      return;
    }
    onChange({ end_date: iso });
  };

  const previewEnd = picking === "end" ? hoverIso : null;

  const cellState = (iso: string): CellState => {
    if (iso === w.start_date) return "start";
    if (iso === w.end_date) return "end";
    const rangeEnd = w.end_date || previewEnd;
    if (w.start_date && rangeEnd && iso > w.start_date && iso < rangeEnd) return "in-range";
    return "none";
  };

  return { pick, cellState, setHoverIso };
}

const cellBase = "flex h-8 w-8 items-center justify-center rounded-full text-sm transition-colors";
const cellByState: Record<CellState, string> = {
  start: "bg-forest-600 text-white",
  end: "bg-forest-600 text-white",
  "in-range": "bg-forest-100 text-forest-800 rounded-none dark:bg-forest-800/40 dark:text-forest-100",
  none: "text-stone-700 hover:bg-sand-100 dark:text-[#DDD] dark:hover:bg-[#222]",
};

function MonthGrid({
  base,
  cellState,
  onPick,
  onHover,
}: {
  base: Date;
  cellState: (iso: string) => CellState;
  onPick: (d: Date) => void;
  onHover: (iso: string | null) => void;
}) {
  const cells = useMemo(() => monthMatrix(base.getFullYear(), base.getMonth()), [base]);
  const today = startOfDay(new Date());
  return (
    <div className="w-64">
      <p className="mb-2 text-center text-sm font-medium text-stone-700 dark:text-[#EEE]">
        {monthLabel(base)}
      </p>
      <div className="grid grid-cols-7 gap-y-1 text-center">
        {WEEKDAY_LABELS.map((d) => (
          <span key={d} className="text-xs text-stone-400 dark:text-[#666]">
            {d}
          </span>
        ))}
        {cells.map(({ date, inMonth, iso }) => {
          const past = isBefore(date, today);
          const disabled = !inMonth || past;
          return (
            <button
              key={iso}
              type="button"
              disabled={disabled}
              aria-label={disabled ? undefined : date.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}
              // Locale-independent hook for e2e locators (aria-label text varies by locale).
              data-day-iso={disabled ? undefined : iso}
              onMouseEnter={() => onHover(iso)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onPick(date)}
              className={cn(
                cellBase,
                disabled ? "invisible" : cellByState[cellState(iso)],
                isSameDay(date, today) && cellState(iso) === "none" && "border border-forest-400",
              )}
            >
              {date.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function WindowRangePicker({
  window: w,
  index,
  isFirst,
  nights,
  onChange,
  onRemove,
}: {
  window: SearchWindow;
  index: number;
  isFirst: boolean;
  nights: number | null;
  onChange: (patch: Partial<SearchWindow>) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [base, setBase] = useState(() => startOfDay(new Date()));
  const { pick, cellState, setHoverIso } = useRangeSelection(w, onChange);
  const triggerLabel = isFirst ? "Search dates" : `Search dates (range ${index + 1})`;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={triggerLabel}
        data-start-date={w.start_date}
        data-end-date={w.end_date}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-md border border-sand-200 bg-white px-3 py-2 text-left text-sm dark:border-[#222] dark:bg-[#1A1A1A]"
      >
        <span className="text-stone-900 dark:text-[#EEE]">
          {w.start_date ? shortLabel(w.start_date) : "Search from"}
          {"  →  "}
          {w.end_date ? shortLabel(w.end_date) : "Search until"}
        </span>
        {nights !== null && (
          <span className="text-xs text-stone-500 dark:text-[#888]">
            {nights} night{nights === 1 ? "" : "s"}
          </span>
        )}
      </button>
      {isFirst && (
        <p className="mt-1 text-xs text-stone-400 dark:text-[#666]">
          Click a start day, then an end day. The end day is checkout — the last night searched is the day before it.
        </p>
      )}
      {open && (
        <div className="absolute z-20 mt-2 rounded-lg border border-sand-200 bg-white p-4 shadow-xl dark:border-[#222] dark:bg-[#161616]">
          <div className="mb-2 flex items-center justify-between">
            <Button type="button" variant="ghost" size="sm" aria-label="Previous month" onClick={() => setBase((b) => addMonths(b, -1))}>
              ←
            </Button>
            <Button type="button" variant="ghost" size="sm" aria-label="Next month" onClick={() => setBase((b) => addMonths(b, 1))}>
              →
            </Button>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row">
            <MonthGrid base={base} cellState={cellState} onPick={pick} onHover={setHoverIso} />
            <MonthGrid base={addMonths(base, 1)} cellState={cellState} onPick={pick} onHover={setHoverIso} />
          </div>
          <div className="mt-3 flex justify-between">
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ start_date: "", end_date: "" })}>
              Clear
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
                Remove window
              </Button>
              <Button type="button" size="sm" onClick={() => setOpen(false)}>
                Done
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
