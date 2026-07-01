import { useMemo, useState } from "react";
import { useAllScanResults, RESULTS_PAGE_SIZE } from "../../hooks/useResults";
import { ResultCard } from "./ResultCard";
import { Pagination } from "../ui/Pagination";
import { PageSizeSelect } from "../ui/PageSizeSelect";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Spinner } from "../ui/Spinner";

export function ResultsTab({ scanId }: { scanId: number }) {
  const { data: all, isLoading } = useAllScanResults(scanId);
  const [search, setSearch] = useState("");
  const [facility, setFacility] = useState("all");
  const [type, setType] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(RESULTS_PAGE_SIZE);

  const facilities = useMemo(
    () => Array.from(new Set((all ?? []).map((r) => r.facility_name))).sort(),
    [all],
  );
  const types = useMemo(
    () => Array.from(new Set((all ?? []).map((r) => r.campsite_type))).sort(),
    [all],
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (all ?? []).filter(
      (r) =>
        (facility === "all" || r.facility_name === facility) &&
        (type === "all" || r.campsite_type === type) &&
        (q === "" || `${r.site_name} ${r.facility_name}`.toLowerCase().includes(q)),
    );
  }, [all, search, facility, type]);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!all || all.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No results yet</p>;

  const resetPage = () => setPage(1);
  const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <Input placeholder="Search site or campground…" value={search}
          onChange={(e) => { setSearch(e.target.value); resetPage(); }} className="w-56" />
        <Select value={facility} onChange={(v) => { setFacility(v); resetPage(); }}
          options={[{ value: "all", label: "All campgrounds" }, ...facilities.map((f) => ({ value: f, label: f }))]} />
        <Select value={type} onChange={(v) => { setType(v); resetPage(); }}
          options={[{ value: "all", label: "All types" }, ...types.map((t) => ({ value: t, label: t }))]} />
        <div className="ml-auto">
          <PageSizeSelect value={pageSize} onChange={(n) => { setPageSize(n); resetPage(); }} />
        </div>
      </div>
      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">No results match your filters</p>
      ) : (
        <>
          {pageItems.map((r) => <ResultCard key={r.id} result={r} />)}
          <Pagination
            page={page}
            hasNext={page * pageSize < filtered.length}
            onPrev={() => setPage((p) => Math.max(1, p - 1))}
            onNext={() => setPage((p) => p + 1)}
          />
        </>
      )}
    </div>
  );
}
