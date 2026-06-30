import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanResults(scanId: number | null, page: number, pageSize: number = PAGE_SIZE) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page, pageSize) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, pageSize),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
