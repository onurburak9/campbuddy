import { fetchApi } from "./client";
import type { AdminUser, AdminScan, Scan } from "../types";

export const admin = {
  listUsers: () => fetchApi<AdminUser[]>("/admin/users"),
  listScans: () => fetchApi<AdminScan[]>("/admin/scans"),
  pauseScan: (id: number) => fetchApi<Scan>(`/admin/scans/${id}/pause`, { method: "POST" }),
  resumeScan: (id: number) => fetchApi<Scan>(`/admin/scans/${id}/resume`, { method: "POST" }),
  deleteScan: (id: number) => fetchApi<void>(`/admin/scans/${id}`, { method: "DELETE" }),
};
