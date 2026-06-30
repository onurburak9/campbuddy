import { useState } from "react";
import { useScanRuns, RUNS_PAGE_SIZE } from "../../hooks/useRuns";
import { RunRow } from "./RunRow";
import { Pagination } from "../ui/Pagination";
import { PageSizeSelect } from "../ui/PageSizeSelect";
import { Toggle } from "../ui/Toggle";
import { Spinner } from "../ui/Spinner";

export function RunHistoryTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(RUNS_PAGE_SIZE);
  const [foundOnly, setFoundOnly] = useState(false);
  const { data: runs, isLoading } = useScanRuns(scanId, page, pageSize, foundOnly ? "success" : undefined);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <Toggle label="Found sites only" checked={foundOnly} onChange={(v) => { setFoundOnly(v); setPage(1); }} />
        <PageSizeSelect value={pageSize} onChange={(n) => { setPageSize(n); setPage(1); }} />
      </div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : !runs || runs.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">No runs yet</p>
      ) : (
        <>
          {runs.map((r) => <RunRow key={r.id} scanId={scanId} run={r} />)}
          <Pagination
            page={page}
            hasNext={runs.length === pageSize}
            onPrev={() => setPage((p) => Math.max(1, p - 1))}
            onNext={() => setPage((p) => p + 1)}
          />
        </>
      )}
    </div>
  );
}
