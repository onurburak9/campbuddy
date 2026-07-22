import { useQuery } from "@tanstack/react-query";
import { runs } from "../api/runs";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanRuns(
  scanId: number | null,
  page: number,
  pageSize: number = PAGE_SIZE,
  outcome?: string,
  startedAfter?: string,
  options?: { refetchInterval?: number | false },
) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page, pageSize, outcome, startedAfter) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, pageSize, outcome, startedAfter),
    enabled: scanId != null,
    refetchInterval: options?.refetchInterval,
  });
}

export function useScanRunsCount(scanId: number | null, outcome?: string, startedAfter?: string) {
  return useQuery({
    queryKey: scanId ? queryKeys.runsCount(scanId, outcome, startedAfter) : ["scans", "none", "runs", "count"],
    queryFn: () => runs.count(scanId as number, outcome, startedAfter),
    enabled: scanId != null,
  });
}

export function useRunResults(scanId: number, runId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.runResults(scanId, runId),
    queryFn: () => runs.runResults(scanId, runId),
    enabled,
  });
}

export { PAGE_SIZE as RUNS_PAGE_SIZE };
