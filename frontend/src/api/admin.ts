import { fetchApi } from "./client";
import type { AdminUser, AdminScan, AdminScanDetail, Scan, ScanRun } from "../types";

export const admin = {
  listUsers: () => fetchApi<AdminUser[]>("/admin/users"),
  listScans: () => fetchApi<AdminScan[]>("/admin/scans"),
  getScan: (id: number) => fetchApi<AdminScanDetail>(`/admin/scans/${id}`),
  listScanRuns: (id: number, page = 1, pageSize = 20, outcome?: string, startedAfter?: string) =>
    fetchApi<ScanRun[]>(
      `/admin/scans/${id}/runs?page=${page}&page_size=${pageSize}` +
        (outcome ? `&outcome=${outcome}` : "") +
        (startedAfter ? `&started_after=${encodeURIComponent(startedAfter)}` : ""),
    ),
  pauseScan: (id: number) => fetchApi<Scan>(`/admin/scans/${id}/pause`, { method: "POST" }),
  resumeScan: (id: number) => fetchApi<Scan>(`/admin/scans/${id}/resume`, { method: "POST" }),
  deleteScan: (id: number) => fetchApi<void>(`/admin/scans/${id}`, { method: "DELETE" }),
};
