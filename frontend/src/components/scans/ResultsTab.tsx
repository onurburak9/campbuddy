import { useState } from "react";
import { useScanResults, RESULTS_PAGE_SIZE } from "../../hooks/useResults";
import { ResultCard } from "./ResultCard";
import { Pagination } from "../ui/Pagination";
import { PageSizeSelect } from "../ui/PageSizeSelect";
import { Spinner } from "../ui/Spinner";

export function ResultsTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(RESULTS_PAGE_SIZE);
  const { data: results, isLoading } = useScanResults(scanId, page, pageSize);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!results || results.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No results yet</p>;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <PageSizeSelect value={pageSize} onChange={(n) => { setPageSize(n); setPage(1); }} />
      </div>
      {results.map((r) => <ResultCard key={r.id} result={r} />)}
      <Pagination
        page={page}
        hasNext={results.length === pageSize}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}
