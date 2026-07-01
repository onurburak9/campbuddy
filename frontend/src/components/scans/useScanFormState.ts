import { useState, useCallback } from "react";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, SearchWindow } from "../../types";

export interface ScanFormState {
  name: string;
  provider: string;
  recAreaIds: string;
  campgroundIds: string;
  campsiteIds: string;
  windows: SearchWindow[];
  nights: number;
  daysOfWeek: number[];
  weekendsOnly: boolean;
  pollingInterval: number;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyNewOnly: boolean;
}

function fromScan(scan?: Scan): ScanFormState {
  return {
    name: scan?.name ?? "",
    provider: scan?.provider ?? "RecreationDotGov",
    recAreaIds: scan?.rec_area_ids?.join(", ") ?? "",
    campgroundIds: scan?.campground_ids?.join(", ") ?? "",
    campsiteIds: scan?.campsite_ids?.join(", ") ?? "",
    windows: scan?.search_windows ?? [],
    nights: scan?.nights ?? 1,
    daysOfWeek: scan?.days_of_week ?? [],
    weekendsOnly: scan?.weekends_only ?? false,
    pollingInterval: scan?.polling_interval ?? 300,
    notifyEmail: scan?.notify_via_email ?? true,
    notifyTelegram: scan?.notify_via_telegram ?? false,
    notifyNewOnly: scan?.notify_on_new_only ?? true,
  };
}

function parseIds(csv: string): number[] | null {
  const ids = csv
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map(Number)
    .filter((n) => !Number.isNaN(n));
  return ids.length ? ids : null;
}

export function useScanFormState(scan?: Scan) {
  const [state, setState] = useState<ScanFormState>(() => fromScan(scan));

  const set = useCallback(<K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toScanCreatePayload = (): ScanCreatePayload => ({
    provider: state.provider,
    name: state.name.trim() || null,
    polling_interval: state.pollingInterval,
    rec_area_ids: parseIds(state.recAreaIds),
    campground_ids: parseIds(state.campgroundIds),
    campsite_ids: parseIds(state.campsiteIds),
    search_windows: state.windows,
    nights: state.nights,
    days_of_week: state.daysOfWeek.length ? state.daysOfWeek : null,
    weekends_only: state.weekendsOnly,
    notify_via_email: state.notifyEmail,
    notify_via_telegram: state.notifyTelegram,
    notify_on_new_only: state.notifyNewOnly,
  });

  const toScanUpdatePayload = (): ScanUpdatePayload => {
    const { provider: _omit, ...rest } = toScanCreatePayload();
    return rest;
  };

  return { state, set, toScanCreatePayload, toScanUpdatePayload };
}
