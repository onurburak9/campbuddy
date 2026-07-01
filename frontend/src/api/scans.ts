import { fetchApi } from "./client";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, ScanStats } from "../types";

export const scans = {
  list: () => fetchApi<Scan[]>("/scans"),
  get: (id: number) => fetchApi<Scan>(`/scans/${id}`),
  create: (payload: ScanCreatePayload) =>
    fetchApi<Scan>("/scans", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: ScanUpdatePayload) =>
    fetchApi<Scan>(`/scans/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id: number) => fetchApi<void>(`/scans/${id}`, { method: "DELETE" }),
  pause: (id: number) => fetchApi<Scan>(`/scans/${id}/pause`, { method: "POST" }),
  resume: (id: number) => fetchApi<Scan>(`/scans/${id}/resume`, { method: "POST" }),
  stats: (id: number) => fetchApi<ScanStats>(`/scans/${id}/stats`),
};
