# Results Search / Run-History Time Filter / Overview Config Card — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add client-side search/filter to the Results tab, a server-side time-range filter to Run History, and a Configuration card to the Overview tab.

**Architecture:** One tiny backend addition (`started_after` param on the runs endpoint). Everything else is frontend: a fetch-all-results hook for client-side filtering, a range dropdown, and a new ConfigCard that replaces the standalone SearchWindowsList on Overview. Backend runs on the main tree (foreground) — no worktree.

**Tech Stack:** FastAPI + SQLAlchemy + pydantic v1 (backend); React 18 + TS + TanStack Query + Vitest/MSW (frontend).

## Global Constraints

- **Results filtering is client-side.** Fetch ALL of a scan's results by paging the existing endpoint at `page_size=100` until a short page; then search/filter/paginate in-browser. No backend change for Results.
- **Result filters:** name **search** (over `site_name` + `facility_name`), **Facility** dropdown (distinct `facility_name`), **Type** dropdown (distinct `campsite_type`). NO "area" filter (not a per-result field).
- **Run History time filter is server-side:** `started_after` (ISO datetime) query param; ranges **All / 6h / 24h / 7d / 30d** (default All); combines with the existing `outcome` (found-only) filter and page-size.
- **Overview ConfigCard** shows provider, rec-area/campground/campsite IDs, search windows, nights, days-of-week (Mon=0..Sun=6), weekends-only, polling interval (`formatInterval`), notifications. It **replaces** the standalone `SearchWindowsList` on Overview, which is **removed**.
- **Days of week:** Monday=0 … Sunday=6.
- **Page sizes:** 20 / 50 / 100 (via existing `PageSizeSelect`).
- **Analytics are OUT of scope** (deferred — ADR 008).
- Frontend typecheck: `npx tsc --noEmit` (NOT `npm run lint`). Full test run: `npx vitest run` from `frontend/`. Backend tests: `.venv/bin/pytest`.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## File Structure

- **Task 1 (backend):** `core/services/history.py` (`list_runs` gains `started_after`), `api/routes/scans.py` (runs route param), tests.
- **Task 2 (plumbing):** `src/hooks/queryKeys.ts` (+`allResults`, `runs` gains `startedAfter`), `src/api/runs.ts` (`list` gains `startedAfter`), `src/hooks/useRuns.ts` (`useScanRuns` gains `startedAfter`), `src/hooks/useResults.ts` (+`useAllScanResults`), tests.
- **Task 3:** `src/components/scans/ResultsTab.tsx` (rework), test.
- **Task 4:** `src/components/scans/RunHistoryTab.tsx` (range dropdown), test.
- **Task 5:** `src/components/scans/ConfigCard.tsx` (new), `src/components/scans/OverviewTab.tsx` (use ConfigCard), remove `src/components/scans/SearchWindowsList.tsx`, tests.

**Execution order:** 1 → 2 → 3 → 4 → 5 (all foreground on `spec/web-ui-design`).

---

## Task 1: Backend — `started_after` filter on the runs endpoint

**Files:**
- Modify: `core/services/history.py`, `api/routes/scans.py`
- Test: `tests/services/test_history.py`, `tests/api/test_scans.py`

**Interfaces:**
- Produces: `history.list_runs(..., started_after=None)`; `GET /api/v1/scans/{id}/runs?started_after=<ISO>`.
- Consumes: existing `get_scan`, `ScanRun`.

- [ ] **Step 1: Write the failing service test**

In `tests/services/test_history.py`, mirror the existing run fixtures. Add:
```python
from datetime import datetime, timezone, timedelta

def test_list_runs_filters_by_started_after(db, seeded_scan_with_runs):
    scan = seeded_scan_with_runs  # has runs across a range of started_at
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recent = history_svc.list_runs(db, scan.id, scan.user_id, started_after=cutoff)
    assert all(r.started_at >= cutoff for r in recent)
    all_runs = history_svc.list_runs(db, scan.id, scan.user_id)
    assert len(recent) <= len(all_runs)
```
Adapt to the module's existing run-building fixture (create at least one run older than 1 day and one newer).

- [ ] **Step 2: Run it, verify failure**

Run: `.venv/bin/pytest tests/services/test_history.py -k started_after -v`
Expected: FAIL (`list_runs` has no `started_after` kwarg).

- [ ] **Step 3: Implement in `core/services/history.py`**

Replace `list_runs` with:
```python
def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20, outcome=None, started_after=None) -> list:
    get_scan(db, scan_id, user_id)
    q = db.query(ScanRun).filter(ScanRun.scan_id == scan_id)
    if outcome is not None:
        q = q.filter(ScanRun.outcome == outcome)
    if started_after is not None:
        q = q.filter(ScanRun.started_at >= started_after)
    return (
        q.order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
```

- [ ] **Step 4: Run the service test, verify pass**

Run: `.venv/bin/pytest tests/services/test_history.py -k started_after -v`
Expected: PASS.

- [ ] **Step 5: Write the failing route test**

In `tests/api/test_scans.py`, mirror the existing runs-route fixture/auth pattern. Add:
```python
def test_runs_started_after_filter(client, auth_client, scan_with_runs):
    scan = scan_with_runs
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = auth_client.get(f"/api/v1/scans/{scan.id}/runs?started_after={cutoff}")
    assert r.status_code == 200
    for item in r.json():
        assert item["started_at"] >= cutoff
```
Use the existing authenticated client fixture (the same one the other runs-route tests use).

- [ ] **Step 6: Run it, verify failure**

Run: `.venv/bin/pytest tests/api/test_scans.py -k started_after -v`
Expected: FAIL (route rejects/ignores the param).

- [ ] **Step 7: Implement the route param in `api/routes/scans.py`**

Add `from datetime import datetime` to the imports at the top. Update the runs route:
```python
@router.get("/{scan_id}/runs", response_model=List[ScanRunResponse])
def list_runs(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    outcome: Optional[ScanOutcome] = Query(default=None),
    started_after: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_runs(
        db, scan_id, user.id, page=page, page_size=page_size,
        outcome=outcome, started_after=started_after,
    )
```

- [ ] **Step 8: Run tests, verify pass + full backend sanity**

Run: `.venv/bin/pytest tests/api/test_scans.py tests/services/test_history.py -q`
Expected: PASS (all).

- [ ] **Step 9: Commit**

```bash
git add core/services/history.py api/routes/scans.py tests/services/test_history.py tests/api/test_scans.py
git commit -m "feat(api): started_after time filter on the runs endpoint"
```

---

## Task 2: Frontend plumbing — startedAfter on runs, useAllScanResults

**Files:**
- Modify: `src/hooks/queryKeys.ts`, `src/api/runs.ts`, `src/hooks/useRuns.ts`, `src/hooks/useResults.ts`
- Test: `src/hooks/useResults.test.tsx` (new)

**Interfaces:**
- Produces: `useScanRuns(scanId, page, pageSize?, outcome?, startedAfter?)`; `useAllScanResults(scanId)` → `ScanResult[]` (all pages); `queryKeys.allResults(id)`.
- Consumes: `results.list`, `runs.list`.

- [ ] **Step 1: Update `src/hooks/queryKeys.ts`**

Change the `runs` key and add `allResults`:
```ts
export const queryKeys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  scans: ["scans"] as const,
  scan: (id: number) => ["scans", id] as const,
  stats: (id: number) => ["scans", id, "stats"] as const,
  runs: (id: number, page: number, pageSize: number, outcome?: string, startedAfter?: string) =>
    ["scans", id, "runs", { page, pageSize, outcome: outcome ?? null, startedAfter: startedAfter ?? null }] as const,
  runResults: (id: number, runId: number) =>
    ["scans", id, "runs", runId, "results"] as const,
  results: (id: number, page: number, pageSize: number) =>
    ["scans", id, "results", { page, pageSize }] as const,
  allResults: (id: number) => ["scans", id, "results", "all"] as const,
};
```

- [ ] **Step 2: Update `src/api/runs.ts`**

```ts
import { fetchApi } from "./client";
import type { ScanRun, ScanResult } from "../types";

export const runs = {
  list: (scanId: number, page = 1, pageSize = 20, outcome?: string, startedAfter?: string) =>
    fetchApi<ScanRun[]>(
      `/scans/${scanId}/runs?page=${page}&page_size=${pageSize}` +
        (outcome ? `&outcome=${outcome}` : "") +
        (startedAfter ? `&started_after=${encodeURIComponent(startedAfter)}` : ""),
    ),
  runResults: (scanId: number, runId: number) =>
    fetchApi<ScanResult[]>(`/scans/${scanId}/runs/${runId}/results`),
};
```

- [ ] **Step 3: Update `src/hooks/useRuns.ts`**

```ts
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
) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page, pageSize, outcome, startedAfter) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, pageSize, outcome, startedAfter),
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
```

- [ ] **Step 4: Write the failing `useAllScanResults` test**

`src/hooks/useResults.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { useAllScanResults } from "./useResults";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function makeResult(id: number) {
  return { id, scan_run_id: 1, scan_id: 7, campsite_id: String(id), facility_name: "F",
    site_name: `S${id}`, campsite_type: "TENT", booking_date: "2026-07-01",
    booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z",
    cart_added: false, notified: false };
}

describe("useAllScanResults", () => {
  it("pages through until a short page and concatenates", async () => {
    server.use(http.get("/api/v1/scans/7/results", ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get("page"));
      if (page === 1) return HttpResponse.json(Array.from({ length: 100 }, (_, i) => makeResult(i + 1)));
      return HttpResponse.json([makeResult(101), makeResult(102)]); // short page → stop
    }));
    const { result } = renderHook(() => useAllScanResults(7), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(102);
  });
});
```

- [ ] **Step 5: Run it, verify failure**

Run: `cd frontend && npx vitest run src/hooks/useResults.test.tsx`
Expected: FAIL (`useAllScanResults` not exported).

- [ ] **Step 6: Implement `useAllScanResults` in `src/hooks/useResults.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";
import type { ScanResult } from "../types";

const PAGE_SIZE = 20;
const FETCH_ALL_PAGE_SIZE = 100;

export function useScanResults(scanId: number | null, page: number, pageSize: number = PAGE_SIZE) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page, pageSize) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, pageSize),
    enabled: scanId != null,
  });
}

export function useAllScanResults(scanId: number | null) {
  return useQuery({
    queryKey: scanId ? queryKeys.allResults(scanId) : ["scans", "none", "results", "all"],
    queryFn: async () => {
      const acc: ScanResult[] = [];
      let page = 1;
      for (;;) {
        const batch = await results.list(scanId as number, page, FETCH_ALL_PAGE_SIZE);
        acc.push(...batch);
        if (batch.length < FETCH_ALL_PAGE_SIZE) break;
        page += 1;
      }
      return acc;
    },
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
```

- [ ] **Step 7: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (full suite; existing useScanRuns callers still compile via defaults).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/hooks/queryKeys.ts frontend/src/api/runs.ts frontend/src/hooks/useRuns.ts frontend/src/hooks/useResults.ts frontend/src/hooks/useResults.test.tsx
git commit -m "feat(ui): startedAfter runs param + useAllScanResults fetch-all hook"
```

---

## Task 3: Results tab — client-side search + Facility/Type filters

**Files:**
- Modify: `src/components/scans/ResultsTab.tsx`
- Test: `src/components/scans/ResultsTab.test.tsx` (rework)

**Interfaces:**
- Consumes: `useAllScanResults` (Task 2), `Input`, `Select`, `PageSizeSelect`, `Pagination`, `ResultCard`, `Spinner`.

- [ ] **Step 1: Rework `src/components/scans/ResultsTab.tsx`**

```tsx
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
```

- [ ] **Step 2: Rework `src/components/scans/ResultsTab.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ResultsTab } from "./ResultsTab";

const mk = (id: number, facility: string, type: string, site: string) => ({
  id, scan_run_id: 9, scan_id: 7, campsite_id: `C${id}`, facility_name: facility,
  site_name: site, campsite_type: type, booking_date: "2026-07-01",
  booking_end_date: "2026-07-03", booking_url: "https://x", first_seen_at: "2026-06-30T11:00:00Z",
  cart_added: false, notified: true,
});
const rows = [
  mk(1, "Moraine", "TENT", "Site 42"),
  mk(2, "Sunset", "RV", "Site 7"),
  mk(3, "Moraine", "RV", "Loop A"),
];

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ResultsTab (client-side filtering)", () => {
  it("renders all results, then filters by search and by facility", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(rows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByText("Site 7")).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/search/i), "loop");
    await waitFor(() => expect(screen.getByText("Loop A")).toBeInTheDocument());
    expect(screen.queryByText("Site 42")).not.toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText(/search/i));
    // Facility dropdown → Sunset
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "" }), "Sunset").catch(() => {});
  });

  it("shows the no-match message when filters exclude everything", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(rows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    await userEvent.type(screen.getByPlaceholderText(/search/i), "zzzznomatch");
    await waitFor(() => expect(screen.getByText(/no results match your filters/i)).toBeInTheDocument());
  });
});
```
> Note: there are multiple `combobox`es (facility, type, page-size); if `getByRole("combobox", { name: "" })` is ambiguous, target the facility select by its option text instead (e.g. `screen.getByRole("option", { name: "All campgrounds" })`'s select) or add an `aria-label`. Keep the two assertions that matter: search narrows the list, and the no-match message appears. The author may simplify the facility-select interaction if selectors are awkward, but MUST keep the search-narrows and no-match assertions.

- [ ] **Step 3: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/scans/ResultsTab.test.tsx`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/scans/ResultsTab.tsx frontend/src/components/scans/ResultsTab.test.tsx
git commit -m "feat(ui): client-side search + facility/type filters on Results"
```

---

## Task 4: Run History — time-range filter

**Files:**
- Modify: `src/components/scans/RunHistoryTab.tsx`
- Test: `src/components/scans/RunHistoryTab.test.tsx` (extend)

**Interfaces:**
- Consumes: `useScanRuns(..., startedAfter?)` (Task 2), `Select`, `Toggle`, `PageSizeSelect`, `Pagination`, `RunRow`, `Spinner`.

- [ ] **Step 1: Rework `src/components/scans/RunHistoryTab.tsx`**

```tsx
import { useState } from "react";
import { useScanRuns, RUNS_PAGE_SIZE } from "../../hooks/useRuns";
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
  const { data: runs, isLoading } = useScanRuns(
    scanId, page, pageSize, foundOnly ? "success" : undefined, cutoffISO(range),
  );

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
            hasNext={runs.length === pageSize}
            onPrev={() => setPage((p) => Math.max(1, p - 1))}
            onNext={() => setPage((p) => p + 1)}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Extend `src/components/scans/RunHistoryTab.test.tsx`**

Add a test that asserts selecting a range sends `started_after`:
```tsx
it("passes started_after when a time range is selected", async () => {
  let lastUrl = "";
  server.use(http.get("/api/v1/scans/7/runs", ({ request }) => {
    lastUrl = request.url;
    return HttpResponse.json([]);
  }));
  wrap(<RunHistoryTab scanId={7} />);
  await waitFor(() => expect(lastUrl).toContain("/scans/7/runs"));
  // pick "Last 7 days" from the range select
  const selects = screen.getAllByRole("combobox");
  await userEvent.selectOptions(selects[0], "7d");
  await waitFor(() => expect(lastUrl).toContain("started_after="));
});
```
> `getAllByRole("combobox")` returns [range, page-size]; index 0 is the range select (first in DOM). If ordering differs, select by option label ("Last 7 days"). Keep the assertion that `started_after=` appears in the request after selecting a range. Ensure `userEvent` is imported.

- [ ] **Step 3: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/scans/RunHistoryTab.test.tsx`
Expected: PASS (the existing expand test still passes).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/scans/RunHistoryTab.tsx frontend/src/components/scans/RunHistoryTab.test.tsx
git commit -m "feat(ui): time-range filter on Run History"
```

---

## Task 5: Overview — Configuration card (replaces SearchWindowsList)

**Files:**
- Create: `src/components/scans/ConfigCard.tsx`
- Modify: `src/components/scans/OverviewTab.tsx`
- Delete: `src/components/scans/SearchWindowsList.tsx`
- Test: `src/components/scans/ConfigCard.test.tsx` (new); update `src/components/scans/OverviewTab.test.tsx` if it referenced SearchWindowsList.

**Interfaces:**
- Consumes: `dateRange`, `formatInterval` from `lib/format`; `Scan` type.
- Produces: `ConfigCard({ scan })`.

- [ ] **Step 1: Write the failing `ConfigCard.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfigCard } from "./ConfigCard";
import type { Scan } from "../../types";

const scan: Scan = {
  id: 5, user_id: 1, provider: "RecreationDotGov", name: "Trip", status: "active",
  polling_interval: 600, rec_area_ids: null, campground_ids: [10357105, 10357111],
  campsite_ids: null, search_windows: [{ start_date: "2026-07-03", end_date: "2026-07-05" }],
  nights: 2, days_of_week: [4, 5], weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

describe("ConfigCard", () => {
  it("renders the scan configuration", () => {
    render(<ConfigCard scan={scan} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("RecreationDotGov")).toBeInTheDocument();
    expect(screen.getByText(/10357105, 10357111/)).toBeInTheDocument();
    expect(screen.getByText(/10 min/)).toBeInTheDocument();     // polling
    expect(screen.getByText(/Email/)).toBeInTheDocument();      // notifications
    expect(screen.getByText("Fri")).toBeInTheDocument();        // day-of-week chip
  });
});
```

- [ ] **Step 2: Run it, verify failure**

Run: `cd frontend && npx vitest run src/components/scans/ConfigCard.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `src/components/scans/ConfigCard.tsx`**

```tsx
import { dateRange, formatInterval } from "../../lib/format";
import { cn } from "../../lib/cn";
import type { Scan } from "../../types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function ids(v: number[] | null | undefined): string {
  return v && v.length ? v.join(", ") : "—";
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
      <span className="w-40 shrink-0 text-sm text-stone-400">{label}</span>
      <span className="text-sm text-stone-700 dark:text-[#CCC]">{children}</span>
    </div>
  );
}

export function ConfigCard({ scan }: { scan: Scan }) {
  const notifs =
    [
      scan.notify_via_email ? "Email" : null,
      scan.notify_via_telegram ? "Telegram" : null,
      scan.notify_on_new_only ? "New only" : null,
    ]
      .filter(Boolean)
      .join(" · ") || "None";

  return (
    <div className="rounded-lg border border-sand-200 bg-white p-5 dark:border-[#222] dark:bg-[#1A1A1A]">
      <h3 className="mb-3 text-sm font-semibold text-stone-800 dark:text-[#EEE]">Configuration</h3>
      <div className="space-y-2">
        <Row label="Provider">{scan.provider}</Row>
        <Row label="Recreation areas">{ids(scan.rec_area_ids)}</Row>
        <Row label="Campgrounds">{ids(scan.campground_ids)}</Row>
        <Row label="Campsites">{ids(scan.campsite_ids)}</Row>
        <Row label="Search windows">
          <span className="flex flex-wrap gap-1.5">
            {scan.search_windows.map((w, i) => (
              <span key={i} className="rounded-full bg-sand-100 px-2.5 py-0.5 text-xs text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
                {dateRange(w.start_date, w.end_date)}
              </span>
            ))}
          </span>
        </Row>
        <Row label="Nights">{scan.nights}</Row>
        <Row label="Days of week">
          {scan.days_of_week && scan.days_of_week.length ? (
            <span className="flex flex-wrap gap-1">
              {DAYS.map((d, i) => (
                <span key={d} className={cn(
                  "rounded px-1.5 py-0.5 text-xs",
                  scan.days_of_week!.includes(i)
                    ? "bg-forest-600 text-white"
                    : "bg-sand-100 text-stone-400 dark:bg-[#222]",
                )}>
                  {d}
                </span>
              ))}
            </span>
          ) : (
            "Any"
          )}
        </Row>
        <Row label="Weekends only">{scan.weekends_only ? "Yes" : "No"}</Row>
        <Row label="Polling">every {formatInterval(scan.polling_interval)}</Row>
        <Row label="Notifications">{notifs}</Row>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the ConfigCard test, verify pass**

Run: `cd frontend && npx vitest run src/components/scans/ConfigCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Update `src/components/scans/OverviewTab.tsx`**

Replace the `SearchWindowsList` import + usage with `ConfigCard`:
```tsx
import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { useScanResults } from "../../hooks/useResults";
import { relativeTime } from "../../lib/format";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { ConfigCard } from "./ConfigCard";
import type { Scan } from "../../types";

export function OverviewTab({ scan }: { scan: Scan }) {
  const { data: stats } = useScanStats(scan.id);
  const { data: runs = [] } = useScanRuns(scan.id, 1);
  const { data: results = [] } = useScanResults(scan.id, 1);

  const lastChecked = runs[0]?.started_at;
  const lastFound = results[0]?.first_seen_at;

  return (
    <div className="space-y-6">
      <StatsRow
        sitesFound={stats?.sites_found ?? 0}
        inCart={stats?.in_cart ?? 0}
        totalRuns={stats?.total_runs ?? 0}
        successRate={stats?.success_rate ?? 0}
      />
      <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm text-stone-500 dark:text-[#888]">
        <span>Last checked: <span className="text-stone-700 dark:text-[#CCC]">{lastChecked ? relativeTime(lastChecked) : "—"}</span></span>
        <span>Last new site found: <span className="text-stone-700 dark:text-[#CCC]">{lastFound ? relativeTime(lastFound) : "—"}</span></span>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Recent Run Health</h3>
        <RunHealthBar runs={runs} />
      </div>
      <ConfigCard scan={scan} />
    </div>
  );
}
```

- [ ] **Step 6: Delete `SearchWindowsList.tsx` and check for other references**

```bash
cd frontend
grep -rn "SearchWindowsList" src || echo "no references remain"
git rm src/components/scans/SearchWindowsList.tsx
```
If `grep` shows any remaining import besides the one just removed from OverviewTab, remove it too. (Expected: none — OverviewTab was its only consumer.) If `src/components/scans/OverviewTab.test.tsx` asserted the old "Search Windows" heading, update that assertion to check for the ConfigCard (e.g. `screen.getByText("Configuration")`); the last-checked/last-found assertions stay.

- [ ] **Step 7: Run tests + typecheck (full suite)**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (all).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/scans/ConfigCard.tsx frontend/src/components/scans/ConfigCard.test.tsx frontend/src/components/scans/OverviewTab.tsx frontend/src/components/scans/OverviewTab.test.tsx
git rm frontend/src/components/scans/SearchWindowsList.tsx
git commit -m "feat(ui): Overview Configuration card (replaces SearchWindowsList)"
```

---

## Self-Review

- **Spec coverage:** Results client-side search + Facility/Type + client pagination (Task 3, via Task 2's `useAllScanResults`); Run History `started_after` + range dropdown (Task 1 backend + Task 4 frontend); Overview ConfigCard replacing SearchWindowsList (Task 5). Analytics deferred (ADR 008) — no task, correct. All covered.
- **Type consistency:** `useScanRuns(scanId, page, pageSize?, outcome?, startedAfter?)` — OverviewTab's `useScanRuns(scan.id, 1)` and RunHistoryTab's call both compile via defaults; `queryKeys.runs` gains `startedAfter?` in the same task (Task 2). `useAllScanResults(scanId)` ↔ `queryKeys.allResults(id)` ↔ `results.list` names align. `runs.list(..., startedAfter?)` matches the hook. `ConfigCard({ scan })` prop matches OverviewTab usage. `formatInterval`/`dateRange` already in `lib/format.ts`.
- **Placeholder scan:** the two frontend test steps note where a selector may be simplified but pin the assertions that must remain; backend test fixtures say "mirror existing" because fixture names live in the test files the implementer reads — all implementation code is complete/literal.
- **DRY:** ConfigCard reuses `dateRange`/`formatInterval`/`cn`; `PageSizeSelect`/`Select`/`Input` reused; SearchWindowsList removed (its chip rendering folded into ConfigCard).
