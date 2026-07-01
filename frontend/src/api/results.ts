import { fetchApi } from "./client";
import type { ScanResult } from "../types";

export const results = {
  list: (scanId: number, page = 1, pageSize = 20) =>
    fetchApi<ScanResult[]>(`/scans/${scanId}/results?page=${page}&page_size=${pageSize}`),
};
