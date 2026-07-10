import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { SearchSelect } from "../ui/SearchSelect";
import { Badge } from "../ui/Badge";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import { PROVIDERS } from "../../types";
import { search } from "../../api/search";
import type { RecreationAreaResult, CampgroundResult } from "../../api/search";
import type { ScanFormState, SelectedItem } from "./useScanFormState";
import type { SearchWindow } from "../../types";
import { formatInterval } from "../../lib/format";

// SearchSelect's generic is inferred as SelectedItem (id/name only) from the
// selected/onChange contract, but at runtime the results here always come
// straight from search.recreationAreas()/campgrounds(), so the fuller shape
// is safe to assume for display purposes.
function RecreationAreaResultRow({ item }: { item: SelectedItem }) {
  const full = item as unknown as RecreationAreaResult;
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-stone-900 dark:text-[#EEE]">{full.name}</p>
        <p className="truncate text-xs text-stone-500 dark:text-[#888]">
          ID {full.id}{full.type && ` · ${full.type}`}
        </p>
      </div>
      {full.state && <Badge tone="neutral">{full.state}</Badge>}
    </div>
  );
}

function CampgroundResultRow({ item }: { item: SelectedItem }) {
  const full = item as unknown as CampgroundResult;
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-stone-900 dark:text-[#EEE]">{full.name}</p>
        <p className="truncate text-xs text-stone-500 dark:text-[#888]">{full.recreation_area}</p>
      </div>
      <Badge tone="neutral">ID {full.id}</Badge>
    </div>
  );
}

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

export function ProviderSitesFields({ state, set }: { state: ScanFormState; set: Setter }) {
  const resolvedRecAreaIds = useResolveFallbackLabels(state.recAreaIds, search.resolveRecreationAreas, (items) => set("recAreaIds", items));
  const resolvedCampgroundIds = useResolveFallbackLabels(state.campgroundIds, search.resolveCampgrounds, (items) => set("campgroundIds", items));
  const resolvedCampsiteIds = useResolveFallbackLabels(state.campsiteIds, search.resolveCampsites, (items) => set("campsiteIds", items));

  const recAreaIds = resolvedRecAreaIds.map((i) => i.id);
  const campgroundIds = resolvedCampgroundIds.map((i) => i.id);

  return (
    <div className="space-y-4">
      <Input label="Scan name (optional)" value={state.name}
        onChange={(e) => set("name", e.target.value)} placeholder="Yosemite summer trip" />
      <Select label="Provider" value={state.provider} onChange={(v) => set("provider", v)}
        options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
      <SearchSelect
        label="Recreation Areas"
        selected={resolvedRecAreaIds}
        onChange={(items) => set("recAreaIds", items)}
        search={(q) => search.recreationAreas(q)}
        renderResult={(item) => <RecreationAreaResultRow item={item} />}
        placeholder="Search by name, e.g. Yosemite"
      />
      <SearchSelect
        label="Campgrounds (optional)"
        selected={resolvedCampgroundIds}
        onChange={(items) => set("campgroundIds", items)}
        search={(q) => search.campgrounds(q, recAreaIds.length ? recAreaIds : null)}
        renderResult={(item) => <CampgroundResultRow item={item} />}
        placeholder="Search by name"
      />
      <SearchSelect
        label="Campsites (optional)"
        selected={resolvedCampsiteIds}
        onChange={(items) => set("campsiteIds", items)}
        search={() => (campgroundIds.length ? search.campsites(campgroundIds) : Promise.resolve([]))}
        disabled={campgroundIds.length === 0}
        placeholder={campgroundIds.length ? "Search by site name" : "Select a campground first"}
      />
    </div>
  );
}

function useResolveFallbackLabels(
  items: SelectedItem[],
  resolve: (ids: number[]) => Promise<SelectedItem[]>,
  apply: (items: SelectedItem[]) => void,
): SelectedItem[] {
  const fallbackIds = items.filter((i) => i.name === `ID ${i.id}`).map((i) => i.id);
  const { data } = useQuery({
    queryKey: ["resolve-ids", resolve.name, fallbackIds],
    queryFn: () => resolve(fallbackIds),
    enabled: fallbackIds.length > 0,
    staleTime: Infinity,
  });

  const resolved = data && data.length > 0
    ? items.map((i) => data.find((d) => d.id === i.id) ?? i)
    : items;

  useEffect(() => {
    if (!data || data.length === 0) return;
    if (resolved.some((u, idx) => u !== items[idx])) apply(resolved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return resolved;
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
