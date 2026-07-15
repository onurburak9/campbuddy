# Onboarding tour (Welcome screen + New Scan wizard)

**Date:** 2026-07-14
**Status:** Approved (design)
**Branch:** `feat/onboarding-tour`

## Problem

New users land on the "Welcome to CampBuddy" empty state
(`frontend/src/components/scans/WelcomePanel.tsx`) with no guidance beyond a
single sentence, and the New Scan wizard's first step
(`ProviderSitesFields` in `frontend/src/components/scans/ScanForm.tsx`) asks
for a provider and Recreation Area with no explanation of where numeric IDs
come from, how the name-search bar works, or why every provider but
`RecreationDotGov` is disabled. A first-time user has to guess.

## Goals

1. A short, auto-shown, dismissible walkthrough on the Welcome screen
   introducing the sidebar: the scans list, the "+ New scan" button, and the
   Settings link.
2. A second short walkthrough, auto-shown the first time a user opens the New
   Scan wizard, explaining the Provider dropdown, the Recreation Area
   search bar (and its "Add by ID" fallback), and the optional
   campground/campsite narrowing fields.
3. Each walkthrough is manually replayable after its first dismissal.
4. No backend involvement — this is client-side, cosmetic onboarding.

## Non-goals (deliberately out of scope)

- **Tours for the Dates & Filters or Notifications wizard steps, or the scan
  detail page.** Deferred — the two walkthroughs above cover the two places a
  brand-new user is most likely to get stuck (finding the entry point, and
  filling in the first wizard step).
- **Cross-device tour state.** "Has seen this tour" is tracked in
  `localStorage`, not the `User` model. It resets if a user switches
  browsers/devices or clears storage — acceptable for a cosmetic onboarding
  flag. No migration, no API changes.
- **A generic/reusable "tour framework."** Two fixed, hand-written tours.
  YAGNI on an abstraction until a third tour is needed.
- **Mobile-specific tour variants.** The Welcome screen tour only needs to
  work at `md:` breakpoint and up, since `WelcomePanel` itself is
  desktop-only (`DashboardLayout.tsx`'s `showingDetail ? "flex" : "hidden
  md:flex"` wrapper). The wizard tour, unlike the Welcome tour, *is* shown on
  mobile (the wizard has no such breakpoint gate) — driver.js positions
  relative to the DOM target regardless of viewport, so no special-casing is
  expected to be needed, but this should be confirmed visually on a narrow
  viewport during implementation.

---

## Design

### 1. Library: driver.js

Evaluated against Intro.js, Shepherd.js, and Reactour:

| Library | License | Deps | Verdict |
|---|---|---|---|
| **driver.js** | MIT | 0 | **Chosen.** Vanilla JS, framework-agnostic, ~90KB unpacked. Needs a thin wrapper for React but the API (`driver({ steps }).drive()`) is trivial to call from a `useEffect`. |
| Reactour | MIT | 7 (incl. `lodash.debounce`, `prop-types` — dated) | React-native API but heavier dependency footprint for what should be a lightweight feature. |
| Intro.js | AGPL-3.0 | — | Copyleft license adds legal exposure even for self-hosted use; avoided. |
| Shepherd.js | AGPL-3.0 | — | Same AGPL concern; also built for more complex multi-page tours than needed here. |

Add `driver.js` to `frontend/package.json` dependencies.

### 2. Module: `frontend/src/lib/tour.ts`

Exports two functions, one per tour, each wrapping `driver.js`:

```ts
export function startWelcomeTour(): void { ... }
export function startWizardProviderTour(): void { ... }
```

Each builds a `driver({ steps: [...] })` instance targeting `[data-tour="..."]`
selectors (see below) and calls `.drive()`. Both use `driver.js`'s
`onDestroyed` callback to write the corresponding `localStorage` flag once the
tour is dismissed or completed (whether by finishing all steps, pressing Esc,
or clicking outside) — so a user who skips the tour still won't see it
auto-trigger again.

Two independent `localStorage` keys:

- `campbuddy:tour-seen:welcome`
- `campbuddy:tour-seen:wizard`

### 3. Welcome screen tour — 3 steps

Auto-triggered from `WelcomePanel.tsx` on mount, if
`campbuddy:tour-seen:welcome` is unset. Also replayable via a "Take the tour"
link added to `WelcomePanel.tsx`'s existing copy.

New `data-tour` attributes on existing elements:

1. `data-tour="scans-list"` on the `<h2>Scans</h2>` header,
   `ScanListPanel.tsx:16` — *"Your scans will show up here once you create
   one."*
2. `data-tour="new-scan-button"` on the `+` button (`aria-label="New scan"`),
   `ScanListPanel.tsx:18` — *"Click here to start monitoring a campground for
   availability."*
3. `data-tour="settings-link"` on the Settings `<Link>`,
   `IconSidebar.tsx:122` — *"Set up email/Telegram notifications and your
   Recreation.gov credentials here."*

### 4. Wizard tour — 3 steps

Auto-triggered from `ScanWizardPanel.tsx` on mount (the wizard always opens on
step 0, "Provider & Sites"), if `campbuddy:tour-seen:wizard` is unset. Also
replayable via a small "?" help icon placed next to the step indicator
(`ScanWizardPanel.tsx`, near the `STEPS` list) — visible regardless of which
step the user is currently on, but only wired to replay the Provider & Sites
tour for now, since that's the only step with one.

`SearchSelect` (`frontend/src/components/ui/SearchSelect.tsx`) is a generic
component reused for Recreation Areas, Campgrounds, and Campsites — its three
instances render identical markup, so a plain `data-tour` attribute inside the
component would tag all three indistinguishably. It gets one new optional
prop:

```ts
interface SearchSelectProps<T extends Item> {
  // ...existing props
  tourId?: string;
}
```

passed through as `data-tour={tourId}` on the component's root `<div>`
(`SearchSelect.tsx:96`). Only the Recreation Areas instance in
`ProviderSitesFields` (`ScanForm.tsx`) passes one:
`tourId="search-recreation-areas"`.

Steps:

1. `data-tour="provider-select"` on the `Provider` `<Select>`,
   `ScanForm.tsx:77` — *"Only RecreationDotGov is available today — other
   providers are coming soon."*
2. `data-tour="search-recreation-areas"` on the Recreation Areas
   `SearchSelect` instance, `ScanForm.tsx:79-86` — *"Search by name, or if you
   already know the numeric ID from the Recreation.gov URL (e.g.
   recreation.gov/camping/campgrounds/**2991**), paste it into 'Add by ID'
   below."*
3. `data-tour="narrow-campground-campsite"` wrapping the Campgrounds and
   Campsites `SearchSelect` instances, `ScanForm.tsx:87-102` — *"Optionally
   narrow down to a specific campground or campsite once you've picked a
   Recreation Area — leave these blank to monitor the whole Recreation
   Area."*

### 5. Styling/theming

`driver.js/dist/driver.css` imported once (in `frontend/src/main.tsx` or
`App.tsx`, alongside the existing Tailwind entry stylesheet). A new
`frontend/src/styles/tour.css` overrides `.driver-popover` to match the
existing palette (forest-600 accent on the "Next" button, sand/stone borders
and text colors), plus a `.dark .driver-popover { ... }` block — dark mode is
toggled via a `dark` class on `<html>` (`ThemeContext.tsx`), not a media
query, so the popover needs an explicit class-scoped override rather than
`prefers-color-scheme`.

### 6. Testing

driver.js manipulates the DOM outside React's tree (its popover/overlay is
appended to `document.body`), so:

- **Unit tests** (`WelcomePanel.test.tsx`, and a new or extended
  `ScanWizardPanel.test.tsx`): mock the `frontend/src/lib/tour.ts` module and
  assert `startWelcomeTour()` / `startWizardProviderTour()` is called exactly
  once on first mount when the relevant `localStorage` flag is unset, not
  called when it's set, and called again when the "Take the tour" link / "?"
  icon is clicked regardless of the flag.
- **Manual browser verification**: popover positioning, copy, and light/dark
  theming, the same way the two bug fixes earlier in this session were
  verified — not something a jsdom-based unit test can meaningfully assert.

---

## Open questions for implementation

None — all decisions above were confirmed during brainstorming. Exact wording
of tooltip copy in sections 3–4 is a reasonable starting draft; small
adjustments during implementation are expected and don't require re-opening
this design.
