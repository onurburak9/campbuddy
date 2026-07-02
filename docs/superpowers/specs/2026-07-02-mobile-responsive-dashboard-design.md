# Mobile Responsive Dashboard — Design Spec

Issue: [#21 — Web UI: full mobile responsive layout (single-panel collapse)](https://github.com/onurburak9/campbuddy/issues/21)
Builds on: `docs/superpowers/specs/2026-05-27-web-ui-design.md` (Phase-1 web UI, shipped desktop-first)

## Problem

The Phase-1 dashboard is a horizontal three-panel flex — `IconSidebar` (52px) · `ScanListPanel` (240px) · detail slot (`flex-1`) — with no breakpoints. On narrow screens all three stay side-by-side and crush the detail panel. The spec called for *"Responsive (desktop-first, mobile collapses to single panel)"*; this delivers that.

## Goal

On small screens the layout collapses to a single navigable panel: **list ➝ tap ➝ detail with a back affordance**. The icon sidebar becomes a **hamburger-toggled slide-in drawer**. Desktop layout is unchanged.

## Breakpoint

Use Tailwind **`md` (768px)** — the convention already established by `LoginPage` (`grid-cols-1 md:grid-cols-2`) and `StatsRow` (`grid-cols-2 md:grid-cols-4`).

- **≥ md (desktop):** current three-panel layout, unchanged.
- **< md (mobile):** single-panel flow + drawer sidebar + contextual top bar.

## Approach

**CSS breakpoints + existing local state.** No routing changes. The dashboard already tracks `selectedScanId` and `wizardOpen`; we derive:

```
showingDetail = wizardOpen || selectedScanId != null
```

Panel visibility is toggled with Tailwind classes (`hidden md:flex` / `flex`), matching the idiom `StatsRow`/`LoginPage` already use. One new piece of state, `sidebarOpen`, drives the mobile drawer.

**Rejected alternatives:**
- *Route-based selection (`/scans/:id`)* — would give native browser-back, but touches DashboardLayout, tests, and contradicts the Phase-1 spec's "selection is UI state" decision, for a benefit the explicit back button already covers. Noted as a possible future enhancement.
- *`matchMedia` hook to conditionally render panels* — adds runtime JS and a hydration flash; CSS visibility classes are the idiomatic Tailwind path.

## Mobile chrome

### Contextual top bar — `MobileTopBar` (new, `md:hidden`)

Rendered by `DashboardLayout` above the panels. Its left control is **conditionally rendered** (not just CSS-hidden) based on `showingDetail`, which keeps the hamburger↔back swap unit-testable in jsdom.

- **List view** (`!showingDetail`): `☰` hamburger (opens drawer) · "Scans" title · `+` new-scan button.
- **Detail / wizard view** (`showingDetail`): `←` back button labelled "Scans" (resets `wizardOpen` + `selectedScanId`).

```
LIST VIEW                     DETAIL VIEW (after tap)
┌───────────────────────┐     ┌───────────────────────┐
│ ☰  Scans        [+]   │     │ ←  Scans              │
├───────────────────────┤     ├───────────────────────┤
│ ● Yosemite            │     │ [Overview][Results][R… │  ← tabs scroll-x
│ ● Big Sur             │     │ stats (2-col)…         │
└───────────────────────┘     └───────────────────────┘
```

The back-label points at the destination ("Scans"), so the top bar needs no scan data — no extra fetch.

### Icon sidebar as drawer — `IconSidebar` (refactor)

A single element serves both layouts via responsive classes:

- **Desktop:** `md:static md:translate-x-0` — the fixed 52px vertical sidebar, unchanged.
- **Mobile:** `fixed left-0 top-0 z-50 h-full transition-transform`, translated off-screen (`-translate-x-full`) unless `open`, then `translate-x-0`. A backdrop (`fixed inset-0 z-40 bg-black/40 md:hidden`) renders behind it when open.
- **Closing:** backdrop click, `Escape` key, or selecting any nav item calls `onClose`.

New props: `open: boolean`, `onClose: () => void`. Existing `onOpenScans` retained; nav clicks also call `onClose`.

### Panels

- **`ScanListPanel`:** `w-full md:w-60`; visible when `!showingDetail` (`flex`), hidden behind detail on mobile (`hidden md:flex`). Its internal "Scans / +" header becomes `hidden md:flex` — the `+` and title move to the mobile top bar to avoid duplication.
- **Detail wrapper** (in `DashboardLayout`, wrapping detail/wizard/welcome): full width on mobile when `showingDetail` (`flex`), otherwise `hidden md:flex`; always visible on desktop.

## Detail-chrome responsive tweaks

- **`ScanDetailHeader`:** stack on mobile — `flex-col gap-3 md:flex-row md:items-start md:justify-between`; padding `px-4 md:px-6`. Action buttons (Pause/Edit/Delete) already `flex gap-2`; allow wrap.
- **`Tabs`:** horizontal scroll on overflow — container `overflow-x-auto`, buttons `whitespace-nowrap shrink-0`.
- **`ScanDetailPanel`:** body/tabs padding `px-4 md:px-6`.
- **`ScanWizardPanel`:** vertical step sidebar (`w-56`) becomes `hidden md:block`; a compact horizontal step indicator (`md:hidden`, e.g. "Step 1 of 3 · Provider & Sites") shows on mobile; padding `p-4 md:p-6`. Nav buttons (Cancel/Back/Next) already wrap via `justify-between`.

## Settings page

`SettingsPage` shares `IconSidebar`, so it gets the same drawer treatment plus its own `sidebarOpen` state and a minimal mobile header (hamburger + "Settings" title, `md:hidden`). The centered `ProfileForm` already reflows.

## Login page

`LoginPage` is already `md:grid-cols-2`. Change `NaturePanel` to `hidden md:flex` so the login form owns the full small screen instead of sharing it with a half-height banner.

## Component / state summary

| Item | Change |
|---|---|
| `DashboardLayout` | add `sidebarOpen` state; derive `showingDetail`; render `MobileTopBar` + drawer `IconSidebar`; responsive visibility on list + detail wrapper |
| `MobileTopBar` | **new** — `md:hidden` contextual bar (list: hamburger/title/＋; detail: back) |
| `IconSidebar` | drawer mode via `open`/`onClose` + responsive classes; nav-click and Esc close |
| `ScanListPanel` | `w-full md:w-60`; header `hidden md:flex` |
| `ScanDetailHeader` | stack `flex-col md:flex-row`; `px-4 md:px-6` |
| `Tabs` | `overflow-x-auto`; buttons `whitespace-nowrap shrink-0` |
| `ScanDetailPanel` | `px-4 md:px-6` |
| `ScanWizardPanel` | step sidebar `hidden md:block`; mobile step indicator; `p-4 md:p-6` |
| `SettingsPage` | `sidebarOpen` state + drawer + mobile header |
| `NaturePanel` | `hidden md:flex` |

No API, hook, type, or data-flow changes. No new dependencies.

## Testing

jsdom does not evaluate media queries, so behaviour is tested via **state-driven conditional rendering** (not computed layout):

- **`MobileTopBar`:** renders hamburger in list mode / back in detail mode; hamburger click → `onOpenSidebar`; back click → `onBack`; `+` click → `onNewScan`.
- **`IconSidebar` drawer:** `open=false` applies `-translate-x-full`, `open=true` applies `translate-x-0`; backdrop click and nav-item click call `onClose`; `Escape` calls `onClose`.
- **`DashboardLayout`:** initially top bar shows hamburger; selecting a `ScanListItem` swaps it to the back control; clicking back restores the hamburger (verifies list ⇄ detail collapse).
- **Regression:** existing 69 tests stay green; desktop rendering unchanged.

Mock nothing new — all external I/O already mocked (MSW). Follows `docs/agents/testing.md`.

## Out of scope

- Bottom tab-bar navigation redesign.
- Route-based scan selection / deep-linking.
- Native browser/OS back-gesture integration (explicit back button only).
- Campground search, map views, and other Phase-1-excluded items.
