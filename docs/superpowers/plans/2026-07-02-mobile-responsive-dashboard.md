# Mobile Responsive Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the desktop three-panel dashboard to a single navigable panel on small screens (list ➝ tap ➝ detail with a back affordance) and turn the icon sidebar into a hamburger-toggled slide-in drawer.

**Architecture:** Pure Tailwind breakpoint (`md`, 768px) visibility toggling driven by the dashboard's existing local state (`selectedScanId`, `wizardOpen`) plus one new `sidebarOpen` flag. A new `md:hidden` `MobileTopBar` provides the hamburger (list view) / back button (detail view). No routing, API, hook, or type changes.

**Tech Stack:** React 18 + TypeScript, Tailwind CSS 3.4, React Router v6, TanStack Query, Vitest + Testing Library + MSW (jsdom).

Spec: `docs/superpowers/specs/2026-07-02-mobile-responsive-dashboard-design.md`

## Global Constraints

- Breakpoint is Tailwind **`md` (768px)**: mobile `< md`, desktop `≥ md`. Copy the existing idiom (`hidden md:flex`, `grid-cols-2 md:grid-cols-4`).
- jsdom does **not** evaluate media queries — test behaviour via **state-driven conditional rendering** and class-string assertions, never computed layout.
- All external I/O is already mocked via MSW; add no new mocks beyond component/context mocks. Follow `docs/agents/testing.md`.
- Run commands from `frontend/`. Test: `npm test`. Type-check: `npm run lint`.
- The existing 69 tests must stay green; desktop rendering must not change.
- Use the `cn()` helper (`src/lib/cn.ts`) for conditional class composition; match existing dark-mode class patterns (`dark:bg-[#1A1A1A]`, `dark:border-[#222]`).

---

### Task 1: MobileTopBar component

A `md:hidden` contextual top bar. Left control is conditionally rendered: **back button** when `onBack` is provided, otherwise a **hamburger**. Optional **+** on the right.

**Files:**
- Create: `frontend/src/components/layout/MobileTopBar.tsx`
- Test: `frontend/src/components/layout/MobileTopBar.test.tsx`

**Interfaces:**
- Produces: `MobileTopBar(props: { title: string; onOpenSidebar?: () => void; onBack?: () => void; onNewScan?: () => void }): JSX.Element`
  - When `onBack` is set → renders a button `aria-label="Back to scans"` with text `← {title}`.
  - Else when `onOpenSidebar` is set → renders a button `aria-label="Open menu"` (hamburger ☰) followed by `{title}`.
  - When `onNewScan` is set → renders a right-aligned button `aria-label="New scan"` with text `+`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/layout/MobileTopBar.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MobileTopBar } from "./MobileTopBar";

describe("MobileTopBar", () => {
  it("list mode: shows hamburger + new-scan and fires their handlers", async () => {
    const onOpenSidebar = vi.fn();
    const onNewScan = vi.fn();
    render(<MobileTopBar title="Scans" onOpenSidebar={onOpenSidebar} onNewScan={onNewScan} />);

    expect(screen.queryByRole("button", { name: /back to scans/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /open menu/i }));
    expect(onOpenSidebar).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onNewScan).toHaveBeenCalledOnce();
  });

  it("detail mode: shows back button (no hamburger) and fires onBack", async () => {
    const onBack = vi.fn();
    render(<MobileTopBar title="Scans" onBack={onBack} />);

    expect(screen.queryByRole("button", { name: /open menu/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /back to scans/i }));
    expect(onBack).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- MobileTopBar`
Expected: FAIL — `Failed to resolve import "./MobileTopBar"`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/layout/MobileTopBar.tsx
interface Props {
  title: string;
  onOpenSidebar?: () => void;
  onBack?: () => void;
  onNewScan?: () => void;
}

export function MobileTopBar({ title, onOpenSidebar, onBack, onNewScan }: Props) {
  return (
    <header className="flex h-12 items-center justify-between border-b border-sand-200 bg-white px-3 dark:border-[#222] dark:bg-[#1A1A1A] md:hidden">
      <div className="flex items-center gap-2">
        {onBack ? (
          <button
            aria-label="Back to scans"
            onClick={onBack}
            className="flex items-center gap-1 rounded-md px-1 py-1 text-sm font-medium text-stone-700 hover:bg-sand-100 dark:text-[#CCC] dark:hover:bg-[#222]"
          >
            <span aria-hidden>←</span> {title}
          </button>
        ) : (
          <>
            {onOpenSidebar && (
              <button
                aria-label="Open menu"
                onClick={onOpenSidebar}
                className="flex h-8 w-8 items-center justify-center rounded-md text-lg hover:bg-sand-100 dark:hover:bg-[#222]"
              >
                <span aria-hidden>☰</span>
              </button>
            )}
            <h1 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">{title}</h1>
          </>
        )}
      </div>
      {onNewScan && (
        <button
          aria-label="New scan"
          onClick={onNewScan}
          className="flex h-7 w-7 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700"
        >
          +
        </button>
      )}
    </header>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- MobileTopBar`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/layout/MobileTopBar.tsx src/components/layout/MobileTopBar.test.tsx
git commit -m "feat(ui): add MobileTopBar contextual mobile header (#21)"
```

---

### Task 2: IconSidebar drawer mode

Make `IconSidebar` render as a left slide-in drawer on mobile while staying a static 52px sidebar on desktop. Closes on backdrop click, Escape, or nav-item selection.

**Files:**
- Modify: `frontend/src/components/layout/IconSidebar.tsx`
- Test: `frontend/src/components/layout/IconSidebar.test.tsx` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: `IconSidebar(props: { onOpenScans: () => void; open?: boolean; onClose?: () => void })`. New props are optional (existing callers keep compiling). When `open` and `onClose` are set, a backdrop with `data-testid="sidebar-backdrop"` renders; backdrop click, `Escape`, and any nav-link click call `onClose`.

- [ ] **Step 1: Write the failing test** (append these to the existing `describe("IconSidebar")` block; keep the existing theme test)

```tsx
// add to frontend/src/components/layout/IconSidebar.test.tsx
  it("closes on backdrop click when open", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape when open", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes when a nav item is selected", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.click(screen.getByRole("link", { name: /settings/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- IconSidebar`
Expected: FAIL — no `sidebar-backdrop` testid; `onClose` not called on Escape / nav click.

- [ ] **Step 3: Write minimal implementation**

Replace the file with:

```tsx
// frontend/src/components/layout/IconSidebar.tsx
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "../../contexts/ThemeContext";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/cn";

export function IconSidebar({ onOpenScans, open = false, onClose }: {
  onOpenScans: () => void;
  open?: boolean;
  onClose?: () => void;
}) {
  const { theme, toggle } = useTheme();
  const { logout, user } = useAuth();
  const { pathname } = useLocation();

  useEffect(() => {
    if (!open || !onClose) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const closeDrawer = () => onClose?.();
  const iconBtn = "flex h-10 w-10 items-center justify-center rounded-lg text-xl transition-colors";

  return (
    <>
      {open && (
        <div
          data-testid="sidebar-backdrop"
          aria-hidden
          onClick={closeDrawer}
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
        />
      )}
      <nav
        className={cn(
          "flex w-[52px] flex-col items-center justify-between border-r border-sand-200 bg-white py-3 dark:border-[#222] dark:bg-[#1A1A1A]",
          "fixed left-0 top-0 z-50 h-full transition-transform md:static md:z-auto md:h-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex flex-col items-center gap-2">
          <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-forest-600 text-white" aria-hidden>⛺</div>
          <Link to="/" onClick={() => { onOpenScans(); closeDrawer(); }} aria-label="Scans"
            className={cn(iconBtn, pathname === "/" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <span aria-hidden>⛺</span>
          </Link>
          <Link to="/settings" onClick={closeDrawer} aria-label="Settings"
            className={cn(iconBtn, pathname === "/settings" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <span aria-hidden>⚙️</span>
          </Link>
        </div>
        <div className="flex flex-col items-center gap-2">
          <button aria-label="Toggle theme" onClick={toggle}
            className={cn(iconBtn, "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <span aria-hidden>{theme === "dark" ? "☀️" : "🌙"}</span>
          </button>
          <button aria-label={`Log out ${user?.email ?? ""}`} onClick={() => logout()}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-forest-600 text-sm font-semibold text-white">
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </button>
        </div>
      </nav>
    </>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- IconSidebar`
Expected: PASS (4 tests — original theme test + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/components/layout/IconSidebar.tsx src/components/layout/IconSidebar.test.tsx
git commit -m "feat(ui): IconSidebar drawer mode for mobile (#21)"
```

---

### Task 3: Tabs horizontal scroll

Let the 4 detail tabs scroll horizontally instead of overflowing on narrow screens.

**Files:**
- Modify: `frontend/src/components/ui/Tabs.tsx`
- Test: `frontend/src/components/ui/Tabs.test.tsx` (create)

**Interfaces:**
- No API change to `Tabs`. Only class additions: `tablist` gains `overflow-x-auto`; each tab button gains `whitespace-nowrap shrink-0`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/ui/Tabs.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tabs } from "./Tabs";

describe("Tabs", () => {
  const tabs = [{ id: "a", label: "Alpha" }, { id: "b", label: "Beta" }];

  it("makes the tablist horizontally scrollable and tabs non-wrapping", () => {
    render(<Tabs tabs={tabs} active="a" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist").className).toContain("overflow-x-auto");
    expect(screen.getByRole("tab", { name: "Alpha" }).className).toContain("whitespace-nowrap");
    expect(screen.getByRole("tab", { name: "Alpha" }).className).toContain("shrink-0");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ui/Tabs`
Expected: FAIL — `overflow-x-auto` / `whitespace-nowrap` not present.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/ui/Tabs.tsx`, change the tablist `div` className to add `overflow-x-auto`:

```tsx
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-sand-200 dark:border-[#222]">
```

and add `whitespace-nowrap shrink-0` to the button's first className string argument:

```tsx
          className={cn(
            "-mb-px shrink-0 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors",
            active === t.id
              ? "border-forest-600 text-forest-700 dark:text-forest-400"
              : "border-transparent text-stone-500 hover:text-stone-800 dark:text-[#888] dark:hover:text-[#CCC]"
          )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- ui/Tabs`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Tabs.tsx src/components/ui/Tabs.test.tsx
git commit -m "feat(ui): scrollable tab bar on narrow screens (#21)"
```

---

### Task 4: Detail-panel responsive chrome

Stack the detail header on mobile and tighten detail padding on small screens.

**Files:**
- Modify: `frontend/src/components/scans/ScanDetailHeader.tsx`
- Modify: `frontend/src/components/scans/ScanDetailPanel.tsx`
- Test: `frontend/src/components/scans/ScanDetailHeader.test.tsx` (extend)

**Interfaces:**
- No prop changes. `ScanDetailHeader`'s root `<header>` becomes `flex-col gap-3 px-4 py-4 md:flex-row md:items-start md:justify-between md:px-6`. `ScanDetailPanel`'s tab-row and body padding become `px-4 md:px-6`.

- [ ] **Step 1: Write the failing test** (append to the existing `describe("ScanDetailHeader")` block)

```tsx
// add to frontend/src/components/scans/ScanDetailHeader.test.tsx
  it("stacks vertically on mobile and switches to a row at md", () => {
    const { container } = wrap(<ScanDetailHeader scan={scan} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    const header = container.querySelector("header")!;
    expect(header.className).toContain("flex-col");
    expect(header.className).toContain("md:flex-row");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ScanDetailHeader`
Expected: FAIL — `flex-col` not present in header className.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/scans/ScanDetailHeader.tsx`, change the root `<header>` className:

```tsx
    <header className="flex flex-col gap-3 border-b border-sand-200 px-4 py-4 dark:border-[#222] md:flex-row md:items-start md:justify-between md:px-6">
```

In `frontend/src/components/scans/ScanDetailPanel.tsx`, change the two padded containers from `px-6` to responsive padding:

```tsx
      <div className="px-4 md:px-6">
        <Tabs tabs={TABS} active={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6" key={scan.id}>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- ScanDetailHeader ScanDetailPanel`
Expected: PASS (new stacking test + all existing ScanDetailHeader and ScanDetailPanel tests still green).

- [ ] **Step 5: Commit**

```bash
git add src/components/scans/ScanDetailHeader.tsx src/components/scans/ScanDetailPanel.tsx src/components/scans/ScanDetailHeader.test.tsx
git commit -m "feat(ui): responsive detail header + padding on mobile (#21)"
```

---

### Task 5: Wizard responsive layout

Hide the wizard's vertical step sidebar on mobile and show a compact horizontal step indicator instead; tighten padding.

**Files:**
- Modify: `frontend/src/components/wizard/ScanWizardPanel.tsx`
- Test: `frontend/src/components/wizard/ScanWizardPanel.test.tsx` (extend)

**Interfaces:**
- No prop changes. The `w-56` step-indicator sidebar becomes `hidden md:block`. A new `md:hidden` line reads `Step {step+1} of {STEPS.length} · {STEPS[step]}` and updates as the user advances.

- [ ] **Step 1: Write the failing test** (append to the existing `describe("ScanWizardPanel")` block)

```tsx
// add to frontend/src/components/wizard/ScanWizardPanel.test.tsx
  it("shows a compact mobile step indicator that advances", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText(/step 1 of 3 · provider & sites/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/recreation area ids/i), "2991");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/step 2 of 3 · dates & filters/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ScanWizardPanel`
Expected: FAIL — "step 1 of 3" text not found.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/wizard/ScanWizardPanel.tsx`:

Add `hidden md:block` to the step-indicator sidebar div:

```tsx
      <div className="hidden w-56 border-r border-sand-200 p-6 dark:border-[#222] md:block">
        <h2 className="mb-6 text-sm font-semibold text-stone-800 dark:text-[#EEE]">New Scan</h2>
        <VerticalStepIndicator steps={STEPS} current={step} />
      </div>
```

Change the content column padding to `p-4 md:p-6` and add the mobile indicator as its first child:

```tsx
      <div className="flex flex-1 flex-col overflow-y-auto p-4 md:p-6">
        <p className="mb-4 text-sm font-medium text-stone-600 dark:text-[#AAA] md:hidden">
          Step {step + 1} of {STEPS.length} · {STEPS[step]}
        </p>
        <div className="max-w-xl flex-1">
```

(Leave the rest of the content column — the `step === n` fields, error, and nav buttons — unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- ScanWizardPanel`
Expected: PASS (existing walk-through test + new mobile-indicator test).

- [ ] **Step 5: Commit**

```bash
git add src/components/wizard/ScanWizardPanel.tsx src/components/wizard/ScanWizardPanel.test.tsx
git commit -m "feat(ui): responsive wizard step indicator on mobile (#21)"
```

---

### Task 6: DashboardLayout single-panel collapse

Wire the drawer sidebar, the `MobileTopBar`, and the list⇄detail collapse together. This is the integrating task.

**Files:**
- Modify: `frontend/src/components/layout/DashboardLayout.tsx`
- Modify: `frontend/src/components/layout/ScanListPanel.tsx`
- Test: `frontend/src/components/layout/DashboardLayout.test.tsx` (create)

**Interfaces:**
- Consumes: `MobileTopBar` (Task 1); `IconSidebar` `open`/`onClose` (Task 2).
- `ScanListPanel`'s root `<aside>` becomes `w-full md:w-60`; its internal `<header>` becomes `hidden md:flex` (title + `+` move to `MobileTopBar` on mobile).
- `DashboardLayout` derives `showingDetail = wizardOpen || selectedScanId != null` and toggles list/detail visibility with `hidden md:flex` / `flex`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/layout/DashboardLayout.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("./IconSidebar", () => ({ IconSidebar: () => <div data-testid="sidebar" /> }));
vi.mock("./ScanListPanel", () => ({
  ScanListPanel: ({ onSelect, onNewScan }: { onSelect: (id: number) => void; onNewScan: () => void }) => (
    <div>
      <button onClick={() => onSelect(7)}>select-scan</button>
      <button onClick={onNewScan}>list-plus</button>
    </div>
  ),
}));
vi.mock("../scans/ScanDetailPanel", () => ({ ScanDetailPanel: () => <div>detail-panel</div> }));
vi.mock("../scans/WelcomePanel", () => ({ WelcomePanel: () => <div>welcome-panel</div> }));
vi.mock("../wizard/ScanWizardPanel", () => ({ ScanWizardPanel: () => <div>wizard-panel</div> }));

import { DashboardLayout } from "./DashboardLayout";

const renderLayout = () => render(<MemoryRouter><DashboardLayout /></MemoryRouter>);

describe("DashboardLayout mobile collapse", () => {
  it("shows the hamburger initially and swaps to back after selecting a scan", async () => {
    renderLayout();
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /back to scans/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "select-scan" }));
    expect(screen.getByRole("button", { name: /back to scans/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open menu/i })).not.toBeInTheDocument();
  });

  it("returns to the list when back is clicked", async () => {
    renderLayout();
    await userEvent.click(screen.getByRole("button", { name: "select-scan" }));
    await userEvent.click(screen.getByRole("button", { name: /back to scans/i }));
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
  });

  it("opens the wizard from the top-bar new-scan button", async () => {
    renderLayout();
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(screen.getByText("wizard-panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to scans/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- DashboardLayout`
Expected: FAIL — no `open menu` button (MobileTopBar not yet rendered by DashboardLayout).

- [ ] **Step 3: Write minimal implementation**

Replace `frontend/src/components/layout/DashboardLayout.tsx`:

```tsx
import { useState } from "react";
import { IconSidebar } from "./IconSidebar";
import { MobileTopBar } from "./MobileTopBar";
import { ScanListPanel } from "./ScanListPanel";
import { ScanDetailPanel } from "../scans/ScanDetailPanel";
import { WelcomePanel } from "../scans/WelcomePanel";
import { ScanWizardPanel } from "../wizard/ScanWizardPanel";
import { cn } from "../../lib/cn";

export function DashboardLayout() {
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const showingDetail = wizardOpen || selectedScanId != null;
  const selectScan = (id: number) => { setWizardOpen(false); setSelectedScanId(id); };
  const back = () => { setWizardOpen(false); setSelectedScanId(null); };

  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar
        onOpenScans={() => setWizardOpen(false)}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar
          title="Scans"
          {...(showingDetail
            ? { onBack: back }
            : { onOpenSidebar: () => setSidebarOpen(true), onNewScan: () => { setSelectedScanId(null); setWizardOpen(true); } })}
        />
        <div className="flex flex-1 overflow-hidden">
          <div className={cn("min-w-0", showingDetail ? "hidden md:flex" : "flex w-full md:w-auto")}>
            <ScanListPanel
              selectedScanId={selectedScanId}
              onSelect={selectScan}
              onNewScan={() => { setSelectedScanId(null); setWizardOpen(true); }}
            />
          </div>
          <div className={cn("flex-1 overflow-hidden", showingDetail ? "flex" : "hidden md:flex")}>
            {wizardOpen ? (
              <ScanWizardPanel
                onClose={back}
                onCreated={(id) => { setWizardOpen(false); setSelectedScanId(id); }}
              />
            ) : selectedScanId != null ? (
              <ScanDetailPanel scanId={selectedScanId} onDeleted={() => setSelectedScanId(null)} />
            ) : (
              <WelcomePanel />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

Then update `frontend/src/components/layout/ScanListPanel.tsx` — make the aside full-width on mobile and hide its header on mobile:

```tsx
    <aside className="flex w-full flex-col border-r border-sand-200 bg-white dark:border-[#222] dark:bg-[#1A1A1A] md:w-60">
      <header className="hidden items-center justify-between border-b border-sand-200 px-3 py-3 dark:border-[#222] md:flex">
```

(Leave the rest of `ScanListPanel` unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- DashboardLayout ScanListPanel`
Expected: PASS (3 new DashboardLayout tests + existing ScanListPanel tests still green — the `new scan` header button is `md:hidden` in the DOM but still present, so `getByRole` finds it).

- [ ] **Step 5: Commit**

```bash
git add src/components/layout/DashboardLayout.tsx src/components/layout/ScanListPanel.tsx src/components/layout/DashboardLayout.test.tsx
git commit -m "feat(ui): single-panel dashboard collapse on mobile (#21)"
```

---

### Task 7: Settings page drawer + mobile header

Give `/settings` the same drawer sidebar and a hamburger header on mobile.

**Files:**
- Modify: `frontend/src/components/settings/SettingsPage.tsx`
- Test: `frontend/src/components/settings/SettingsPage.test.tsx` (create)

**Interfaces:**
- Consumes: `IconSidebar` `open`/`onClose` (Task 2); `MobileTopBar` (Task 1, list-style usage: `title="Settings"`, `onOpenSidebar`, no `onNewScan`).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/SettingsPage.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../layout/IconSidebar", () => ({ IconSidebar: () => <div data-testid="sidebar" /> }));
vi.mock("./ProfileForm", () => ({ ProfileForm: () => <div>profile-form</div> }));

import { SettingsPage } from "./SettingsPage";

describe("SettingsPage", () => {
  it("renders a mobile header with a hamburger and the Settings title", () => {
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("profile-form")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- settings/SettingsPage`
Expected: FAIL — no `open menu` button.

- [ ] **Step 3: Write minimal implementation**

Replace `frontend/src/components/settings/SettingsPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { IconSidebar } from "../layout/IconSidebar";
import { MobileTopBar } from "../layout/MobileTopBar";
import { ProfileForm } from "./ProfileForm";

export function SettingsPage() {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar
        onOpenScans={() => navigate("/")}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar title="Settings" onOpenSidebar={() => setSidebarOpen(true)} />
        <div className="flex flex-1 items-start justify-center overflow-y-auto p-6 md:p-10">
          <ProfileForm />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- settings/SettingsPage`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/components/settings/SettingsPage.tsx src/components/settings/SettingsPage.test.tsx
git commit -m "feat(ui): drawer sidebar + mobile header on settings page (#21)"
```

---

### Task 8: Full-suite verification

Confirm the whole suite and the type-checker pass with all changes integrated.

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `npm test`
Expected: PASS — all prior tests (69) plus the new ones (MobileTopBar 2, IconSidebar +3, Tabs 1, ScanDetailHeader +1, ScanWizardPanel +1, DashboardLayout 3, SettingsPage 1). 0 failures.

- [ ] **Step 2: Run the type-checker**

Run: `npm run lint`
Expected: no errors (exit 0).

- [ ] **Step 3: Commit (only if any fix was needed)**

```bash
git add -A
git commit -m "chore(ui): verify mobile responsive suite green (#21)"
```

---

## Self-Review

**Spec coverage:**
- Breakpoint `md` → Global Constraints + every task. ✓
- `showingDetail` CSS collapse (no routing) → Task 6. ✓
- Hamburger slide-in drawer (backdrop / Esc / nav-close) → Task 2. ✓
- `MobileTopBar` contextual (list hamburger+＋ / detail back) → Task 1 + wired in Task 6. ✓
- `ScanListPanel` `w-full md:w-60` + header `hidden md:flex` → Task 6. ✓
- `ScanDetailHeader` stacking + `Tabs` scroll + detail padding → Tasks 3, 4. ✓
- `ScanWizardPanel` step indicator + padding → Task 5. ✓
- `SettingsPage` drawer + mobile header → Task 7. ✓
- `NaturePanel` — spec listed `hidden md:flex`, but the code **already** has it; no task needed (verified in `NaturePanel.tsx`). Noted here so the omission is intentional, not a gap.
- Testing approach (state-driven, jsdom-safe, no new I/O mocks) → Global Constraints + every task; full-suite gate → Task 8. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N"; every code step shows complete code. ✓

**Type consistency:** `MobileTopBar` prop names (`title`, `onOpenSidebar`, `onBack`, `onNewScan`) identical in Task 1, 6, 7. `IconSidebar` props (`onOpenScans`, `open`, `onClose`) identical in Task 2, 6, 7. `showingDetail`/`back` names consistent within Task 6. Aria-labels (`Open menu`, `Back to scans`, `New scan`) consistent across producing and consuming tasks. ✓
