import { useMemo, useState } from "react";
import { useScanRuns, useScanRunsCount, RUNS_PAGE_SIZE } from "../../hooks/useRuns";
import { RunRow } from "./RunRow";
import { Pagination } from "../ui/Pagination";
import { PageSizeSelect } from "../ui/PageSizeSelect";
import { Select } from "../ui/Select";
import { Toggle } from "../ui/Toggle";
import { Spinner } from "../ui/Spinner";

const RANGE_OPTIONS = [
  { value: "all", label: "All time" },
  { value: "6h", label: "Last 6 hours" },
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
];
const RANGE_MS: Record<string, number> = {
  "6h": 6 * 3600_000,
  "24h": 24 * 3600_000,
  "7d": 7 * 24 * 3600_000,
  "30d": 30 * 24 * 3600_000,
};
function cutoffISO(range: string): string | undefined {
  return range === "all" ? undefined : new Date(Date.now() - RANGE_MS[range]).toISOString();
}

export function RunHistoryTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(RUNS_PAGE_SIZE);
  const [foundOnly, setFoundOnly] = useState(false);
  const [range, setRange] = useState("all");
  const startedAfter = useMemo(() => cutoffISO(range), [range]);
  const outcome = foundOnly ? "success" : undefined;
  const { data: runs, isLoading } = useScanRuns(scanId, page, pageSize, outcome, startedAfter);
  const { data: countData } = useScanRunsCount(scanId, outcome, startedAfter);
  const totalPages = countData ? Math.max(1, Math.ceil(countData.total / pageSize)) : undefined;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Toggle label="Found sites only" checked={foundOnly} onChange={(v) => { setFoundOnly(v); setPage(1); }} />
        <Select value={range} onChange={(v) => { setRange(v); setPage(1); }} options={RANGE_OPTIONS} />
        <div className="ml-auto">
          <PageSizeSelect value={pageSize} onChange={(n) => { setPageSize(n); setPage(1); }} />
        </div>
      </div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : !runs || runs.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">No runs in this range</p>
      ) : (
        <>
          {runs.map((r) => <RunRow key={r.id} scanId={scanId} run={r} />)}
          <Pagination
            page={page}
            hasNext={totalPages != null ? page < totalPages : runs.length === pageSize}
            totalPages={totalPages}
            onPrev={() => setPage((p) => Math.max(1, p - 1))}
            onNext={() => setPage((p) => p + 1)}
          />
        </>
      )}
    </div>
  );
}
