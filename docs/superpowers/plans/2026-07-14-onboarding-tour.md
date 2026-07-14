# Onboarding Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two short, dismissible, replayable driver.js walkthroughs — one on the "Welcome to CampBuddy" empty state (sidebar orientation), one on the New Scan wizard's Provider & Sites step (provider/search/ID guidance) — matching `docs/superpowers/specs/2026-07-14-onboarding-tour-design.md`.

**Architecture:** A single client-side module (`frontend/src/lib/tour.ts`) wraps `driver.js` and exposes one `start*Tour()` + one `hasSeen*Tour()` pair per tour. Each tour targets existing DOM elements via new `data-tour="..."` attributes. Auto-trigger-on-mount + manual-replay logic lives in the two consuming components (`WelcomePanel.tsx`, `ScanWizardPanel.tsx`). Persistence is two independent `localStorage` flags, written by `tour.ts` itself via driver.js's `onDestroyed` callback.

**Tech Stack:** React 18, TypeScript, Vite, Vitest + Testing Library (existing), `driver.js` v1.6.0 (new dependency).

## Global Constraints

- `driver.js` is the chosen library (MIT, zero deps) — do not substitute Reactour/Intro.js/Shepherd.js.
- Two `localStorage` keys, exact strings: `campbuddy:tour-seen:welcome`, `campbuddy:tour-seen:wizard`.
- `data-tour` attribute values are a fixed contract between the tour steps (`tour.ts`) and the DOM (components) — must match exactly: `scans-list`, `new-scan-button`, `settings-link`, `provider-select`, `search-recreation-areas`, `narrow-campground-campsite`.
- No backend/API/migration changes — this is 100% frontend.
- No new abstraction/framework for "tours in general" — two fixed, hand-written tour configs.
- The Welcome screen tour is desktop-only (matches `WelcomePanel`'s own existing `md:` gating); the wizard tour has no such gating and must work on mobile viewports too.
- Deviation from the spec, decided during planning: the wizard's "?" replay icon is only rendered while `step === 0` (Provider & Sites), not on all 3 steps as the spec's wording literally suggested — showing it on later steps would let a user replay a tour targeting `data-tour` elements that aren't in the DOM on those steps (nothing rendered by `ProviderSitesFields` exists once the user has advanced), which driver.js can't handle gracefully. This is a implementation-time correction of an ambiguity in the design doc, not a scope change.

---

### Task 1: Tour engine module, dependency, and styling

**Files:**
- Modify: `frontend/package.json` (add `driver.js` dependency)
- Create: `frontend/src/lib/tour.ts`
- Create: `frontend/src/lib/tour.test.ts`
- Create: `frontend/src/styles/tour.css`
- Modify: `frontend/src/main.tsx:1-4` (import the two new stylesheets)

**Interfaces:**
- Produces (consumed by Tasks 2 & 3):
  - `startWelcomeTour(): void`
  - `hasSeenWelcomeTour(): boolean`
  - `startWizardProviderTour(): void`
  - `hasSeenWizardTour(): boolean`
  - all exported from `frontend/src/lib/tour.ts`
- Produces (DOM contract Tasks 2 & 3 must satisfy): the exact `data-tour` selector strings listed in Global Constraints above — Task 1's steps arrays reference them; Tasks 2/3 must add matching attributes to the DOM or the tours silently fail to find their target.

- [ ] **Step 1: Install driver.js**

```bash
cd frontend && npm install driver.js
```

Expected: `package.json` gains `"driver.js": "^1.6.0"` under `dependencies`; `package-lock.json` updates.

- [ ] **Step 2: Write the failing test for `tour.ts`**

Create `frontend/src/lib/tour.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

const driveMock = vi.fn();
const driverMock = vi.fn(() => ({ drive: driveMock }));
vi.mock("driver.js", () => ({ driver: driverMock }));

import {
  startWelcomeTour,
  hasSeenWelcomeTour,
  startWizardProviderTour,
  hasSeenWizardTour,
} from "./tour";

describe("tour", () => {
  beforeEach(() => {
    localStorage.clear();
    driverMock.mockClear();
    driveMock.mockClear();
  });

  describe("welcome tour", () => {
    it("targets the 3 welcome-screen data-tour selectors in order", () => {
      startWelcomeTour();
      const config = driverMock.mock.calls[0][0];
      expect(config.steps.map((s: any) => s.element)).toEqual([
        '[data-tour="scans-list"]',
        '[data-tour="new-scan-button"]',
        '[data-tour="settings-link"]',
      ]);
      expect(driveMock).toHaveBeenCalledTimes(1);
    });

    it("has not been seen until the tour is destroyed", () => {
      expect(hasSeenWelcomeTour()).toBe(false);
      startWelcomeTour();
      expect(hasSeenWelcomeTour()).toBe(false);
      const config = driverMock.mock.calls[0][0];
      config.onDestroyed();
      expect(hasSeenWelcomeTour()).toBe(true);
    });
  });

  describe("wizard provider tour", () => {
    it("targets the 3 wizard data-tour selectors in order", () => {
      startWizardProviderTour();
      const config = driverMock.mock.calls[0][0];
      expect(config.steps.map((s: any) => s.element)).toEqual([
        '[data-tour="provider-select"]',
        '[data-tour="search-recreation-areas"]',
        '[data-tour="narrow-campground-campsite"]',
      ]);
      expect(driveMock).toHaveBeenCalledTimes(1);
    });

    it("has not been seen until the tour is destroyed", () => {
      expect(hasSeenWizardTour()).toBe(false);
      startWizardProviderTour();
      expect(hasSeenWizardTour()).toBe(false);
      const config = driverMock.mock.calls[0][0];
      config.onDestroyed();
      expect(hasSeenWizardTour()).toBe(true);
    });
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/lib/tour.test.ts
```

Expected: FAIL — `Failed to resolve import "./tour"` (module doesn't exist yet).

- [ ] **Step 4: Implement `tour.ts`**

Create `frontend/src/lib/tour.ts`:

```ts
import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import "../styles/tour.css";

const WELCOME_SEEN_KEY = "campbuddy:tour-seen:welcome";
const WIZARD_SEEN_KEY = "campbuddy:tour-seen:wizard";

export function hasSeenWelcomeTour(): boolean {
  return localStorage.getItem(WELCOME_SEEN_KEY) === "1";
}

export function hasSeenWizardTour(): boolean {
  return localStorage.getItem(WIZARD_SEEN_KEY) === "1";
}

export function startWelcomeTour(): void {
  driver({
    showProgress: true,
    onDestroyed: () => localStorage.setItem(WELCOME_SEEN_KEY, "1"),
    steps: [
      {
        element: '[data-tour="scans-list"]',
        popover: {
          title: "Your scans",
          description: "Your scans will show up here once you create one.",
        },
      },
      {
        element: '[data-tour="new-scan-button"]',
        popover: {
          title: "Create a scan",
          description: "Click here to start monitoring a campground for availability.",
        },
      },
      {
        element: '[data-tour="settings-link"]',
        popover: {
          title: "Settings",
          description: "Set up email/Telegram notifications and your Recreation.gov credentials here.",
        },
      },
    ],
  }).drive();
}

export function startWizardProviderTour(): void {
  driver({
    showProgress: true,
    onDestroyed: () => localStorage.setItem(WIZARD_SEEN_KEY, "1"),
    steps: [
      {
        element: '[data-tour="provider-select"]',
        popover: {
          title: "Provider",
          description: "Only RecreationDotGov is available today — other providers are coming soon.",
        },
      },
      {
        element: '[data-tour="search-recreation-areas"]',
        popover: {
          title: "Find a Recreation Area",
          description:
            "Search by name, or if you already know the numeric ID from the Recreation.gov URL " +
            "(e.g. recreation.gov/camping/campgrounds/2991), paste it into “Add by ID” below.",
        },
      },
      {
        element: '[data-tour="narrow-campground-campsite"]',
        popover: {
          title: "Narrow it down (optional)",
          description:
            "Optionally narrow down to a specific campground or campsite once you’ve picked a " +
            "Recreation Area — leave these blank to monitor the whole Recreation Area.",
        },
      },
    ],
  }).drive();
}
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/lib/tour.test.ts
```

Expected: PASS — 4 tests.

- [ ] **Step 6: Create the theming stylesheet**

Create `frontend/src/styles/tour.css`:

```css
.driver-popover {
  background-color: #ffffff;
  color: #1c1917;
  border-radius: 0.5rem;
  border: 1px solid #DFDCD9;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
}

.driver-popover-title {
  color: #1c1917;
}

.driver-popover-description {
  color: #57534e;
}

.driver-popover-progress-text {
  color: #78716c;
}

.driver-popover-footer-btn.driver-popover-next-btn,
.driver-popover-footer-btn.driver-popover-done-btn {
  background-color: #2E6F40;
  border-color: #2E6F40;
  color: #ffffff;
}

.driver-popover-footer-btn.driver-popover-next-btn:hover,
.driver-popover-footer-btn.driver-popover-done-btn:hover {
  background-color: #235732;
  border-color: #235732;
}

.driver-popover-close-btn {
  color: #a8a29e;
}

.driver-popover-close-btn:hover,
.driver-popover-close-btn:focus {
  color: #1c1917;
}

.dark .driver-popover {
  background-color: #1A1A1A;
  color: #EEEEEE;
  border-color: #222222;
}

.dark .driver-popover-title {
  color: #EEEEEE;
}

.dark .driver-popover-description {
  color: #AAAAAA;
}

.dark .driver-popover-progress-text {
  color: #888888;
}

.dark .driver-popover-footer-btn {
  background-color: #222222;
  border-color: #333333;
  color: #EEEEEE;
}

.dark .driver-popover-footer-btn.driver-popover-next-btn,
.dark .driver-popover-footer-btn.driver-popover-done-btn {
  background-color: #2E6F40;
  border-color: #2E6F40;
  color: #ffffff;
}

.dark .driver-popover-close-btn {
  color: #888888;
}

/* Arrow color follows the popover background per side — see driver.js's own
   driver-popover-arrow-side-* rules, which each leave exactly one border
   side at its default color and zero out the other three. */
.dark .driver-popover-arrow-side-left { border-left-color: #1A1A1A; }
.dark .driver-popover-arrow-side-right { border-right-color: #1A1A1A; }
.dark .driver-popover-arrow-side-top { border-top-color: #1A1A1A; }
.dark .driver-popover-arrow-side-bottom { border-bottom-color: #1A1A1A; }
```

- [ ] **Step 7: Wire the stylesheet imports into the app entrypoint**

Read `frontend/src/main.tsx` first to confirm current imports. Modify the top of `frontend/src/main.tsx`:

```ts
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import "driver.js/dist/driver.css";
import "./styles/tour.css";
import App from "./App";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";
```

(Everything below this import block is unchanged.)

- [ ] **Step 8: Run the full frontend test suite to confirm no regressions**

```bash
cd frontend && npx vitest run
```

Expected: all existing tests still pass, plus the 4 new `tour.test.ts` tests (PASS count increases by 4 from the current baseline).

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/tour.ts frontend/src/lib/tour.test.ts frontend/src/styles/tour.css frontend/src/main.tsx
git commit -m "feat: add driver.js-based tour engine module"
```

---

### Task 2: Welcome screen tour

**Files:**
- Modify: `frontend/src/components/layout/ScanListPanel.tsx:16,18`
- Modify: `frontend/src/components/layout/IconSidebar.tsx:122`
- Modify: `frontend/src/components/scans/WelcomePanel.tsx`
- Create: `frontend/src/components/scans/WelcomePanel.test.tsx`

**Interfaces:**
- Consumes: `startWelcomeTour(): void`, `hasSeenWelcomeTour(): boolean` from `frontend/src/lib/tour.ts` (Task 1).
- Produces: `data-tour="scans-list"`, `data-tour="new-scan-button"`, `data-tour="settings-link"` attributes on the DOM (relied on only by Task 1's already-written step selectors — no later task depends on this beyond making the Welcome tour actually find its targets at runtime).

- [ ] **Step 1: Write the failing test for `WelcomePanel`**

Create `frontend/src/components/scans/WelcomePanel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const startWelcomeTourMock = vi.fn();
const hasSeenWelcomeTourMock = vi.fn();
vi.mock("../../lib/tour", () => ({
  startWelcomeTour: startWelcomeTourMock,
  hasSeenWelcomeTour: hasSeenWelcomeTourMock,
}));

import { WelcomePanel } from "./WelcomePanel";

describe("WelcomePanel", () => {
  beforeEach(() => {
    startWelcomeTourMock.mockClear();
    hasSeenWelcomeTourMock.mockClear();
  });

  it("auto-starts the tour on mount when it hasn't been seen", () => {
    hasSeenWelcomeTourMock.mockReturnValue(false);
    render(<WelcomePanel />);
    expect(startWelcomeTourMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start the tour on mount when it has already been seen", () => {
    hasSeenWelcomeTourMock.mockReturnValue(true);
    render(<WelcomePanel />);
    expect(startWelcomeTourMock).not.toHaveBeenCalled();
  });

  it("replays the tour when 'Take the tour' is clicked, regardless of seen state", async () => {
    hasSeenWelcomeTourMock.mockReturnValue(true);
    render(<WelcomePanel />);
    await userEvent.click(screen.getByRole("button", { name: /take the tour/i }));
    expect(startWelcomeTourMock).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/components/scans/WelcomePanel.test.tsx
```

Expected: FAIL — `WelcomePanel` doesn't call `startWelcomeTour`/render a "Take the tour" button yet (the mocked `hasSeenWelcomeTour`/`startWelcomeTour` are never invoked; the first two assertions fail, the third can't find the button).

- [ ] **Step 3: Add the `data-tour` attributes**

Read `frontend/src/components/layout/ScanListPanel.tsx` first. Modify lines 16-18:

```tsx
      <header className="hidden items-center justify-between border-b border-sand-200 px-3 py-3 dark:border-[#222] md:flex">
        <h2 data-tour="scans-list" className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">Scans</h2>
        <button
          data-tour="new-scan-button"
          aria-label="New scan"
          onClick={onNewScan}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700"
        >
          +
        </button>
      </header>
```

Read `frontend/src/components/layout/IconSidebar.tsx` first. Modify line 122:

```tsx
          <Link to="/settings" data-tour="settings-link" onClick={closeDrawer} aria-label="Settings" title="Settings"
            className={cn(iconBtn, pathname === "/settings" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <img src="/icons/gear.svg" alt="" className="h-7 w-7" />
          </Link>
```

- [ ] **Step 4: Implement the auto-trigger + replay link in `WelcomePanel`**

Replace the full contents of `frontend/src/components/scans/WelcomePanel.tsx`:

```tsx
import { useEffect } from "react";
import { hasSeenWelcomeTour, startWelcomeTour } from "../../lib/tour";

export function WelcomePanel() {
  useEffect(() => {
    if (!hasSeenWelcomeTour()) startWelcomeTour();
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <span className="text-5xl" aria-hidden>🏕️</span>
      <h2 className="text-lg font-semibold text-stone-700 dark:text-[#CCC]">Welcome to CampBuddy</h2>
      <p className="max-w-xs text-sm text-stone-500 dark:text-[#888]">
        Select a scan from the list, or create a new one to start monitoring campsite availability.
      </p>
      <button
        type="button"
        onClick={startWelcomeTour}
        className="text-sm text-forest-600 underline hover:text-forest-700 dark:text-forest-400"
      >
        Take the tour
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/components/scans/WelcomePanel.test.tsx
```

Expected: PASS — 3 tests.

- [ ] **Step 6: Run the full frontend test suite to confirm no regressions**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass (previous baseline + 4 from Task 1 + 3 from this task).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/ScanListPanel.tsx frontend/src/components/layout/IconSidebar.tsx frontend/src/components/scans/WelcomePanel.tsx frontend/src/components/scans/WelcomePanel.test.tsx
git commit -m "feat: add auto-shown Welcome screen tour"
```

---

### Task 3: Wizard Provider & Sites tour

**Files:**
- Modify: `frontend/src/components/ui/SearchSelect.tsx:11-19,21-29,96`
- Modify: `frontend/src/components/scans/ScanForm.tsx:85-110`
- Modify: `frontend/src/components/wizard/ScanWizardPanel.tsx`
- Modify: `frontend/src/components/wizard/ScanWizardPanel.test.tsx`

**Interfaces:**
- Consumes: `startWizardProviderTour(): void`, `hasSeenWizardTour(): boolean` from `frontend/src/lib/tour.ts` (Task 1).
- Consumes: `SearchSelectProps<T>` from `frontend/src/components/ui/SearchSelect.tsx` — adds one new optional field `tourId?: string`; all existing callers (in `ScanForm.tsx`, and any others) remain valid unchanged since it's optional.
- Produces: `data-tour="provider-select"`, `data-tour="search-recreation-areas"`, `data-tour="narrow-campground-campsite"` attributes on the DOM — satisfies Task 1's wizard tour step selectors.

- [ ] **Step 1: Write the failing tests for `ScanWizardPanel`'s tour behavior**

Read `frontend/src/components/wizard/ScanWizardPanel.test.tsx` first (it already has 2 tests using MSW + userEvent). Add a mock at the top of the file (after the existing `vi.mock("../../contexts/AuthContext", ...)` line) and three new tests inside the existing `describe("ScanWizardPanel", ...)` block:

```tsx
const startWizardProviderTourMock = vi.fn();
const hasSeenWizardTourMock = vi.fn();
vi.mock("../../lib/tour", () => ({
  startWizardProviderTour: startWizardProviderTourMock,
  hasSeenWizardTour: hasSeenWizardTourMock,
}));
```

(Place this alongside the other `vi.mock` call, before the `import { ScanWizardPanel } ...` line — `vi.mock` calls must run before the mocked module is imported.)

Add inside `describe("ScanWizardPanel", ...)`, after the existing `beforeEach`:

```tsx
  beforeEach(() => {
    startWizardProviderTourMock.mockClear();
    hasSeenWizardTourMock.mockClear();
    hasSeenWizardTourMock.mockReturnValue(true);
  });

  it("auto-starts the provider tour on mount when it hasn't been seen", () => {
    hasSeenWizardTourMock.mockReturnValue(false);
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(startWizardProviderTourMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start the provider tour on mount when it has already been seen", () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(startWizardProviderTourMock).not.toHaveBeenCalled();
  });

  it("replays the provider tour via the help icon, and hides the icon once past step 1", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    await userEvent.click(screen.getAllByRole("button", { name: /show tips for this step/i })[0]);
    expect(startWizardProviderTourMock).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.queryByRole("button", { name: /show tips for this step/i })).not.toBeInTheDocument();
  });
```

Note: there will be a *second* `beforeEach` in the same `describe` block (the existing one that stubs the resolve endpoint stays as-is) — Vitest runs multiple `beforeEach` hooks in a `describe` block in declaration order, so just add this as a second one rather than merging into the existing one.

- [ ] **Step 2: Run the tests to verify the 3 new ones fail**

```bash
cd frontend && npx vitest run src/components/wizard/ScanWizardPanel.test.tsx
```

Expected: the 2 pre-existing tests still PASS; the 3 new tests FAIL (no "Show tips for this step" button exists yet, `startWizardProviderTourMock` never called).

- [ ] **Step 3: Add the `tourId` prop to `SearchSelect`**

Read `frontend/src/components/ui/SearchSelect.tsx` first. Modify the `SearchSelectProps` interface and function signature (lines 11-29):

```tsx
interface SearchSelectProps<T extends Item> {
  label: string;
  selected: T[];
  onChange: (items: T[]) => void;
  search: (query: string) => Promise<T[]>;
  renderResult?: (item: T) => ReactNode;
  disabled?: boolean;
  placeholder?: string;
  tourId?: string;
}

export function SearchSelect<T extends Item>({
  label,
  selected,
  onChange,
  search,
  renderResult,
  disabled,
  placeholder,
  tourId,
}: SearchSelectProps<T>) {
```

Modify the root `<div>` (line 96):

```tsx
    <div className="space-y-2" ref={containerRef} data-tour={tourId}>
```

- [ ] **Step 4: Add `data-tour` targeting in `ProviderSitesFields`**

Read `frontend/src/components/scans/ScanForm.tsx` first. Replace lines 85-110 (the `Select` + three `SearchSelect` elements inside `ProviderSitesFields`):

```tsx
      <div data-tour="provider-select">
        <Select label="Provider" value={state.provider} onChange={(v) => set("provider", v)}
          options={PROVIDERS.map((p) => ({ value: p, label: p, disabled: p !== "RecreationDotGov" }))} />
      </div>
      <SearchSelect
        tourId="search-recreation-areas"
        label="Recreation Areas"
        selected={resolvedRecAreaIds}
        onChange={(items) => set("recAreaIds", items)}
        search={(q) => search.recreationAreas(q)}
        renderResult={(item) => <RecreationAreaResultRow item={item} />}
        placeholder="Search by name, e.g. Yosemite"
      />
      <div data-tour="narrow-campground-campsite" className="space-y-4">
        <SearchSelect
          label="Campgrounds (optional)"
          selected={resolvedCampgroundIds}
          onChange={(items) => set("campgroundIds", items)}
          search={(q) => search.campgrounds(q, recAreaIds.length ? recAreaIds : null)}
          renderResult={(item) => <CampgroundResultRow item={item} />}
          placeholder="Search by name"
        />
        <SearchSelect
          label="Campsites (optional)"
          selected={resolvedCampsiteIds}
          onChange={(items) => set("campsiteIds", items)}
          search={() => (campgroundIds.length ? search.campsites(campgroundIds) : Promise.resolve([]))}
          disabled={campgroundIds.length === 0}
          placeholder={campgroundIds.length ? "Search by site name" : "Select a campground first"}
        />
      </div>
```

- [ ] **Step 5: Wire the auto-trigger effect and the "?" replay icon into `ScanWizardPanel`**

Read `frontend/src/components/wizard/ScanWizardPanel.tsx` first (current full content — 76 lines). Replace the full file:

```tsx
import { useEffect, useState } from "react";
import { useScanFormState } from "../scans/useScanFormState";
import { ProviderSitesFields, DatesFiltersFields, NotificationsFields, windowNights } from "../scans/ScanForm";
import { VerticalStepIndicator } from "./VerticalStepIndicator";
import { Button } from "../ui/Button";
import { useCreateScan } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";
import { hasSeenWizardTour, startWizardProviderTour } from "../../lib/tour";

const STEPS = ["Provider & Sites", "Dates & Filters", "Notifications"];

function TourHelpButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      aria-label="Show tips for this step"
      onClick={startWizardProviderTour}
      className={
        "flex h-5 w-5 items-center justify-center rounded-full border border-sand-200 text-xs text-stone-500 " +
        "hover:bg-sand-100 dark:border-[#222] dark:text-[#888] dark:hover:bg-[#222] " +
        (className ?? "")
      }
    >
      ?
    </button>
  );
}

export function ScanWizardPanel({ onClose, onCreated }: {
  onClose: () => void; onCreated: (id: number) => void;
}) {
  const form = useScanFormState();
  const create = useCreateScan();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasSeenWizardTour()) startWizardProviderTour();
  }, []);

  const hasAnyIds = form.state.recAreaIds.length > 0 || form.state.campgroundIds.length > 0 || form.state.campsiteIds.length > 0;
  const validWindows = form.state.windows.length > 0 && form.state.windows.every((w) => w.start_date && w.end_date);
  const windowNightCounts = form.state.windows.map(windowNights).filter((n): n is number => n !== null);
  const shortestWindowNights = windowNightCounts.length ? Math.min(...windowNightCounts) : null;
  const nightsExceedWindow = shortestWindowNights !== null && form.state.nights > shortestWindowNights;

  function next() {
    setError(null);
    if (step === 0 && !hasAnyIds) { setError("Enter at least one Recreation Area, Campground, or Campsite ID."); return; }
    if (step === 1 && nightsExceedWindow) { setError(`Consecutive nights can't be longer than the shortest search window (${shortestWindowNights} nights).`); return; }
    setStep((s) => Math.min(2, s + 1));
  }

  async function onCreate() {
    setError(null);
    if (!validWindows) { setError("Add at least one search window with start and end dates."); return; }
    if (nightsExceedWindow) { setError(`Consecutive nights can't be longer than the shortest search window (${shortestWindowNights} nights).`); return; }
    try {
      const scan = await create.mutateAsync(form.toScanCreatePayload());
      onCreated(scan.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create scan");
    }
  }

  return (
    <section className="flex flex-1 overflow-hidden">
      <div className="hidden w-56 border-r border-sand-200 p-6 dark:border-[#222] md:block">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">New Scan</h2>
          {step === 0 && <TourHelpButton />}
        </div>
        <VerticalStepIndicator steps={STEPS} current={step} />
      </div>
      <div className="flex flex-1 flex-col overflow-y-auto p-4 md:p-6">
        <div className="mb-4 flex items-center justify-between md:hidden">
          <p className="text-sm font-medium text-stone-600 dark:text-[#AAA]">
            Step {step + 1} of {STEPS.length} · {STEPS[step]}
          </p>
          {step === 0 && <TourHelpButton />}
        </div>
        <div className="max-w-xl flex-1">
          {step === 0 && <ProviderSitesFields state={form.state} set={form.set} />}
          {step === 1 && <DatesFiltersFields state={form.state} set={form.set} />}
          {step === 2 && <NotificationsFields state={form.state} set={form.set} telegramAvailable={!!user?.has_telegram} />}
          {error && <p className="mt-4 text-sm text-[#DC2626]">{error}</p>}
        </div>
        <div className="mt-6 flex justify-between border-t border-sand-200 pt-4 dark:border-[#222]">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <div className="flex gap-2">
            {step > 0 && <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>Back</Button>}
            {step < 2
              ? <Button onClick={next}>Next →</Button>
              : <Button onClick={onCreate} disabled={create.isPending}>
                  {create.isPending ? "Creating…" : "Create Scan"}
                </Button>}
          </div>
        </div>
      </div>
    </section>
  );
}
```

Note the pre-existing mobile step text (`Step {step + 1} of {STEPS.length} · {STEPS[step]}`, previously a standalone `<p>` with its own `mb-4 md:hidden` classes) is now wrapped in a flex row alongside the conditional help button — its own text and classes are otherwise unchanged, just re-parented.

- [ ] **Step 6: Run the wizard test file to verify all tests pass**

```bash
cd frontend && npx vitest run src/components/wizard/ScanWizardPanel.test.tsx
```

Expected: PASS — 5 tests (2 pre-existing + 3 new).

- [ ] **Step 7: Run the full frontend test suite to confirm no regressions**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass (previous baseline + 4 from Task 1 + 3 from Task 2 + 3 from this task).

- [ ] **Step 8: Run the TypeScript compiler to confirm no type errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors (in particular, confirms the new optional `tourId` prop didn't break any existing `SearchSelect` caller, and `TourHelpButton`'s className concatenation is a valid `string`).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/SearchSelect.tsx frontend/src/components/scans/ScanForm.tsx frontend/src/components/wizard/ScanWizardPanel.tsx frontend/src/components/wizard/ScanWizardPanel.test.tsx
git commit -m "feat: add auto-shown wizard Provider & Sites tour"
```

---

### Task 4: Manual verification and wrap-up

**Files:** none (verification only).

**Interfaces:** none — this task consumes the finished feature from Tasks 1-3 and produces nothing further.

- [ ] **Step 1: Run the full test suite one more time**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
```

Expected: all tests pass, no type errors.

- [ ] **Step 2: Manually verify in a browser**

Follow the same manual-verification approach used earlier in this project for the "consecutive nights" bug fixes (start the API on a scratch port + scratch DB copy if port 8000 is occupied by another worktree, start `npm run dev`, log in, drive with Playwright or by hand). Check, in both light and dark mode:

1. **Welcome screen** (desktop viewport, e.g. 1280×800): the tour auto-starts the first time you load the app as a user with no scans; it highlights the Scans header, the "+" button, and the Settings icon in order; the popover is legibly styled (forest-green "Next"/"Done" button, readable text, no visual clipping); after dismissing (Esc, "Done", or clicking outside), reloading the page does *not* re-trigger it; clicking "Take the tour" replays it regardless.
2. **Wizard tour** on desktop: open "+ New scan" for the first time (clear `localStorage` first, since you already dismissed the welcome tour's flag but not the wizard's — or simply check `campbuddy:tour-seen:wizard` specifically); the tour auto-starts on the Provider & Sites step, highlighting the Provider dropdown, the Recreation Areas search bar, and the Campgrounds/Campsites narrowing fields in order; the "?" icon next to "New Scan" replays it; advancing to "Dates & Filters" or "Notifications" hides the "?" icon.
3. **Wizard tour on a narrow/mobile viewport** (e.g. resize to 375×667): repeat the wizard tour check — the mobile step-indicator row's "?" icon should behave the same as the desktop one, and driver.js's popover should still position sensibly relative to the highlighted element without being clipped off-screen.

- [ ] **Step 3: Record the outcome**

No code or commit for this step — if manual verification surfaces an issue, fix it as a small follow-up commit on this branch (not a new task) and re-run Step 1 and the relevant part of Step 2 before considering the plan complete.
