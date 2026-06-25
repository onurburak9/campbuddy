import { fetchApi } from "./client";
import type { ScanRun } from "../types";

export const runs = {
  list: (scanId: number, page = 1, pageSize = 20) =>
    fetchApi<ScanRun[]>(`/scans/${scanId}/runs?page=${page}&page_size=${pageSize}`),
};
