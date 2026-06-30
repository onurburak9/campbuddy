import { fetchApi } from "./client";
import type { ScanRun, ScanResult } from "../types";

export const runs = {
  list: (scanId: number, page = 1, pageSize = 20, outcome?: string) =>
    fetchApi<ScanRun[]>(
      `/scans/${scanId}/runs?page=${page}&page_size=${pageSize}${outcome ? `&outcome=${outcome}` : ""}`,
    ),
  runResults: (scanId: number, runId: number) =>
    fetchApi<ScanResult[]>(`/scans/${scanId}/runs/${runId}/results`),
};
