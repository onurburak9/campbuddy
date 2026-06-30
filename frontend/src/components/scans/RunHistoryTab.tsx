import { useState } from "react";
import { useScanRuns, RUNS_PAGE_SIZE } from "../../hooks/useRuns";
import { RunRow } from "./RunRow";
import { Pagination } from "../ui/Pagination";
import { Spinner } from "../ui/Spinner";

export function RunHistoryTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const { data: runs, isLoading } = useScanRuns(scanId, page);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!runs || runs.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No runs yet</p>;

  return (
    <div>
      {runs.map((r) => <RunRow key={r.id} run={r} />)}
      <Pagination
        page={page}
        hasNext={runs.length === RUNS_PAGE_SIZE}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}
