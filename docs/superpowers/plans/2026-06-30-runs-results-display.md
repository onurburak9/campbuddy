# Runs & Results Display Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a scan's runs and results views actually useful against real data — expandable per-run discovered sites, denser result cards, page-size + outcome filtering, and header/overview context — all using the current data model.

**Architecture:** Three small backend additions (a field, an endpoint, a query filter) plus frontend enhancements to the Results and Run History tabs, the scan header, and the Overview tab. Backend is a parallel side task in a git worktree; frontend continues on `spec/web-ui-design`.

**Tech Stack:** FastAPI + SQLAlchemy + pydantic v1 (backend); React 18 + TS + Vite + TanStack Query + Vitest/MSW (frontend).

## Global Constraints

- **Data semantics:** `scan_results` is deduped by `(scan_id, campsite_id, booking_date)`; each row's `scan_run_id` = the run that **first** discovered it. Per-run sites are labelled **"newly discovered in this run"**, never "currently available". The limitation is surfaced with a tooltip pointing at ADR 007.
- **Availability badges are OUT of scope** (deferred to ADR 007 — `last_seen_at`/`is_available`). Leave room in the ResultCard layout for a future badge.
- **Backend conventions:** pydantic v1 (`BaseModel`, `orm_mode`), ownership checks via `get_scan(db, scan_id, user_id)` (raises `NotFound`), service layer in `core/services/history.py`, routes in `api/routes/scans.py`. Tests mock external I/O, use in-memory SQLite (`docs/agents/testing.md`). Run backend tests with `.venv/bin/pytest`.
- **Frontend typecheck:** use `npx tsc --noEmit` (NOT `npm run lint` — a harness wrapper makes it spuriously exit 1). Full test run: `npx vitest run` from `frontend/`.
- **Page sizes:** 20 / 50 / 100 (max 100, matching the API's `page_size` ceiling). Default 20.
- **Outcome filter** uses `outcome=success` for the "Found sites only" toggle.
- Every commit message ends with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## File Structure

**Backend (Task B):**
- Modify `api/schemas.py` — add `scan_run_id` to `ScanResultResponse`.
- Modify `core/services/history.py` — `list_runs(outcome=...)`, new `list_run_results(...)`.
- Modify `api/routes/scans.py` — `outcome` query param on runs route; new per-run results route.
- Modify `tests/services/test_history.py`, `tests/api/test_scans.py`.

**Frontend:**
- F1: `src/lib/format.ts` (+ move `formatInterval`), `src/components/scans/ScanForm.tsx` (import it), `src/types/index.ts` (`scan_run_id`), `src/components/ui/PageSizeSelect.tsx` (new), tests.
- F2: `src/components/scans/ScanDetailHeader.tsx`, `src/components/scans/OverviewTab.tsx`, tests.
- F3: `src/api/results.ts` (no change needed), `src/hooks/useResults.ts`, `src/hooks/queryKeys.ts`, `src/components/scans/ResultsTab.tsx`, `src/components/scans/ResultCard.tsx`, tests.
- F4: `src/api/runs.ts`, `src/hooks/useRuns.ts`, `src/hooks/queryKeys.ts`, `src/components/scans/RunHistoryTab.tsx`, `src/components/scans/RunRow.tsx`, tests.

**Execution order:** Task B (side worktree) ∥ F1 → F2. Then merge B. Then F3 → F4.

---

## Task B: Backend — per-run results, scan_run_id, outcome filter

**Files:**
- Modify: `api/schemas.py`, `core/services/history.py`, `api/routes/scans.py`
- Test: `tests/services/test_history.py`, `tests/api/test_scans.py`

**Interfaces:**
- Produces: `GET /api/v1/scans/{scan_id}/runs/{run_id}/results` → `List[ScanResultResponse]`; `ScanResultResponse.scan_run_id: int`; `GET /api/v1/scans/{scan_id}/runs?outcome=success` filter.
- Consumes: existing `get_scan(db, scan_id, user_id)`, `NotFound` from `core.services.exceptions`.

- [ ] **Step 1: Add `scan_run_id` to `ScanResultResponse`**

In `api/schemas.py`, in `class ScanResultResponse`, add the field right after `id`:
```python
class ScanResultResponse(BaseModel):
    id: int
    scan_run_id: int
    scan_id: int
    campsite_id: str
    # ... rest unchanged
```

- [ ] **Step 2: Write failing service tests**

In `tests/services/test_history.py`, mirror the existing fixtures used by the `stats` tests. Add:
```python
import pytest
from core.services import history as history_svc
from core.services.exceptions import NotFound

def test_list_runs_filters_by_outcome(db, seeded_scan):
    # seeded_scan: a scan owned by user_id with >=1 success and >=1 no_results run
    success = history_svc.list_runs(db, seeded_scan.id, seeded_scan.user_id, outcome="success")
    assert all(r.outcome.value == "success" for r in success)
    all_runs = history_svc.list_runs(db, seeded_scan.id, seeded_scan.user_id)
    assert len(all_runs) >= len(success)

def test_list_run_results_returns_only_that_runs_sites(db, seeded_scan_with_results):
    scan, run, other_run = seeded_scan_with_results  # run has 2 results, other_run has 1
    rows = history_svc.list_run_results(db, scan.id, run.id, scan.user_id)
    assert {r.scan_run_id for r in rows} == {run.id}
    assert len(rows) == 2

def test_list_run_results_unknown_run_raises(db, seeded_scan):
    with pytest.raises(NotFound):
        history_svc.list_run_results(db, seeded_scan.id, 999999, seeded_scan.user_id)
```
Adapt the fixtures to the existing ones in this test module (the `stats` tests already build scans with runs/results — reuse or extend those builders rather than inventing new ones).

- [ ] **Step 3: Run the service tests, verify they fail**

Run: `.venv/bin/pytest tests/services/test_history.py -k "outcome or run_results" -v`
Expected: FAIL (`list_run_results` undefined; `list_runs` has no `outcome` kwarg).

- [ ] **Step 4: Implement service changes**

In `core/services/history.py`:
```python
from db.models import ScanRun, ScanResult, ScanOutcome
from core.services.scans import get_scan
from core.services.exceptions import NotFound


def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20, outcome=None) -> list:
    get_scan(db, scan_id, user_id)
    q = db.query(ScanRun).filter(ScanRun.scan_id == scan_id)
    if outcome is not None:
        q = q.filter(ScanRun.outcome == outcome)
    return (
        q.order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def list_run_results(db, scan_id: int, run_id: int, user_id: int) -> list:
    get_scan(db, scan_id, user_id)
    run = (
        db.query(ScanRun)
        .filter(ScanRun.id == run_id, ScanRun.scan_id == scan_id)
        .first()
    )
    if run is None:
        raise NotFound(f"Run {run_id} not found for scan {scan_id}")
    return (
        db.query(ScanResult)
        .filter(ScanResult.scan_run_id == run_id)
        .order_by(ScanResult.first_seen_at.desc())
        .all()
    )
```
(Leave `list_results` and `stats` unchanged.)

- [ ] **Step 5: Run service tests, verify they pass**

Run: `.venv/bin/pytest tests/services/test_history.py -v`
Expected: PASS (all, including the 3 new).

- [ ] **Step 6: Write failing route tests**

In `tests/api/test_scans.py`, mirror the existing authenticated-client pattern used by the runs/stats route tests. Add:
```python
def test_runs_outcome_filter(client, auth_headers, scan_with_runs):
    r = client.get(f"/api/v1/scans/{scan_with_runs.id}/runs?outcome=success", headers=auth_headers)
    assert r.status_code == 200
    assert all(item["outcome"] == "success" for item in r.json())

def test_run_results_endpoint(client, auth_headers, scan_with_results):
    scan, run = scan_with_results
    r = client.get(f"/api/v1/scans/{scan.id}/runs/{run.id}/results", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body and all(item["scan_run_id"] == run.id for item in body)

def test_run_results_404_for_unknown_run(client, auth_headers, scan_with_results):
    scan, _ = scan_with_results
    r = client.get(f"/api/v1/scans/{scan.id}/runs/999999/results", headers=auth_headers)
    assert r.status_code == 404
```
Use the same fixtures the existing scan-route tests use (auth cookie/header + seeded scan). Do not invent a new auth mechanism.

- [ ] **Step 7: Run route tests, verify they fail**

Run: `.venv/bin/pytest tests/api/test_scans.py -k "outcome or run_results" -v`
Expected: FAIL (route/param not defined).

- [ ] **Step 8: Implement route changes**

In `api/routes/scans.py`, update imports and the runs route, and add the new route:
```python
from typing import List, Optional
from db.models import ScanOutcome
from api.schemas import ScanResultResponse  # ensure imported

@router.get("/{scan_id}/runs", response_model=List[ScanRunResponse])
def list_runs(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    outcome: Optional[ScanOutcome] = Query(default=None),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_runs(db, scan_id, user.id, page=page, page_size=page_size, outcome=outcome)


@router.get("/{scan_id}/runs/{run_id}/results", response_model=List[ScanResultResponse])
def list_run_results(
    scan_id: int,
    run_id: int,
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_run_results(db, scan_id, run_id, user.id)
```

- [ ] **Step 9: Run the full backend suite**

Run: `.venv/bin/pytest tests/api/test_scans.py tests/services/test_history.py -v`
Expected: PASS (all). Then a broad sanity run: `.venv/bin/pytest tests/api tests/services -q`.

- [ ] **Step 10: Commit (on the worktree branch)**

```bash
git add api/schemas.py core/services/history.py api/routes/scans.py tests/services/test_history.py tests/api/test_scans.py
git commit -m "feat(api): per-run results endpoint, scan_run_id field, runs outcome filter"
```

---

## Task F1: Frontend plumbing — shared formatInterval, scan_run_id type, PageSizeSelect

**Files:**
- Modify: `frontend/src/lib/format.ts`, `frontend/src/components/scans/ScanForm.tsx`, `frontend/src/types/index.ts`
- Create: `frontend/src/components/ui/PageSizeSelect.tsx`
- Test: `frontend/src/lib/format.test.ts` (extend), `frontend/src/components/ui/PageSizeSelect.test.tsx`

**Interfaces:**
- Produces: `formatInterval(seconds: number): string` exported from `lib/format.ts`; `ScanResult.scan_run_id: number`; `PageSizeSelect({ value: number; onChange: (n: number) => void })`.

- [ ] **Step 1: Add a failing test for `formatInterval` in `lib/format.test.ts`**

Append:
```ts
import { formatInterval } from "./format";

describe("formatInterval", () => {
  it("formats minutes and hours", () => {
    expect(formatInterval(300)).toBe("5 min");
    expect(formatInterval(3600)).toBe("1 hour");
    expect(formatInterval(7200)).toBe("2 hours");
  });
});
```

- [ ] **Step 2: Run it, verify failure**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL (`formatInterval` not exported).

- [ ] **Step 3: Move `formatInterval` into `lib/format.ts`**

Add to `frontend/src/lib/format.ts`:
```ts
export function formatInterval(seconds: number): string {
  if (seconds % 3600 === 0) {
    const h = seconds / 3600;
    return `${h} hour${h > 1 ? "s" : ""}`;
  }
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} sec`;
}
```
Then in `frontend/src/components/scans/ScanForm.tsx`: delete the local `function formatInterval(...)` block and add to the imports:
```ts
import { formatInterval } from "../../lib/format";
```

- [ ] **Step 4: Run format test, verify pass**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: PASS.

- [ ] **Step 5: Add `scan_run_id` to the `ScanResult` type**

In `frontend/src/types/index.ts`, in `interface ScanResult`, add after `id`:
```ts
export interface ScanResult {
  id: number;
  scan_run_id: number;
  scan_id: number;
  // ... rest unchanged
}
```

- [ ] **Step 6: Create `PageSizeSelect` + failing test**

`frontend/src/components/ui/PageSizeSelect.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PageSizeSelect } from "./PageSizeSelect";

describe("PageSizeSelect", () => {
  it("renders options and emits a number on change", async () => {
    const onChange = vi.fn();
    render(<PageSizeSelect value={20} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(onChange).toHaveBeenCalledWith(50);
  });
});
```
Run it, verify FAIL (module missing). Then create `frontend/src/components/ui/PageSizeSelect.tsx`:
```tsx
import { Select } from "./Select";

const OPTIONS = [20, 50, 100].map((n) => ({ value: String(n), label: `${n} / page` }));

export function PageSizeSelect({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <Select
      value={String(value)}
      onChange={(v) => onChange(Number(v))}
      options={OPTIONS}
      className="w-32"
    />
  );
}
```

- [ ] **Step 7: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (full suite green; ScanForm tests still pass with the moved import).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts frontend/src/components/scans/ScanForm.tsx frontend/src/types/index.ts frontend/src/components/ui/PageSizeSelect.tsx frontend/src/components/ui/PageSizeSelect.test.tsx
git commit -m "feat(ui): shared formatInterval, scan_run_id type, PageSizeSelect"
```

---

## Task F2: Scan header context + Overview last-checked/last-found

**Files:**
- Modify: `frontend/src/components/scans/ScanDetailHeader.tsx`, `frontend/src/components/scans/OverviewTab.tsx`
- Test: `frontend/src/components/scans/ScanDetailHeader.test.tsx` (extend), `frontend/src/components/scans/OverviewTab.test.tsx` (new)

**Interfaces:**
- Consumes: `formatInterval` (F1), `useScanRuns`, `useScanResults`, `relativeTime`.

- [ ] **Step 1: Extend `ScanDetailHeader.test.tsx` with a failing assertion**

Add a test (mirror the existing file's QueryClient wrapper) using a scan fixture that has `campground_ids: [232447]`, `polling_interval: 600`, `notify_via_email: true`, `notify_via_telegram: false`:
```tsx
it("shows scan id, campground ids, polling interval and notifications", () => {
  wrap(<ScanDetailHeader scan={scan} onDeleted={vi.fn()} onEdit={vi.fn()} />);
  expect(screen.getByText(/#7/)).toBeInTheDocument();
  expect(screen.getByText(/campgrounds 232447/)).toBeInTheDocument();
  expect(screen.getByText(/10 min/)).toBeInTheDocument();
  expect(screen.getByText(/Email/)).toBeInTheDocument();
});
```
Run it, verify FAIL.

- [ ] **Step 2: Implement header changes in `ScanDetailHeader.tsx`**

Add `import { formatInterval } from "../../lib/format";`. Update the meta list and add a chips row. Replace the `meta` const and the `<div>` block:
```tsx
  const meta = [
    `#${scan.id}`,
    scan.provider,
    scan.rec_area_ids?.length ? `areas ${scan.rec_area_ids.join(", ")}` : null,
    scan.campground_ids?.length ? `campgrounds ${scan.campground_ids.join(", ")}` : null,
    `${scan.nights} night${scan.nights === 1 ? "" : "s"}`,
  ].filter(Boolean).join(" · ");

  const notifs = [
    scan.notify_via_email ? "Email" : null,
    scan.notify_via_telegram ? "Telegram" : null,
    scan.notify_on_new_only ? "New only" : null,
  ].filter(Boolean) as string[];
```
And in the JSX left block, after the `<p className="mt-1 ...">{meta}</p>` line, add:
```tsx
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-sand-100 px-2 py-0.5 text-xs text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
            every {formatInterval(scan.polling_interval)}
          </span>
          {notifs.map((n) => (
            <span key={n} className="rounded-full bg-forest-50 px-2 py-0.5 text-xs text-forest-700 dark:bg-[#1b2a1f] dark:text-forest-400">
              {n}
            </span>
          ))}
        </div>
```

- [ ] **Step 3: Run header test, verify pass**

Run: `cd frontend && npx vitest run src/components/scans/ScanDetailHeader.test.tsx`
Expected: PASS.

- [ ] **Step 4: Write a failing `OverviewTab.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { OverviewTab } from "./OverviewTab";
import type { Scan } from "../../types";

const scan = { id: 7, search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }] } as unknown as Scan;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OverviewTab", () => {
  it("shows last checked and last new site found", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({ sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80 })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([{ id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null }])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([{ id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "F", site_name: "S", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z", cart_added: false, notified: true }])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Last checked/i)).toBeInTheDocument());
    expect(screen.getByText(/Last new site found/i)).toBeInTheDocument();
  });
});
```
Run it, verify FAIL.

- [ ] **Step 5: Implement Overview changes in `OverviewTab.tsx`**

Add imports and a derived line. Replace the component body:
```tsx
import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { useScanResults } from "../../hooks/useResults";
import { relativeTime } from "../../lib/format";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { SearchWindowsList } from "./SearchWindowsList";
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
      <SearchWindowsList windows={scan.search_windows} />
    </div>
  );
}
```

- [ ] **Step 6: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (full suite).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/scans/ScanDetailHeader.tsx frontend/src/components/scans/ScanDetailHeader.test.tsx frontend/src/components/scans/OverviewTab.tsx frontend/src/components/scans/OverviewTab.test.tsx
git commit -m "feat(ui): scan header context + Overview last-checked/last-found"
```

> **CHECKPOINT after F2 + backend merge:** merge the Task B worktree branch into `spec/web-ui-design` before starting F3/F4 (they consume `scan_run_id` and the new endpoints). Verify the backend suite is green post-merge.

---

## Task F3: Results tab — page size + richer cards

**Files:**
- Modify: `frontend/src/hooks/useResults.ts`, `frontend/src/hooks/queryKeys.ts`, `frontend/src/components/scans/ResultsTab.tsx`, `frontend/src/components/scans/ResultCard.tsx`
- Test: `frontend/src/components/scans/ResultsTab.test.tsx` (extend)

**Interfaces:**
- Consumes: `PageSizeSelect` (F1), `scan_run_id`/`notified`/`first_seen_at` on `ScanResult`, `relativeTime`.
- Produces: `useScanResults(scanId, page, pageSize?)`.

- [ ] **Step 1: Extend `ResultsTab.test.tsx` with failing assertions**

Add to the existing result fixture `scan_run_id: 9, notified: true` (and ensure `first_seen_at` is set). Add a test:
```tsx
it("renders campsite id, first-seen, notified badge and run link", async () => {
  server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([result])));
  wrap(<ResultsTab scanId={7} />);
  await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
  expect(screen.getByText(/#A1/)).toBeInTheDocument();       // campsite_id
  expect(screen.getByText(/notified/i)).toBeInTheDocument();  // badge
  expect(screen.getByText(/run #9/)).toBeInTheDocument();     // discovering run
});
```
(Use the existing `result` fixture's `campsite_id: "A1"`; adjust the regex to its value.) Run it, verify FAIL.

- [ ] **Step 2: Add `pageSize` to `useResults.ts` + queryKey**

`frontend/src/hooks/queryKeys.ts` — change the `results` key:
```ts
  results: (id: number, page: number, pageSize: number) =>
    ["scans", id, "results", { page, pageSize }] as const,
```
`frontend/src/hooks/useResults.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanResults(scanId: number | null, page: number, pageSize: number = PAGE_SIZE) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page, pageSize) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, pageSize),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
```

- [ ] **Step 3: Add page-size selector to `ResultsTab.tsx`**

```tsx
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
```

- [ ] **Step 4: Enrich `ResultCard.tsx`**

```tsx
import { Badge } from "../ui/Badge";
import { dateRange, relativeTime } from "../../lib/format";
import type { ScanResult } from "../../types";

export function ResultCard({ result }: { result: ScanResult }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="font-medium text-stone-900 dark:text-[#EEE]">{result.site_name}</p>
          <span className="rounded bg-sand-100 px-1.5 py-0.5 font-mono text-xs text-stone-500 dark:bg-[#222] dark:text-[#888]">
            #{result.campsite_id}
          </span>
        </div>
        <p className="text-sm text-stone-500 dark:text-[#888]">{result.facility_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          {dateRange(result.booking_date, result.booking_end_date)} · {result.campsite_type}
        </p>
        <p className="text-xs text-stone-400">
          First seen {relativeTime(result.first_seen_at)} · run #{result.scan_run_id}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        <div className="flex gap-1.5">
          {result.cart_added ? <Badge tone="accent">In cart</Badge> : <Badge tone="neutral">Not in cart</Badge>}
          {result.notified && <Badge tone="info">Notified</Badge>}
        </div>
        <a href={result.booking_url} target="_blank" rel="noopener noreferrer"
          className="text-sm font-medium text-forest-700 hover:underline dark:text-forest-400">
          Book →
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (full suite; existing ResultsTab tests still pass).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useResults.ts frontend/src/hooks/queryKeys.ts frontend/src/components/scans/ResultsTab.tsx frontend/src/components/scans/ResultCard.tsx frontend/src/components/scans/ResultsTab.test.tsx
git commit -m "feat(ui): results page-size selector + richer result cards"
```

---

## Task F4: Run History — page size, found-only filter, expandable per-run sites

**Files:**
- Modify: `frontend/src/api/runs.ts`, `frontend/src/hooks/useRuns.ts`, `frontend/src/hooks/queryKeys.ts`, `frontend/src/components/scans/RunHistoryTab.tsx`, `frontend/src/components/scans/RunRow.tsx`
- Test: `frontend/src/components/scans/RunHistoryTab.test.tsx` (extend)

**Interfaces:**
- Consumes: per-run results endpoint + `outcome` filter (Task B), `PageSizeSelect`, `Toggle`, `dateRange`.
- Produces: `useScanRuns(scanId, page, pageSize?, outcome?)`, `useRunResults(scanId, runId, enabled)`, `runs.runResults(scanId, runId)`.

- [ ] **Step 1: Extend `api/runs.ts`**

```ts
import { fetchApi } from "./client";
import type { ScanRun, ScanResult } from "../types";

export const runs = {
  list: (scanId: number, page = 1, pageSize = 20, outcome?: string) =>
    fetchApi<ScanRun[]>(
      `/scans/${scanId}/runs?page=${page}&page_size=${pageSize}${outcome ? `&outcome=${outcome}` : ""}`,
    ),
  runResults: (scanId: number, runId: number) =>
    fetchApi<ScanResult[]>(`/scans/${scanId}/runs/${runId}/results`),
};
```

- [ ] **Step 2: Extend `queryKeys.ts` + `useRuns.ts`**

`queryKeys.ts` — change the `runs` key and add `runResults`:
```ts
  runs: (id: number, page: number, pageSize: number, outcome?: string) =>
    ["scans", id, "runs", { page, pageSize, outcome: outcome ?? null }] as const,
  runResults: (id: number, runId: number) =>
    ["scans", id, "runs", runId, "results"] as const,
```
`useRuns.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { runs } from "../api/runs";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanRuns(scanId: number | null, page: number, pageSize: number = PAGE_SIZE, outcome?: string) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page, pageSize, outcome) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, pageSize, outcome),
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
(`useScanRuns(scan.id, 1)` callers in OverviewTab continue to work via defaults.)

- [ ] **Step 3: Add failing tests to `RunHistoryTab.test.tsx`**

```tsx
it("expands a run to show its discovered sites", async () => {
  server.use(
    http.get("/api/v1/scans/7/runs", () => HttpResponse.json([
      { id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null },
    ])),
    http.get("/api/v1/scans/7/runs/9/results", () => HttpResponse.json([
      { id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "Upper Pines", site_name: "Site 42", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "https://x", first_seen_at: "2026-06-30T11:00:00Z", cart_added: false, notified: true },
    ])),
  );
  wrap(<RunHistoryTab scanId={7} />);
  await waitFor(() => expect(screen.getByText(/Success/)).toBeInTheDocument());
  await userEvent.click(screen.getByText(/Success/));
  await waitFor(() => expect(screen.getByText(/Site 42/)).toBeInTheDocument());
  expect(screen.getByText(/first discovered in this run/i)).toBeInTheDocument();
});
```
Add `import userEvent from "@testing-library/user-event";` if not present. Run it, verify FAIL.

- [ ] **Step 4: Rewrite `RunRow.tsx` as expandable**

```tsx
import { useState } from "react";
import { StatusDot } from "../ui/StatusDot";
import { Spinner } from "../ui/Spinner";
import { relativeTime, duration, dateRange } from "../../lib/format";
import { outcomeLabel, outcomeTone } from "./RunHealthBar";
import { useRunResults } from "../../hooks/useRuns";
import type { ScanRun } from "../../types";

export function RunRow({ scanId, run }: { scanId: number; run: ScanRun }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = run.sites_found > 0;
  const { data: sites, isLoading } = useRunResults(scanId, run.id, expanded);

  return (
    <div className="border-b border-sand-200 py-3 dark:border-[#222]">
      <div className="flex items-center justify-between">
        <button
          type="button"
          disabled={!canExpand}
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-3 text-left disabled:cursor-default"
        >
          {canExpand && <span className="w-3 text-stone-400">{expanded ? "▾" : "▸"}</span>}
          <StatusDot tone={outcomeTone(run.outcome)} />
          <span className="text-sm font-medium text-stone-800 dark:text-[#EEE]">{outcomeLabel(run.outcome)}</span>
          <span className="text-sm text-stone-400" title={new Date(run.started_at).toLocaleString()}>
            {relativeTime(run.started_at)}
          </span>
        </button>
        <div className="flex gap-4 text-sm text-stone-500 dark:text-[#888]">
          <span>{run.sites_found} sites</span>
          <span>{duration(run.started_at, run.finished_at)}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 pl-6">
          {isLoading ? (
            <Spinner className="h-4 w-4" />
          ) : sites && sites.length > 0 ? (
            <>
              <ul className="space-y-1">
                {sites.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-stone-700 dark:text-[#CCC]">
                      {s.site_name} · {s.facility_name} · {dateRange(s.booking_date, s.booking_end_date)}
                    </span>
                    <a href={s.booking_url} target="_blank" rel="noopener noreferrer"
                      className="shrink-0 text-forest-700 hover:underline dark:text-forest-400">Book →</a>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-stone-400">
                Sites first discovered in this run. Re-found sites aren't individually recorded (see ADR 007).
              </p>
            </>
          ) : (
            <p className="text-xs text-stone-400">{run.sites_found} sites found (all previously seen).</p>
          )}
        </div>
      )}

      {run.error_message && (
        <details className="mt-2 pl-6 text-sm text-[#DC2626]">
          <summary className="cursor-pointer select-none">Show details</summary>
          <pre className="mt-1 whitespace-pre-wrap break-words">{run.error_message}</pre>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Update `RunHistoryTab.tsx` (page size + found-only + pass scanId)**

```tsx
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
```

- [ ] **Step 6: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (full suite; existing RunHistory tests updated for the new `scanId` prop / toolbar still pass).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/runs.ts frontend/src/hooks/useRuns.ts frontend/src/hooks/queryKeys.ts frontend/src/components/scans/RunHistoryTab.tsx frontend/src/components/scans/RunRow.tsx frontend/src/components/scans/RunHistoryTab.test.tsx
git commit -m "feat(ui): run history page-size, found-only filter, expandable per-run sites"
```

---

## Self-Review

- **Spec coverage:** B1 scan_run_id (Task B Step 1 + F1 Step 5 type), B2 per-run endpoint (Task B), B3 outcome filter (Task B), Run History expand + filter + page size (F4), denser Results + page size (F3), header context (F2), Overview last-checked/found (F2), tooltips/limitation copy (F4 RunRow). Availability badges explicitly deferred (ADR 007). All covered.
- **Type consistency:** `useScanResults(scanId, page, pageSize?)` and `useScanRuns(scanId, page, pageSize?, outcome?)` keep older positional calls working via defaults (OverviewTab `useScanRuns(scan.id, 1)`, `useScanResults(scan.id, 1)`). `queryKeys.results`/`runs` signatures updated in the same task as their hook. `RunRow` now requires `scanId` — updated at its only call site (RunHistoryTab). `runs.runResults` ↔ `useRunResults` ↔ `queryKeys.runResults` names align. `formatInterval` single definition in `lib/format.ts`.
- **Placeholder scan:** backend test fixtures intentionally reference "mirror the existing test fixtures" because the exact fixture names live in the test files the implementer will read; all implementation code is complete and literal.
- **DRY:** `formatInterval` and `PageSizeSelect` are single-sourced; the per-run site line reuses `dateRange`; tooltip copy points at ADR 007.
