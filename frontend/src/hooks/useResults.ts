import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";
import type { ScanResult } from "../types";

const PAGE_SIZE = 20;
const FETCH_ALL_PAGE_SIZE = 100;

export function useScanResults(scanId: number | null, page: number, pageSize: number = PAGE_SIZE) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page, pageSize) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, pageSize),
    enabled: scanId != null,
  });
}

export function useAllScanResults(scanId: number | null) {
  return useQuery({
    queryKey: scanId ? queryKeys.allResults(scanId) : ["scans", "none", "results", "all"],
    queryFn: async () => {
      const acc: ScanResult[] = [];
      let page = 1;
      for (;;) {
        const batch = await results.list(scanId as number, page, FETCH_ALL_PAGE_SIZE);
        acc.push(...batch);
        if (batch.length < FETCH_ALL_PAGE_SIZE) break;
        page += 1;
      }
      return acc;
    },
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
