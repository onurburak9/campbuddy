import { useMemo, useState } from "react";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import type { ScanFormState, Setter } from "./useScanFormState";
import type { EquipmentType, SearchWindow } from "../../types";
import { EQUIPMENT_TYPE_OPTIONS } from "../../lib/equipmentTypes";
import {
  anyWeekendNightInMonth,
  nextTwoWeekends,
  nextWeekend,
  upcomingMonths,
  weekendsInMonth,
  wholeMonth,
} from "../../lib/dateTemplates";
import type { DateTemplateResult } from "../../lib/dateTemplates";
import { describeSearch, DAY_NAMES } from "../../lib/describeSearch";

const DAYS = DAY_NAMES.map((label, i) => ({ i, label }));

export function windowNights(w: SearchWindow): number | null {
  if (!w.start_date || !w.end_date) return null;
  const diffDays = Math.round(
    (new Date(w.end_date).getTime() - new Date(w.start_date).getTime()) / 86_400_000,
  );
  return diffDays > 0 ? diffDays : null;
}

function DateTemplateRow({ set }: { set: Setter }) {
  const months = useMemo(() => upcomingMonths(new Date()), []);
  const [monthKey, setMonthKey] = useState(months[0].key);
  const month = months.find((m) => m.key === monthKey) ?? months[0];

  // Templates replace the whole date config rather than merging, so a leftover
  // filter from a previous pick can't silently narrow the generated window.
  const apply = (result: DateTemplateResult) => {
    set("windows", result.windows);
    set("nights", result.nights);
    set("weekendsOnly", result.weekendsOnly);
    set("daysOfWeek", result.daysOfWeek);
  };

  return (
    <div data-tour="quick-picks" className="space-y-2 rounded-md bg-sand-100/60 p-3 dark:bg-[#161616]">
      <span className="block text-xs text-stone-500 dark:text-[#888]">Quick picks</span>
      <div className="flex flex-wrap items-end gap-1.5">
        <Button type="button" variant="secondary" size="sm"
          onClick={() => apply(nextWeekend(new Date()))}>
          Next weekend
        </Button>
        <Button type="button" variant="secondary" size="sm"
          onClick={() => apply(nextTwoWeekends(new Date()))}>
          Next 2 weekends
        </Button>
      </div>
      <div className="flex flex-wrap items-end gap-1.5">
        <Select label="Month" className="w-auto" value={monthKey} onChange={setMonthKey}
          options={months.map((m) => ({ value: m.key, label: m.label }))} />
        <Button type="button" variant="secondary" size="sm"
          onClick={() => apply(wholeMonth(monthKey, new Date()))}>
          All of {month.name}
        </Button>
        <Button type="button" variant="secondary" size="sm"
          onClick={() => apply(weekendsInMonth(monthKey, new Date()))}>
          Weekends in {month.name}
        </Button>
        <Button type="button" variant="secondary" size="sm"
          onClick={() => apply(anyWeekendNightInMonth(monthKey, new Date()))}>
          Any Fri/Sat night in {month.name}
        </Button>
      </div>
    </div>
  );
}

export function DatesFiltersFields({ state, set }: { state: ScanFormState; set: Setter }) {
  const updateWindow = (idx: number, patch: Partial<SearchWindow>) =>
    set("windows", state.windows.map((w, i) => (i === idx ? { ...w, ...patch } : w)));
  const addWindow = () => set("windows", [...state.windows, { start_date: "", end_date: "" }]);
  const removeWindow = (idx: number) => set("windows", state.windows.filter((_, i) => i !== idx));
  const toggleDay = (d: number) =>
    set(
      "daysOfWeek",
      state.daysOfWeek.includes(d)
        ? state.daysOfWeek.filter((x) => x !== d)
        : [...state.daysOfWeek, d],
    );
  const toggleEquipmentType = (t: EquipmentType) =>
    set(
      "equipmentTypes",
      state.equipmentTypes.includes(t)
        ? state.equipmentTypes.filter((x) => x !== t)
        : [...state.equipmentTypes, t],
    );

  const windowNightCounts = state.windows
    .map((w) => windowNights(w))
    .filter((n): n is number => n !== null);
  const shortestWindowNights = windowNightCounts.length ? Math.min(...windowNightCounts) : null;
  const nightsExceedWindow = shortestWindowNights !== null && state.nights > shortestWindowNights;
  // Mirrors the payload's Math.max(1, nights) so the summary never reads
  // "0 nights" while the nights field is momentarily cleared.
  const summary = describeSearch(
    state.windows,
    Math.max(1, state.nights),
    state.weekendsOnly,
    state.daysOfWeek,
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <span className="block text-sm text-stone-600 dark:text-[#888]">Search windows</span>
        <DateTemplateRow set={set} />
        <p
          data-testid="search-summary"
          data-tour="search-summary"
          className={
            summary
              ? "text-sm font-medium text-forest-700 dark:text-forest-400"
              : "text-sm text-stone-400 dark:text-[#666]"
          }
        >
          {summary ?? "Pick a quick pick above, or add a window below, to see what you'll be searching."}
        </p>
        {state.windows.map((w, i) => (
          <div key={i} className="flex items-end gap-2">
            <Input type="date" value={w.start_date}
              {...(i === 0 ? { label: "Search from" } : { "aria-label": `Search from (range ${i + 1})` })}
              onChange={(e) => updateWindow(i, { start_date: e.target.value })} />
            <Input type="date" value={w.end_date}
              {...(i === 0
                ? {
                    label: "Search until",
                    hint: "The day you'd check out. The last night searched is the day before this.",
                  }
                : { "aria-label": `Search until (range ${i + 1})` })}
              onChange={(e) => updateWindow(i, { end_date: e.target.value })} />
            <Button type="button" variant="ghost" size="sm" onClick={() => removeWindow(i)}>
              Remove
            </Button>
          </div>
        ))}
        <Button type="button" variant="secondary" size="sm" onClick={addWindow}>
          + Add window
        </Button>
      </div>
      <div data-tour="nights-field">
      <Input
        label="Consecutive nights"
        hint="How long a stay to look for, exactly - 2 will not match a single free night. Quick picks overwrite this."
        type="number"
        min={1}
        value={state.nights === 0 ? "" : state.nights}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") { set("nights", 0); return; }
          const parsed = Number(raw);
          if (Number.isNaN(parsed)) return;
          set("nights", Math.max(1, parsed));
        }}
        onBlur={() => { if (state.nights === 0) set("nights", 1); }}
      />
      </div>
      {nightsExceedWindow && (
        <p className="text-sm text-[#DC2626]">
          Consecutive nights ({state.nights}) can't be longer than the shortest search window ({shortestWindowNights} night{shortestWindowNights === 1 ? "" : "s"}).
        </p>
      )}
      <div>
        <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">Days of week</span>
        <div className="flex flex-wrap gap-1.5">
          {DAYS.map((d) => (
            <button
              key={d.i}
              type="button"
              onClick={() => toggleDay(d.i)}
              className={`rounded-full px-3 py-1 text-sm ${
                state.daysOfWeek.includes(d.i)
                  ? "bg-forest-600 text-white"
                  : "bg-sand-100 text-stone-600 dark:bg-[#222] dark:text-[#AAA]"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>
      <Toggle label="Weekends only" checked={state.weekendsOnly}
        onChange={(v) => set("weekendsOnly", v)} />
      <div>
        <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">Equipment</span>
        <div className="flex flex-wrap gap-1.5">
          {EQUIPMENT_TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => toggleEquipmentType(opt.value)}
              className={`rounded-full px-3 py-1 text-sm ${
                state.equipmentTypes.includes(opt.value)
                  ? "bg-forest-600 text-white"
                  : "bg-sand-100 text-stone-600 dark:bg-[#222] dark:text-[#AAA]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-stone-400 dark:text-[#666]">
          Leave empty to match any equipment type.
        </p>
      </div>
    </div>
  );
}
