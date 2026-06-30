import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanResults(scanId: number | null, page: number) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, PAGE_SIZE),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
