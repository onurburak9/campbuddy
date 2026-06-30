import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import { PROVIDERS } from "../../types";
import type { ScanFormState } from "./useScanFormState";
import type { SearchWindow } from "../../types";

type Setter = <K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => void;

const DAYS = [
  { i: 0, label: "Mon" }, { i: 1, label: "Tue" }, { i: 2, label: "Wed" },
  { i: 3, label: "Thu" }, { i: 4, label: "Fri" }, { i: 5, label: "Sat" }, { i: 6, label: "Sun" },
];

const POLLING_OPTIONS = [
  { value: "300", label: "5 min" },
  { value: "900", label: "15 min" },
  { value: "1800", label: "30 min" },
  { value: "2700", label: "45 min" },
  { value: "3600", label: "1 hour" },
  { value: "7200", label: "2 hours" },
  { value: "21600", label: "6 hours" },
];

function formatInterval(seconds: number): string {
  if (seconds % 3600 === 0) { const h = seconds / 3600; return `${h} hour${h > 1 ? "s" : ""}`; }
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} sec`;
}

export function ProviderSitesFields({ state, set }: { state: ScanFormState; set: Setter }) {
  return (
    <div className="space-y-4">
      <Input label="Scan name (optional)" value={state.name}
        onChange={(e) => set("name", e.target.value)} placeholder="Yosemite summer trip" />
      <Select label="Provider" value={state.provider} onChange={(v) => set("provider", v)}
        options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
      <Input label="Recreation Area IDs (comma-separated)" value={state.recAreaIds}
        onChange={(e) => set("recAreaIds", e.target.value)} placeholder="2991, 2992" />
      <Input label="Campground IDs (optional)" value={state.campgroundIds}
        onChange={(e) => set("campgroundIds", e.target.value)} />
      <Input label="Campsite IDs (optional)" value={state.campsiteIds}
        onChange={(e) => set("campsiteIds", e.target.value)} />
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

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <span className="block text-sm text-stone-600 dark:text-[#888]">Search windows</span>
        {state.windows.map((w, i) => (
          <div key={i} className="flex items-end gap-2">
            <Input type="date" value={w.start_date}
              onChange={(e) => updateWindow(i, { start_date: e.target.value })} />
            <Input type="date" value={w.end_date}
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
      <Input label="Consecutive nights" type="number" min={1} value={state.nights}
        onChange={(e) => set("nights", Math.max(1, Number(e.target.value) || 1))} />
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
    </div>
  );
}

export function NotificationsFields({
  state,
  set,
  telegramAvailable,
}: {
  state: ScanFormState;
  set: Setter;
  telegramAvailable: boolean;
}) {
  const currentVal = String(state.pollingInterval);
  const pollingOptions = POLLING_OPTIONS.some((o) => o.value === currentVal)
    ? POLLING_OPTIONS
    : [{ value: currentVal, label: formatInterval(state.pollingInterval) }, ...POLLING_OPTIONS];

  return (
    <div className="space-y-4">
      <Select
        label="Polling interval"
        value={currentVal}
        onChange={(v) => set("pollingInterval", Number(v))}
        options={pollingOptions}
      />
      <Toggle label="Notify via email" checked={state.notifyEmail}
        onChange={(v) => set("notifyEmail", v)} />
      <Toggle
        label="Notify via Telegram"
        checked={state.notifyTelegram}
        disabled={!telegramAvailable}
        onChange={(v) => set("notifyTelegram", v)}
      />
      <Toggle label="Notify on new sites only" checked={state.notifyNewOnly}
        onChange={(v) => set("notifyNewOnly", v)} />
    </div>
  );
}
