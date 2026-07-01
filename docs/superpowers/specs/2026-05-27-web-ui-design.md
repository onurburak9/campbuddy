# CampBuddy Web UI — Design Spec

## Overview

A React-based single-page application for CampBuddy that provides a scan-centric dashboard for managing campsite availability monitors. Multi-user community app with per-user logins and dashboards. Communicates with the existing FastAPI REST API via session cookie auth.

## Tech Stack

- **Framework:** React 18+ with TypeScript
- **Build:** Vite
- **Styling:** Tailwind CSS (class-based dark mode strategy)
- **Data fetching:** TanStack Query (React Query)
- **Routing:** React Router v6
- **Deployment:** Separate Docker container (nginx serving static files, reverse-proxying `/api` to FastAPI)

## Design Influences

- **Linear** — sidebar navigation, status dots, warm gray palette, information density
- **Better Stack / Cronitor** — run health timelines, monitoring card patterns, smart summary headers
- **Campnab** — scan-centric dashboard, stepped creation wizard, active/paused states
- **Notion** — warm grays, disciplined spacing, readable typography
- **AllTrails / REI / NPS** — forest green primary, nature-themed aesthetics, outdoor authority feel
- **Hipcamp / Recreation.gov** — card-based campsite listings, availability visualization

## Color System

### Palette

| Role | Light Mode | Dark Mode | Notes |
|------|-----------|-----------|-------|
| Primary | `#2E6F40` (forest green) | `#2E6F40` | CTAs, active nav, brand |
| Primary dark | `#1B4332` (deep evergreen) | `#1B4332` | Login gradient, emphasis |
| Accent | `#C7522A` (campfire/terracotta) | `#C7522A` | Cart-added badges, warm highlights |
| Success | `#22C55E` | `#22C55E` | Active scans, successful runs |
| Warning | `#EAB308` | `#EAB308` | Paused scans, no-result runs |
| Error | `#DC2626` | `#DC2626` | Failed runs, delete actions |
| Info | `#60A5FA` | `#60A5FA` | Sites-found counts, stats |
| Background | `#FAF9F6` (warm cream) | `#0D0D0D` | Page background |
| Surface | `#FFFFFF` | `#1A1A1A` | Cards, panels |
| Border | `#DFDCD9` | `#222222` | Dividers, card borders |
| Text primary | `#1A1A1A` | `#EEEEEE` | Headings, body |
| Text secondary | `#6B6B6B` | `#888888` | Metadata, labels |
| Text muted | `#999999` | `#555555` | Timestamps, hints |

### Tailwind Config

Custom color scales in `tailwind.config.ts`:
- `forest` — 50 through 900, with 600 as the primary `#2E6F40`
- `campfire` — 50 through 900, with 500 as the accent `#C7522A`
- `sand` — 50: `#FAF9F6`, 100: `#F0EFED`, 200: `#DFDCD9`

Dark mode uses the `class` strategy toggled via `ThemeProvider`.

## Pages & Routes

| Route | Page | Auth | Description |
|-------|------|------|-------------|
| `/login` | Login | No | Split-screen login; redirects to `/` if authenticated |
| `/` | Dashboard | Yes | Three-panel layout; default view with scan list + detail |
| `/settings` | Settings | Yes | Profile editing (email, Telegram, rec.gov creds) |

Only 3 routes. Scan selection, tab switching, and the creation wizard are UI state within the dashboard — not separate routes.

## Layout: Three-Panel Hybrid

The dashboard uses a three-panel layout inspired by Linear/Slack/email clients:

```
┌──────┬──────────────────┬─────────────────────────────┐
│ Icon │   Scan List      │        Detail Panel          │
│ Side │   Panel          │                              │
│ bar  │                  │   (tabs: Overview, Results,  │
│      │  ● Yosemite      │    Run History, Settings)    │
│  ⛺  │  ● Big Sur       │                              │
│  📊  │  ● Pinnacles     │   OR                        │
│  ⚙️  │                  │                              │
│      │                  │   Scan Creation Wizard       │
│      │                  │   (slide-in replacement)     │
└──────┴──────────────────┴─────────────────────────────┘
```

### Icon Sidebar (~52px wide)
- CampBuddy logo/icon at top
- Navigation icons: Scans (tent), Settings (gear)
- Theme toggle (sun/moon) near bottom
- User avatar at bottom

### Scan List Panel (~240px wide)
- Header: "Scans" title + "+" new scan button
- List of `ScanListItem` components, each showing:
  - Status dot (green=active, yellow=paused)
  - Scan name (or campground fallback)
  - Date range + sites found count
- Selected scan highlighted with border
- Empty state when no scans exist

### Detail Panel (remaining width)
- Shows the selected scan's details in a tabbed interface
- Replaced by the scan creation wizard when creating a new scan

## Scan Detail Panel — Tabbed Interface

### Header
- Status dot + scan name (large, bold)
- Provider + IDs + nights metadata line
- Action buttons: Pause/Resume, Edit, Delete

### Tab: Overview
- **Stats row** — 4 cards: Sites Found, In Cart, Total Runs, Success Rate
- **Run health bar** — Cronitor-style colored bars showing last N runs (green=success, red=error, yellow=no results). Hoverable for tooltip with timestamp and details.
- **Search windows list** — Date range chips

### Tab: Results
- Paginated list of `ScanResult` cards, each showing:
  - Site name + facility name
  - Booking dates + campsite type
  - Cart status badge (green "In cart" or neutral)
  - "Book →" link button (opens booking URL in new tab)
- Sorted by `first_seen_at` descending (newest first)

### Tab: Run History
- Paginated list of run rows, each showing:
  - Status dot (green/red/yellow)
  - Timestamp (relative, e.g., "3 min ago")
  - Outcome label (Success, No Results, Error)
  - Sites found count
  - Duration
  - Error message (expandable, if present)
- Sorted by `started_at` descending

### Tab: Settings
- Inline form to edit the scan configuration
- Same fields as the creation wizard but pre-filled
- Save button applies changes via PATCH

## Scan Creation Wizard — Slide-In Panel

When the user clicks "+ New Scan", the detail panel is replaced by a slide-in wizard with a vertical step indicator on the left side.

### Step 1: Provider & Sites
- Scan name (optional text input)
- Provider (dropdown: RecreationDotGov, Yellowstone, ReserveCalifornia, etc.)
- Recreation Area IDs (comma-separated input)
- Campground IDs (optional, comma-separated)
- Campsite IDs (optional, comma-separated)

### Step 2: Dates & Filters
- Search windows (add/remove date range pairs with start/end date pickers)
- Consecutive nights (number input, min 1)
- Days of week (multi-select chips: Mon–Sun)
- Weekends only toggle

### Step 3: Notifications & Polling
- Polling interval (select: 1 min, 5 min, 10 min, 15 min, 30 min)
- Notify via email toggle
- Notify via Telegram toggle (only if user has telegram_chat_id set)
- Notify on new sites only toggle

### Navigation
- "Back" and "Next →" buttons at the bottom
- "Cancel" returns to the previous detail view
- Step 3 has "Create Scan" as the final action

## Login Page — Split Screen

Left half:
- Forest green gradient (`#1B4332` → `#2E6F40` → `#3A8A50`)
- Tree silhouettes at the bottom
- Subtle star dots
- CampBuddy logo (tent icon in frosted glass square)
- "CampBuddy" title + "Never miss a campsite again" tagline

Right half:
- "Welcome back" heading + "Sign in to your account" subtitle
- Email input
- Password input
- "Sign In" button (forest green)
- Error message area for invalid credentials

Redirects to `/` on successful login. Shows inline error on failure.

## Settings Page

Profile editing form:
- Email address
- Telegram Chat ID
- Recreation.gov email
- Recreation.gov password (masked, with reveal toggle)
- "Save" button

Uses the existing `PATCH /api/v1/users/me` endpoint.

## Component Architecture

```
App
├── AuthProvider (context: user, login, logout, isAuthenticated)
├── ThemeProvider (dark/light toggle, persisted to localStorage)
├── QueryClientProvider (TanStack Query)
│
├── LoginPage
│   ├── NaturePanel
│   └── LoginForm
│
└── ProtectedRoute (redirects to /login if not authenticated)
    └── DashboardLayout
        ├── IconSidebar
        ├── ScanListPanel
        │   ├── ScanListHeader
        │   ├── ScanListItem[]
        │   └── EmptyState
        │
        ├── ScanDetailPanel (when scan selected)
        │   ├── ScanDetailHeader
        │   ├── TabBar
        │   ├── OverviewTab
        │   │   ├── StatsRow
        │   │   ├── RunHealthBar
        │   │   └── SearchWindowsList
        │   ├── ResultsTab
        │   │   ├── ResultCard[]
        │   │   └── Pagination
        │   ├── RunHistoryTab
        │   │   ├── RunRow[]
        │   │   └── Pagination
        │   └── SettingsTab
        │
        ├── ScanWizardPanel (when creating)
        │   ├── VerticalStepIndicator
        │   ├── Step1ProviderSites
        │   ├── Step2DatesFilters
        │   └── Step3Notifications
        │
        ├── SettingsPage
        │   └── ProfileForm
        │
        └── WelcomePanel (no scan selected)
```

## State Management

### Server State (TanStack Query)

| Hook | Endpoint | Notes |
|------|----------|-------|
| `useMe()` | `GET /auth/me` | Current user; cached, refetches on window focus |
| `useScans()` | `GET /scans` | Scan list; refetches on focus + after mutations |
| `useScan(id)` | `GET /scans/{id}` | Single scan detail |
| `useScanRuns(scanId, page)` | `GET /scans/{id}/runs` | Paginated run history |
| `useScanResults(scanId, page)` | `GET /scans/{id}/results` | Paginated results |
| `useCreateScan()` | `POST /scans` | Invalidates scan list on success |
| `useUpdateScan()` | `PATCH /scans/{id}` | Invalidates scan + list |
| `useDeleteScan()` | `DELETE /scans/{id}` | Invalidates list, clears selection |
| `usePauseScan()` | `POST /scans/{id}/pause` | Invalidates scan + list |
| `useResumeScan()` | `POST /scans/{id}/resume` | Invalidates scan + list |
| `useUpdateProfile()` | `PATCH /users/me` | Invalidates me query |
| `useLogin()` | `POST /auth/login` | Sets auth state, redirects |
| `useLogout()` | `POST /auth/logout` | Clears auth state, redirects |

### Local UI State

- `selectedScanId` — which scan is active in the list (DashboardLayout state)
- `activeTab` — current detail tab (ScanDetailPanel state)
- `wizardOpen` / `wizardStep` — creation wizard state (DashboardLayout state)
- `theme` — dark/light (ThemeContext, persisted to localStorage)

No global store (Zustand/Redux) needed.

## API Client

```
src/api/
├── client.ts      — base fetch wrapper with error handling
├── auth.ts        — login(), logout(), me()
├── scans.ts       — list, create, update, delete, pause, resume
├── runs.ts        — listRuns(scanId, page)
├── results.ts     — listResults(scanId, page)
└── users.ts       — updateProfile()
```

`client.ts` provides a `fetchApi(path, options)` function that:
- Prepends `/api/v1` to all paths
- Sets `Content-Type: application/json`
- Includes `credentials: 'include'` for cookie auth
- Throws typed errors for 401 (redirect to login), 4xx, 5xx

## Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts          — proxy /api to localhost:8000 in dev
├── tailwind.config.ts      — custom colors (forest, campfire, sand)
├── tsconfig.json
├── Dockerfile              — multi-stage: node build → nginx
├── nginx.conf              — serve static + proxy /api to api:8000
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx
    ├── App.tsx              — routes, providers
    ├── api/                 — fetch wrappers per resource
    ├── hooks/               — TanStack Query hooks
    ├── components/
    │   ├── layout/          — DashboardLayout, IconSidebar, ScanListPanel
    │   ├── scans/           — ScanDetailPanel, tabs, ScanListItem, WelcomePanel
    │   ├── wizard/          — ScanWizardPanel, Step1/2/3, VerticalStepIndicator
    │   ├── auth/            — LoginPage, LoginForm, NaturePanel
    │   ├── settings/        — ProfileForm
    │   └── ui/              — Button, Input, Badge, Select, Tabs, Pagination, Toggle
    ├── contexts/            — AuthContext, ThemeContext
    ├── pages/               — LoginPage, DashboardPage, SettingsPage
    ├── types/               — TypeScript interfaces matching API schemas
    └── lib/                 — cn() utility, date formatting helpers
```

## Docker Integration

New service added to `docker-compose.yml`:

```yaml
frontend:
  build: ./frontend
  ports:
    - "127.0.0.1:3000:80"
  depends_on:
    - api
```

The nginx config inside the frontend container:
- Serves static files from `/usr/share/nginx/html`
- Proxies `/api/` requests to `http://api:8000/api/`
- Returns `index.html` for all other routes (SPA fallback)

## Phase 1 Scope

### Included
- Login / logout
- Scan list with status indicators
- Scan detail with all 4 tabs (Overview, Results, Run History, Settings)
- Scan creation wizard (3 steps, manual IDs)
- Scan actions (pause, resume, edit, delete)
- Profile settings page
- Light + dark mode
- Responsive (desktop-first, mobile collapses to single panel)
- Docker container with nginx

### Excluded (future phases)
- Campground search / autocomplete
- Admin dashboard
- Real-time WebSocket updates
- User self-registration
- Mobile native app
- Map visualization of campgrounds
