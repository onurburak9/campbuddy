import { useQuery } from "@tanstack/react-query";
import { runs } from "../api/runs";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanRuns(scanId: number | null, page: number) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, PAGE_SIZE),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RUNS_PAGE_SIZE };
