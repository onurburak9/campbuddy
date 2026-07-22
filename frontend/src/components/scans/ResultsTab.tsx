import { useEffect, useMemo, useState } from "react";
import { useAllScanResults, RESULTS_PAGE_SIZE } from "../../hooks/useResults";
import { hasGroupableResults } from "../../lib/groupResults";
import { cn } from "../../lib/cn";
import { ResultCard } from "./ResultCard";
import { GroupedResultsView } from "./GroupedResultsView";
import { Pagination } from "../ui/Pagination";
import { PageSizeSelect } from "../ui/PageSizeSelect";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Spinner } from "../ui/Spinner";

type ViewMode = "grouped" | "flat";

export function ResultsTab({ scanId }: { scanId: number }) {
  const { data: all, isLoading } = useAllScanResults(scanId);
  const [search, setSearch] = useState("");
  const [facility, setFacility] = useState("all");
  const [type, setType] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(RESULTS_PAGE_SIZE);
  const [view, setView] = useState<ViewMode>("grouped");
  const [viewInitialized, setViewInitialized] = useState(false);

  useEffect(() => {
    if (!viewInitialized && all) {
      setView(hasGroupableResults(all) ? "grouped" : "flat");
      setViewInitialized(true);
    }
  }, [all, viewInitialized]);

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
        (view === "flat" ? facility === "all" || r.facility_name === facility : true) &&
        (type === "all" || r.campsite_type === type) &&
        (q === "" || `${r.site_name} ${r.facility_name}`.toLowerCase().includes(q)),
    );
  }, [all, search, facility, type, view]);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!all || all.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No results yet</p>;

  const resetPage = () => setPage(1);
  const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex overflow-hidden rounded-md border border-sand-200 dark:border-[#222]">
          <button
            type="button"
            onClick={() => setView("grouped")}
            className={cn(
              "px-3 py-2 text-sm",
              view === "grouped"
                ? "bg-forest-700 text-white"
                : "bg-white text-stone-600 dark:bg-[#1A1A1A] dark:text-[#888]",
            )}
          >
            Grouped
          </button>
          <button
            type="button"
            onClick={() => setView("flat")}
            className={cn(
              "px-3 py-2 text-sm",
              view === "flat"
                ? "bg-forest-700 text-white"
                : "bg-white text-stone-600 dark:bg-[#1A1A1A] dark:text-[#888]",
            )}
          >
            Flat
          </button>
        </div>
        <Input
          placeholder="Search site or campground…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); resetPage(); }}
          className="w-56"
        />
        {view === "flat" && (
          <Select
            value={facility}
            onChange={(v) => { setFacility(v); resetPage(); }}
            options={[{ value: "all", label: "All campgrounds" }, ...facilities.map((f) => ({ value: f, label: f }))]}
          />
        )}
        <Select
          value={type}
          onChange={(v) => { setType(v); resetPage(); }}
          options={[{ value: "all", label: "All types" }, ...types.map((t) => ({ value: t, label: t }))]}
        />
        {view === "flat" && (
          <div className="ml-auto">
            <PageSizeSelect value={pageSize} onChange={(n) => { setPageSize(n); resetPage(); }} />
          </div>
        )}
      </div>
      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">No results match your filters</p>
      ) : view === "grouped" ? (
        <GroupedResultsView results={filtered} />
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
