export type ScanStatus = "active" | "paused" | "completed";
export type RunOutcome = "success" | "no_results" | "error";

export interface User {
  id: number;
  email: string;
  scan_limit: number;
  scans_used: number;
  has_telegram: boolean;
}

export interface ScanStats {
  sites_found: number;
  in_cart: number;
  total_runs: number;
  success_rate: number; // 0–100
  next_run_at: string | null;
  last_run_duration_seconds: number | null;
}

export interface SearchWindow {
  start_date: string; // ISO date YYYY-MM-DD
  end_date: string;
}

export interface Scan {
  id: number;
  user_id: number;
  provider: string;
  name: string | null;
  status: ScanStatus;
  polling_interval: number;
  rec_area_ids: number[] | null;
  campground_ids: number[] | null;
  campsite_ids: number[] | null;
  search_windows: SearchWindow[];
  nights: number;
  days_of_week: number[] | null;
  weekends_only: boolean;
  notify_via_email: boolean;
  notify_via_telegram: boolean;
  notify_on_new_only: boolean;
  created_at: string;
}

export interface ScanRun {
  id: number;
  scan_id: number;
  started_at: string;
  finished_at: string | null;
  outcome: RunOutcome | null;
  sites_found: number;
  error_message: string | null;
}

export interface ScanResult {
  id: number;
  scan_run_id: number;
  scan_id: number;
  campsite_id: string;
  facility_id: string | null;
  facility_name: string;
  recreation_area_id: string | null;
  recreation_area: string | null;
  site_name: string;
  campsite_type: string;
  booking_date: string;
  booking_end_date: string;
  booking_url: string;
  first_seen_at: string;
  last_seen_at: string;
  is_available: boolean;
  cart_added: boolean;
  notified: boolean;
}

export interface ScanCreatePayload {
  provider: string;
  name?: string | null;
  polling_interval: number;
  rec_area_ids?: number[] | null;
  campground_ids?: number[] | null;
  campsite_ids?: number[] | null;
  search_windows: SearchWindow[];
  nights: number;
  days_of_week?: number[] | null;
  weekends_only: boolean;
  notify_via_email: boolean;
  notify_via_telegram: boolean;
  notify_on_new_only: boolean;
}

export type ScanUpdatePayload = Partial<Omit<ScanCreatePayload, "provider">>;

export interface Profile {
  id: number;
  email: string;
  telegram_chat_id: string | null;
  recreationgov_email: string | null;
  scan_limit: number;
}

export interface ProfileUpdatePayload {
  email?: string;
  telegram_chat_id?: string;
  recreationgov_email?: string;
  recreationgov_password?: string;
}

export const PROVIDERS = [
  "RecreationDotGov", "Yellowstone", "GoingToCamp", "ReserveCalifornia",
  "AlabamaStateParks", "ArizonaStateParks", "FloridaStateParks",
  "MinnesotaStateParks", "MissouriStateParks", "OhioStateParks",
  "VirginiaStateParks", "NorthernTerritory", "FairfaxCountyParks",
  "MaricopaCountyParks", "OregonMetro", "RecreationDotGovTicket",
  "RecreationDotGovTimedEntry", "RecreationDotGovDailyTicket",
  "RecreationDotGovDailyTimedEntry",
] as const;
