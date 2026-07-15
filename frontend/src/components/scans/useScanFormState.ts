import { useState, useCallback } from "react";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, SearchWindow } from "../../types";

export interface SelectedItem {
  id: number;
  name: string;
}

export interface ScanFormState {
  name: string;
  provider: string;
  recAreaIds: SelectedItem[];
  campgroundIds: SelectedItem[];
  campsiteIds: SelectedItem[];
  windows: SearchWindow[];
  nights: number;
  daysOfWeek: number[];
  weekendsOnly: boolean;
  pollingInterval: number;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyNewOnly: boolean;
}

function idsAsFallbackItems(ids: number[] | null | undefined): SelectedItem[] {
  return (ids ?? []).map((id) => ({ id, name: `ID ${id}` }));
}

function fromScan(scan?: Scan): ScanFormState {
  return {
    name: scan?.name ?? "",
    provider: scan?.provider ?? "RecreationDotGov",
    recAreaIds: idsAsFallbackItems(scan?.rec_area_ids),
    campgroundIds: idsAsFallbackItems(scan?.campground_ids),
    campsiteIds: idsAsFallbackItems(scan?.campsite_ids),
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

export function useScanFormState(scan?: Scan) {
  const [state, setState] = useState<ScanFormState>(() => fromScan(scan));

  const set = useCallback(<K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toScanCreatePayload = (): ScanCreatePayload => ({
    provider: state.provider,
    name: state.name.trim() || null,
    polling_interval: state.pollingInterval,
    rec_area_ids: state.recAreaIds.length ? state.recAreaIds.map((i) => i.id) : null,
    campground_ids: state.campgroundIds.length ? state.campgroundIds.map((i) => i.id) : null,
    campsite_ids: state.campsiteIds.length ? state.campsiteIds.map((i) => i.id) : null,
    search_windows: state.windows,
    nights: Math.max(1, state.nights),
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
