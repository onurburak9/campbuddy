# CampBuddy Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React + TypeScript single-page app (`frontend/`) that provides a scan-centric dashboard for CampBuddy, talking to the existing FastAPI cookie-auth REST API, deployed as an nginx Docker container.

**Architecture:** Vite-built React 18 SPA. Three contexts (Auth, Theme, QueryClient) wrap a React Router v6 tree with exactly three routes (`/login`, `/`, `/settings`). Server state lives entirely in TanStack Query hooks backed by a thin typed `fetchApi` wrapper that sends `credentials: 'include'` for cookie auth. UI state (selected scan, active tab, wizard step) is local React state in `DashboardLayout`. No global store. Styling is Tailwind with custom `forest`/`campfire`/`sand` scales and class-based dark mode.

**Tech Stack:** React 18, TypeScript 5, Vite 5, Tailwind CSS 3, TanStack Query v5, React Router v6, Vitest + React Testing Library + jsdom + MSW (mock service worker) for tests.

## Global Constraints

- **API base:** every request path is prefixed with `/api/v1` inside `fetchApi`. Resource modules pass paths WITHOUT the prefix (e.g. `/scans`, `/auth/me`).
- **Auth:** cookie-based (httponly `samesite=lax`). Client never reads/writes a token. Every request sends `credentials: 'include'`. A 401 from any request triggers redirect to `/login`.
- **Login response:** `POST /auth/login` returns `{ "ok": true }` and sets the cookie — there is no user body. Fetch the user separately via `GET /auth/me`.
- **Pagination:** `/scans/{id}/runs` and `/scans/{id}/results` accept `page` (1-based, default 1) and `page_size` (default 20, max 100) query params and return a plain JSON array (NO total-count envelope). "Has next page" is inferred as `items.length === page_size`.
- **Providers:** the provider dropdown must use exactly these 19 values (from `api/schemas.py` `VALID_PROVIDERS`): RecreationDotGov, Yellowstone, GoingToCamp, ReserveCalifornia, AlabamaStateParks, ArizonaStateParks, FloridaStateParks, MinnesotaStateParks, MissouriStateParks, OhioStateParks, VirginiaStateParks, NorthernTerritory, FairfaxCountyParks, MaricopaCountyParks, OregonMetro, RecreationDotGovTicket, RecreationDotGovTimedEntry, RecreationDotGovDailyTicket, RecreationDotGovDailyTimedEntry.
- **days_of_week:** integers 0–6 where Monday=0 … Sunday=6.
- **Colors (exact hex):** primary forest `#2E6F40`, primary-dark `#1B4332`, campfire accent `#C7522A`, success `#22C55E`, warning `#EAB308`, error `#DC2626`, info `#60A5FA`. Light bg `#FAF9F6` / surface `#FFFFFF` / border `#DFDCD9`. Dark bg `#0D0D0D` / surface `#1A1A1A` / border `#222222`.
- **Status semantics:** scan `status` is `active` | `paused` | `completed` (the ORM `ScanStatus` enum has all three). Run `outcome` is `success` | `no_results` | `error` | null (running). Tone mapping: active→success(green), paused→warning(yellow), completed→neutral(gray); run success→green, no_results→yellow, error→red.
- **Node:** built and verified on Node 20+ (local env is v25). All commands run from `frontend/`.

---

## File Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts          — React plugin, dev proxy /api → localhost:8000, vitest config
├── tsconfig.json / tsconfig.node.json
├── tailwind.config.ts      — forest/campfire/sand scales, darkMode: 'class'
├── postcss.config.js
├── Dockerfile              — node build → nginx
├── nginx.conf              — static + /api proxy + SPA fallback
├── .dockerignore
├── public/favicon.svg
└── src/
    ├── main.tsx            — mounts <App/> with providers
    ├── App.tsx             — Router + routes + ProtectedRoute
    ├── index.css          — Tailwind directives + base layer
    ├── test/setup.ts      — RTL + jsdom + MSW server lifecycle
    ├── test/server.ts     — MSW server + default handlers
    ├── types/index.ts     — interfaces matching API schemas
    ├── lib/
    │   ├── cn.ts          — className merge helper
    │   └── format.ts      — relative time, date range, duration formatters
    ├── api/
    │   ├── client.ts      — fetchApi wrapper + ApiError
    │   ├── auth.ts        — login/logout/me
    │   ├── scans.ts       — list/get/create/update/delete/pause/resume
    │   ├── runs.ts        — listRuns
    │   ├── results.ts     — listResults
    │   └── users.ts       — updateProfile
    ├── contexts/
    │   ├── ThemeContext.tsx
    │   └── AuthContext.tsx
    ├── hooks/
    │   ├── queryKeys.ts
    │   ├── useScans.ts     — useScans, useScan, useCreateScan, useUpdateScan, useDeleteScan, usePauseScan, useResumeScan
    │   ├── useRuns.ts
    │   ├── useResults.ts
    │   └── useProfile.ts
    ├── components/
    │   ├── ui/            — Button, Input, Badge, Select, Toggle, Tabs, Pagination, StatusDot, Spinner
    │   ├── auth/          — LoginPage, LoginForm, NaturePanel
    │   ├── layout/        — DashboardLayout, IconSidebar, ScanListPanel, ScanListItem, EmptyState
    │   ├── scans/         — ScanDetailPanel, ScanDetailHeader, TabBar, OverviewTab, StatsRow,
    │   │                    RunHealthBar, SearchWindowsList, ResultsTab, ResultCard,
    │   │                    RunHistoryTab, RunRow, SettingsTab, WelcomePanel, ScanForm
    │   ├── wizard/        — ScanWizardPanel, VerticalStepIndicator, Step1, Step2, Step3
    │   └── settings/      — SettingsPage, ProfileForm
    └── pages/            — (thin route wrappers if needed; most pages are components above)
```

---

## Phase A — Foundation

### Task 1: Scaffold the frontend project

**Files:**
- Create: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/postcss.config.js`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/test/setup.ts`, `frontend/.gitignore`
- Modify: `.gitignore` (root) — add `frontend/node_modules` and `frontend/dist`

**Interfaces:**
- Produces: a runnable Vite app, `npm test` wired to Vitest, `npm run build` producing `dist/`.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "campbuddy-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "jsdom": "^24.1.1",
    "msw": "^2.3.5",
    "postcss": "^8.4.40",
    "tailwindcss": "^3.4.7",
    "typescript": "^5.5.4",
    "vite": "^5.3.5",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en" class="">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CampBuddy</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
```

- [ ] **Step 4: Create `frontend/tsconfig.json` and `frontend/tsconfig.node.json`**

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noEmit": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create `frontend/postcss.config.js` and `frontend/src/index.css`**

`postcss.config.js`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-sand-50 text-stone-900 antialiased dark:bg-[#0D0D0D] dark:text-[#EEEEEE];
  }
}
```

- [ ] **Step 6: Create `frontend/src/main.tsx` (temporary placeholder App)**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`src/App.tsx` (placeholder, replaced in Task 7):
```tsx
export default function App() {
  return <div className="p-8 text-2xl font-bold">CampBuddy</div>;
}
```

- [ ] **Step 7: Create `frontend/src/test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());
```

- [ ] **Step 8: Create `frontend/.gitignore`**

```
node_modules
dist
*.local
```

- [ ] **Step 9: Install and verify build**

Run: `cd frontend && npm install && npm run build`
Expected: dependencies install, `tsc -b` passes, `vite build` writes `dist/index.html`. No errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/ .gitignore
git commit -m "feat(ui): scaffold Vite + React + TS frontend"
```

---

### Task 2: Tailwind theme configuration

**Files:**
- Create: `frontend/tailwind.config.ts`
- Test: `frontend/src/lib/cn.test.ts` (created here to lock the className helper used everywhere)
- Create: `frontend/src/lib/cn.ts`

**Interfaces:**
- Produces: `cn(...classes)` → `string`; Tailwind classes `forest-{50..900}`, `campfire-{50..900}`, `sand-{50,100,200}`.

- [ ] **Step 1: Write the failing test for `cn`**

`src/lib/cn.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("joins truthy class names with spaces", () => {
    expect(cn("a", "b")).toBe("a b");
  });
  it("drops falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });
  it("supports conditional object syntax", () => {
    expect(cn("base", { active: true, hidden: false })).toBe("base active");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/cn.test.ts`
Expected: FAIL — cannot find module `./cn`.

- [ ] **Step 3: Implement `src/lib/cn.ts`**

```ts
type ClassValue = string | false | null | undefined | Record<string, boolean>;

export function cn(...values: ClassValue[]): string {
  const out: string[] = [];
  for (const v of values) {
    if (!v) continue;
    if (typeof v === "string") out.push(v);
    else for (const [key, on] of Object.entries(v)) if (on) out.push(key);
  }
  return out.join(" ");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/cn.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: {
          50: "#EAF3EC", 100: "#CFE3D5", 200: "#A6CBB1", 300: "#74AC86",
          400: "#4A8C61", 500: "#357A4B", 600: "#2E6F40", 700: "#235732",
          800: "#1B4332", 900: "#13301F",
        },
        campfire: {
          50: "#FBEDE7", 100: "#F6D6C8", 200: "#EBAD93", 300: "#E0855F",
          400: "#D66A40", 500: "#C7522A", 600: "#A84323", 700: "#84341B",
          800: "#5F2613", 900: "#3D180C",
        },
        sand: { 50: "#FAF9F6", 100: "#F0EFED", 200: "#DFDCD9" },
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 6: Verify build still passes**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/tailwind.config.ts frontend/src/lib/cn.ts frontend/src/lib/cn.test.ts
git commit -m "feat(ui): tailwind theme + cn helper"
```

---

### Task 3: TypeScript types matching API schemas

**Files:**
- Create: `frontend/src/types/index.ts`

**Interfaces:**
- Produces: `User`, `Scan`, `ScanStatus`, `ScanRun`, `RunOutcome`, `ScanResult`, `SearchWindow`, `ScanCreatePayload`, `ScanUpdatePayload`, `ProfileUpdatePayload`, `Profile`, `PROVIDERS` (const string array).

- [ ] **Step 1: Create `src/types/index.ts`**

```ts
export type ScanStatus = "active" | "paused" | "completed";
export type RunOutcome = "success" | "no_results" | "error";

export interface User {
  id: number;
  email: string;
  scan_limit: number;
  scans_used: number;
  has_telegram: boolean;
}

export interface ScanStats {
  sites_found: number;
  in_cart: number;
  total_runs: number;
  success_rate: number; // 0–100
}

export interface SearchWindow {
  start_date: string; // ISO date YYYY-MM-DD
  end_date: string;
}

export interface Scan {
  id: number;
  user_id: number;
  provider: string;
  name: string | null;
  status: ScanStatus;
  polling_interval: number;
  rec_area_ids: number[] | null;
  campground_ids: number[] | null;
  campsite_ids: number[] | null;
  search_windows: SearchWindow[];
  nights: number;
  days_of_week: number[] | null;
  weekends_only: boolean;
  notify_via_email: boolean;
  notify_via_telegram: boolean;
  notify_on_new_only: boolean;
  created_at: string;
}

export interface ScanRun {
  id: number;
  scan_id: number;
  started_at: string;
  finished_at: string | null;
  outcome: RunOutcome | null;
  sites_found: number;
  error_message: string | null;
}

export interface ScanResult {
  id: number;
  scan_id: number;
  campsite_id: string;
  facility_name: string;
  site_name: string;
  campsite_type: string;
  booking_date: string;
  booking_end_date: string;
  booking_url: string;
  first_seen_at: string;
  cart_added: boolean;
  notified: boolean;
}

export interface ScanCreatePayload {
  provider: string;
  name?: string | null;
  polling_interval: number;
  rec_area_ids?: number[] | null;
  campground_ids?: number[] | null;
  campsite_ids?: number[] | null;
  search_windows: SearchWindow[];
  nights: number;
  days_of_week?: number[] | null;
  weekends_only: boolean;
  notify_via_email: boolean;
  notify_via_telegram: boolean;
  notify_on_new_only: boolean;
}

export type ScanUpdatePayload = Partial<Omit<ScanCreatePayload, "provider">>;

export interface Profile {
  id: number;
  email: string;
  telegram_chat_id: string | null;
  recreationgov_email: string | null;
  scan_limit: number;
}

export interface ProfileUpdatePayload {
  email?: string;
  telegram_chat_id?: string;
  recreationgov_email?: string;
  recreationgov_password?: string;
}

export const PROVIDERS = [
  "RecreationDotGov", "Yellowstone", "GoingToCamp", "ReserveCalifornia",
  "AlabamaStateParks", "ArizonaStateParks", "FloridaStateParks",
  "MinnesotaStateParks", "MissouriStateParks", "OhioStateParks",
  "VirginiaStateParks", "NorthernTerritory", "FairfaxCountyParks",
  "MaricopaCountyParks", "OregonMetro", "RecreationDotGovTicket",
  "RecreationDotGovTimedEntry", "RecreationDotGovDailyTicket",
  "RecreationDotGovDailyTimedEntry",
] as const;
```

- [ ] **Step 2: Verify type-check passes**

Run: `cd frontend && npm run lint`
Expected: PASS (no emit, no type errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(ui): add API types"
```

---

### Task 4: API client + resource modules + MSW test server

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/api/scans.ts`, `frontend/src/api/runs.ts`, `frontend/src/api/results.ts`, `frontend/src/api/users.ts`
- Create: `frontend/src/test/server.ts`
- Modify: `frontend/src/test/setup.ts` (wire MSW lifecycle)
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `class ApiError extends Error { status: number; }`
  - `fetchApi<T>(path: string, options?: RequestInit): Promise<T>`
  - `auth.login(email, password): Promise<void>`, `auth.logout(): Promise<void>`, `auth.me(): Promise<User>`
  - `scans.list(): Promise<Scan[]>`, `scans.get(id): Promise<Scan>`, `scans.create(payload): Promise<Scan>`, `scans.update(id, payload): Promise<Scan>`, `scans.remove(id): Promise<void>`, `scans.pause(id): Promise<Scan>`, `scans.resume(id): Promise<Scan>`, `scans.stats(id): Promise<ScanStats>`
  - `runs.list(scanId, page, pageSize): Promise<ScanRun[]>`
  - `results.list(scanId, page, pageSize): Promise<ScanResult[]>`
  - `users.getProfile(): Promise<Profile>`, `users.updateProfile(payload): Promise<Profile>`
- Consumes: types from Task 3.

- [ ] **Step 1: Write failing test `src/api/client.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { fetchApi, ApiError } from "./client";

describe("fetchApi", () => {
  it("prepends /api/v1 and returns parsed JSON", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([{ id: 1 }])));
    const data = await fetchApi<{ id: number }[]>("/scans");
    expect(data).toEqual([{ id: 1 }]);
  });

  it("throws ApiError with status on 4xx", async () => {
    server.use(
      http.get("/api/v1/scans", () =>
        HttpResponse.json({ detail: "nope" }, { status: 403 })
      )
    );
    await expect(fetchApi("/scans")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
    });
  });

  it("returns undefined for 204 No Content", async () => {
    server.use(http.delete("/api/v1/scans/1", () => new HttpResponse(null, { status: 204 })));
    const out = await fetchApi("/scans/1", { method: "DELETE" });
    expect(out).toBeUndefined();
  });
});
```

- [ ] **Step 2: Create `src/test/server.ts`**

```ts
import { setupServer } from "msw/node";

export const server = setupServer();
```

- [ ] **Step 3: Update `src/test/setup.ts` to wire MSW**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach, afterAll, beforeAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: FAIL — cannot find module `./client`.

- [ ] **Step 5: Implement `src/api/client.ts`**

```ts
const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchApi<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });

  if (res.status === 401 && !path.startsWith("/auth")) {
    // Session expired — bounce to login.
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 7: Implement resource modules**

`src/api/auth.ts`:
```ts
import { fetchApi } from "./client";
import type { User } from "../types";

export const auth = {
  login: (email: string, password: string) =>
    fetchApi<void>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => fetchApi<void>("/auth/logout", { method: "POST" }),
  me: () => fetchApi<User>("/auth/me"),
};
```

`src/api/scans.ts`:
```ts
import { fetchApi } from "./client";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, ScanStats } from "../types";

export const scans = {
  list: () => fetchApi<Scan[]>("/scans"),
  get: (id: number) => fetchApi<Scan>(`/scans/${id}`),
  create: (payload: ScanCreatePayload) =>
    fetchApi<Scan>("/scans", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: ScanUpdatePayload) =>
    fetchApi<Scan>(`/scans/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id: number) => fetchApi<void>(`/scans/${id}`, { method: "DELETE" }),
  pause: (id: number) => fetchApi<Scan>(`/scans/${id}/pause`, { method: "POST" }),
  resume: (id: number) => fetchApi<Scan>(`/scans/${id}/resume`, { method: "POST" }),
  stats: (id: number) => fetchApi<ScanStats>(`/scans/${id}/stats`),
};
```

`src/api/runs.ts`:
```ts
import { fetchApi } from "./client";
import type { ScanRun } from "../types";

export const runs = {
  list: (scanId: number, page = 1, pageSize = 20) =>
    fetchApi<ScanRun[]>(`/scans/${scanId}/runs?page=${page}&page_size=${pageSize}`),
};
```

`src/api/results.ts`:
```ts
import { fetchApi } from "./client";
import type { ScanResult } from "../types";

export const results = {
  list: (scanId: number, page = 1, pageSize = 20) =>
    fetchApi<ScanResult[]>(`/scans/${scanId}/results?page=${page}&page_size=${pageSize}`),
};
```

`src/api/users.ts`:
```ts
import { fetchApi } from "./client";
import type { Profile, ProfileUpdatePayload } from "../types";

export const users = {
  getProfile: () => fetchApi<Profile>("/users/me"),
  updateProfile: (payload: ProfileUpdatePayload) =>
    fetchApi<Profile>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
};
```

- [ ] **Step 8: Verify lint + tests pass**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api frontend/src/test
git commit -m "feat(ui): typed API client + resource modules + MSW test harness"
```

---

## Phase B — Providers, Auth & Routing

### Task 5: ThemeContext

**Files:**
- Create: `frontend/src/contexts/ThemeContext.tsx`
- Test: `frontend/src/contexts/ThemeContext.test.tsx`

**Interfaces:**
- Produces: `ThemeProvider` (component), `useTheme(): { theme: "light"|"dark"; toggle: () => void }`. Persists to `localStorage["theme"]`, toggles `document.documentElement.classList` `dark`.

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "./ThemeContext";

function Probe() {
  const { theme, toggle } = useTheme();
  return <button onClick={toggle}>theme:{theme}</button>;
}

describe("ThemeContext", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to light and toggles to dark, applying the dark class", async () => {
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText("theme:light")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("theme:dark")).toBeInTheDocument();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("theme")).toBe("dark");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/contexts/ThemeContext.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/contexts/ThemeContext.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
interface ThemeCtx { theme: Theme; toggle: () => void; }

const Ctx = createContext<ThemeCtx | null>(null);

function initialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return <Ctx.Provider value={{ theme, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/contexts/ThemeContext.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/ThemeContext.tsx frontend/src/contexts/ThemeContext.test.tsx
git commit -m "feat(ui): theme context with persistence"
```

---

### Task 6: AuthContext

**Files:**
- Create: `frontend/src/contexts/AuthContext.tsx`
- Test: `frontend/src/contexts/AuthContext.test.tsx`

**Interfaces:**
- Produces: `AuthProvider`, `useAuth(): { user: User | null; isLoading: boolean; isAuthenticated: boolean; login(email,password): Promise<void>; logout(): Promise<void>; }`.
- Consumes: `auth` from `src/api/auth.ts`; `useQueryClient` from TanStack Query.
- Behavior: On mount, runs `useQuery(['me'], auth.me)` with `retry: false`. `isAuthenticated = !!user`. `login` calls `auth.login` then refetches `['me']`. `logout` calls `auth.logout` then clears the query cache.

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { isAuthenticated, isLoading, user, login } = useAuth();
  if (isLoading) return <span>loading</span>;
  return (
    <div>
      <span>{isAuthenticated ? `hi ${user?.email}` : "anon"}</span>
      <button onClick={() => login("a@b.c", "pw")}>login</button>
    </div>
  );
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider><Probe /></AuthProvider>
    </QueryClientProvider>
  );
}

describe("AuthContext", () => {
  it("shows anon when /auth/me returns 401", async () => {
    server.use(http.get("/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));
    wrap();
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument());
  });

  it("authenticates after login", async () => {
    let logged = false;
    server.use(
      http.get("/api/v1/auth/me", () =>
        logged
          ? HttpResponse.json({ id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0 })
          : new HttpResponse(null, { status: 401 })
      ),
      http.post("/api/v1/auth/login", () => { logged = true; return HttpResponse.json(undefined); })
    );
    wrap();
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument());
    await userEvent.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByText("hi a@b.c")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/contexts/AuthContext.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/contexts/AuthContext.tsx`**

```tsx
import { createContext, useContext, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { auth } from "../api/auth";
import { ApiError } from "../api/client";
import type { User } from "../types";

interface AuthCtx {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: auth.me,
    retry: (count, err) => !(err instanceof ApiError && err.status === 401) && count < 1,
    staleTime: 5 * 60 * 1000,
  });

  const login = async (email: string, password: string) => {
    await auth.login(email, password);
    await qc.invalidateQueries({ queryKey: ["me"] });
  };
  const logout = async () => {
    await auth.logout();
    qc.clear();
  };

  return (
    <Ctx.Provider
      value={{ user: data ?? null, isLoading, isAuthenticated: !!data, login, logout }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/contexts/AuthContext.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/AuthContext.tsx frontend/src/contexts/AuthContext.test.tsx
git commit -m "feat(ui): auth context backed by /auth/me query"
```

---

### Task 7: App shell — providers, router, ProtectedRoute

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Create: `frontend/src/components/auth/ProtectedRoute.tsx`
- Create stubs: `frontend/src/components/auth/LoginPage.tsx`, `frontend/src/components/layout/DashboardLayout.tsx`, `frontend/src/components/settings/SettingsPage.tsx` (replaced in later tasks)
- Test: `frontend/src/components/auth/ProtectedRoute.test.tsx`

**Interfaces:**
- Consumes: `useAuth`, `AuthProvider`, `ThemeProvider`, `QueryClientProvider`.
- Produces: `ProtectedRoute` (renders children when authenticated, `<Navigate to="/login">` otherwise, spinner while loading). Routes: `/login`→LoginPage, `/`→DashboardLayout (protected), `/settings`→SettingsPage (protected).

- [ ] **Step 1: Write failing test for ProtectedRoute**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { AuthProvider } from "../../contexts/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<div>login page</div>} />
            <Route path="/" element={<ProtectedRoute><div>secret</div></ProtectedRoute>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("ProtectedRoute", () => {
  it("redirects to /login when unauthenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));
    renderAt("/");
    await waitFor(() => expect(screen.getByText("login page")).toBeInTheDocument());
  });

  it("renders children when authenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0 })));
    renderAt("/");
    await waitFor(() => expect(screen.getByText("secret")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/auth/ProtectedRoute.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ProtectedRoute.tsx`**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { Spinner } from "../ui/Spinner";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

> Note: `Spinner` is created in Task 8 (UI primitives). If executing strictly in order, create a one-line placeholder `export function Spinner(){return <span>…</span>;}` in `src/components/ui/Spinner.tsx` now and refine in Task 8.

- [ ] **Step 4: Create page stubs**

`src/components/auth/LoginPage.tsx`: `export function LoginPage(){return <div>login</div>;}`
`src/components/layout/DashboardLayout.tsx`: `export function DashboardLayout(){return <div>dashboard</div>;}`
`src/components/settings/SettingsPage.tsx`: `export function SettingsPage(){return <div>settings</div>;}`

- [ ] **Step 5: Rewrite `src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { LoginPage } from "./components/auth/LoginPage";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { SettingsPage } from "./components/settings/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Rewrite `src/main.tsx` with all providers**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 7: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): app shell, providers, routing, ProtectedRoute"
```

---

### Task 8: UI primitives

**Files:**
- Create: `frontend/src/components/ui/Button.tsx`, `Input.tsx`, `Badge.tsx`, `Select.tsx`, `Toggle.tsx`, `Tabs.tsx`, `Pagination.tsx`, `StatusDot.tsx`, `Spinner.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx`, `frontend/src/components/ui/Pagination.test.tsx`

**Interfaces:**
- `Button`: props `{ variant?: "primary"|"secondary"|"danger"|"ghost"; size?: "sm"|"md"; } & ButtonHTMLAttributes`. Default variant `primary`.
- `Input`: `InputHTMLAttributes` + optional `label?: string; error?: string;`.
- `Badge`: `{ tone: "success"|"warning"|"error"|"info"|"accent"|"neutral"; children }`.
- `Select`: `{ value; onChange(value:string); options: {value:string;label:string}[]; label?; } `.
- `Toggle`: `{ checked: boolean; onChange(next:boolean): void; label?: string; disabled?: boolean }`.
- `Tabs`: `{ tabs: {id:string;label:string}[]; active:string; onChange(id:string):void }`.
- `Pagination`: `{ page: number; hasNext: boolean; onPrev():void; onNext():void }` — Prev disabled when page<=1, Next disabled when !hasNext.
- `StatusDot`: `{ tone: "success"|"warning"|"error"|"neutral"; title?: string }`.
- `Spinner`: spinning indicator.

- [ ] **Step 1: Write failing tests**

`Button.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
  it("does not fire when disabled", async () => {
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

`Pagination.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("disables Prev on page 1 and Next when no more pages", () => {
    render(<Pagination page={1} hasNext={false} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/ui`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement primitives**

`src/components/ui/Spinner.tsx`:
```tsx
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-forest-600 border-t-transparent ${className}`}
    />
  );
}
```

`src/components/ui/Button.tsx`:
```tsx
import { type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "danger" | "ghost";
interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

const variants: Record<Variant, string> = {
  primary: "bg-forest-600 text-white hover:bg-forest-700 disabled:bg-forest-300",
  secondary:
    "bg-sand-100 text-stone-800 hover:bg-sand-200 dark:bg-[#222] dark:text-[#EEE] dark:hover:bg-[#333]",
  danger: "bg-[#DC2626] text-white hover:bg-red-700 disabled:bg-red-300",
  ghost: "bg-transparent text-stone-600 hover:bg-sand-100 dark:text-[#888] dark:hover:bg-[#222]",
};

export function Button({ variant = "primary", size = "md", className, ...rest }: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "px-2.5 py-1 text-sm" : "px-4 py-2 text-sm",
        variants[variant],
        className
      )}
      {...rest}
    />
  );
}
```

`src/components/ui/Input.tsx`:
```tsx
import { type InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, id, ...rest }: Props) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">{label}</span>}
      <input
        id={id}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 outline-none",
          "border-sand-200 focus:border-forest-600 focus:ring-1 focus:ring-forest-600",
          "dark:border-[#222] dark:bg-[#1A1A1A] dark:text-[#EEE]",
          error && "border-[#DC2626]",
          className
        )}
        {...rest}
      />
      {error && <span className="mt-1 block text-sm text-[#DC2626]">{error}</span>}
    </label>
  );
}
```

`src/components/ui/Badge.tsx`:
```tsx
import { cn } from "../../lib/cn";

type Tone = "success" | "warning" | "error" | "info" | "accent" | "neutral";
const tones: Record<Tone, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  accent: "bg-campfire-100 text-campfire-700 dark:bg-campfire-900/40 dark:text-campfire-300",
  neutral: "bg-sand-100 text-stone-600 dark:bg-[#222] dark:text-[#888]",
};

export function Badge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}
```

`src/components/ui/StatusDot.tsx`:
```tsx
import { cn } from "../../lib/cn";

type Tone = "success" | "warning" | "error" | "neutral";
const colors: Record<Tone, string> = {
  success: "bg-[#22C55E]",
  warning: "bg-[#EAB308]",
  error: "bg-[#DC2626]",
  neutral: "bg-stone-400",
};

export function StatusDot({ tone, title }: { tone: Tone; title?: string }) {
  return <span title={title} className={cn("inline-block h-2.5 w-2.5 rounded-full", colors[tone])} />;
}
```

`src/components/ui/Select.tsx`:
```tsx
import { cn } from "../../lib/cn";

interface Props {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label?: string;
  className?: string;
}

export function Select({ value, onChange, options, label, className }: Props) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">{label}</span>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 outline-none",
          "border-sand-200 focus:border-forest-600 dark:border-[#222] dark:bg-[#1A1A1A] dark:text-[#EEE]",
          className
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
```

`src/components/ui/Toggle.tsx`:
```tsx
import { cn } from "../../lib/cn";

interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, disabled }: Props) {
  return (
    <label className={cn("flex items-center gap-3", disabled && "opacity-50")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 rounded-full transition-colors",
          checked ? "bg-forest-600" : "bg-sand-200 dark:bg-[#333]"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
            checked ? "translate-x-5" : "translate-x-0.5"
          )}
        />
      </button>
      {label && <span className="text-sm text-stone-700 dark:text-[#CCC]">{label}</span>}
    </label>
  );
}
```

`src/components/ui/Tabs.tsx`:
```tsx
import { cn } from "../../lib/cn";

interface Props {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-sand-200 dark:border-[#222]">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors",
            active === t.id
              ? "border-forest-600 text-forest-700 dark:text-forest-400"
              : "border-transparent text-stone-500 hover:text-stone-800 dark:text-[#888] dark:hover:text-[#CCC]"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

`src/components/ui/Pagination.tsx`:
```tsx
import { Button } from "./Button";

interface Props {
  page: number;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ page, hasNext, onPrev, onNext }: Props) {
  return (
    <div className="flex items-center justify-between pt-4">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={onPrev}>
        ← Prev
      </Button>
      <span className="text-sm text-stone-500 dark:text-[#888]">Page {page}</span>
      <Button variant="secondary" size="sm" disabled={!hasNext} onClick={onNext}>
        Next →
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/ui`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui
git commit -m "feat(ui): UI primitives (Button, Input, Badge, Select, Toggle, Tabs, Pagination, StatusDot, Spinner)"
```

---

### Task 9: Login page

**Files:**
- Modify: `frontend/src/components/auth/LoginPage.tsx`
- Create: `frontend/src/components/auth/LoginForm.tsx`, `frontend/src/components/auth/NaturePanel.tsx`
- Test: `frontend/src/components/auth/LoginForm.test.tsx`

**Interfaces:**
- Consumes: `useAuth().login`, `useAuth().isAuthenticated`, `ApiError`, `Button`, `Input`, `useNavigate`.
- `LoginPage`: split-screen; if `isAuthenticated`, `<Navigate to="/" replace>`. Left = `NaturePanel`, right = `LoginForm`.
- `LoginForm`: controlled email/password; on submit calls `login`, navigates to `/` on success; on `ApiError` shows "Invalid email or password" (for 401) else the error message.

- [ ] **Step 1: Write failing test for LoginForm**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const login = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ login }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("logs in and navigates home on success", async () => {
    login.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><LoginForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "pw");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });

  it("shows an error on 401", async () => {
    login.mockRejectedValueOnce(new ApiError(401, "Invalid credentials"));
    render(<MemoryRouter><LoginForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "bad");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument()
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/auth/LoginForm.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `LoginForm.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("Invalid email or password");
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Welcome back</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Sign in to your account</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Input id="password" label="Password" type="password" autoComplete="current-password"
        value={password} onChange={(e) => setPassword(e.target.value)} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Signing in…" : "Sign In"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/auth/LoginForm.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement `NaturePanel.tsx`**

```tsx
export function NaturePanel() {
  return (
    <div className="relative hidden flex-col justify-end overflow-hidden bg-gradient-to-br from-forest-800 via-forest-600 to-forest-500 p-12 text-white md:flex">
      <div className="absolute right-10 top-10 h-1 w-1 rounded-full bg-white/60" />
      <div className="absolute right-24 top-20 h-1 w-1 rounded-full bg-white/40" />
      <div className="absolute left-16 top-16 h-1 w-1 rounded-full bg-white/50" />
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
        <span className="text-3xl" aria-hidden>⛺</span>
      </div>
      <h2 className="text-3xl font-bold">CampBuddy</h2>
      <p className="mt-2 text-white/80">Never miss a campsite again</p>
      <svg className="pointer-events-none absolute bottom-0 left-0 w-full text-forest-900/40"
        viewBox="0 0 400 80" preserveAspectRatio="none" aria-hidden>
        <polygon points="40,80 60,30 80,80" fill="currentColor" />
        <polygon points="120,80 150,15 180,80" fill="currentColor" />
        <polygon points="240,80 270,25 300,80" fill="currentColor" />
        <polygon points="330,80 350,35 370,80" fill="currentColor" />
      </svg>
    </div>
  );
}
```

- [ ] **Step 6: Implement `LoginPage.tsx`**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { NaturePanel } from "./NaturePanel";
import { LoginForm } from "./LoginForm";
import { Spinner } from "../ui/Spinner";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <NaturePanel />
      <div className="flex items-center justify-center bg-sand-50 p-8 dark:bg-[#0D0D0D]">
        <LoginForm />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/auth
git commit -m "feat(ui): split-screen login page"
```

---

## Phase C — Query Hooks

### Task 10: TanStack Query hooks + format helpers

**Files:**
- Create: `frontend/src/hooks/queryKeys.ts`, `frontend/src/hooks/useScans.ts`, `frontend/src/hooks/useRuns.ts`, `frontend/src/hooks/useResults.ts`, `frontend/src/hooks/useProfile.ts`
- Create: `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/format.test.ts`, `frontend/src/hooks/useScans.test.tsx`

**Interfaces:**
- `queryKeys`: `scans: ['scans']`, `scan: (id) => ['scans', id]`, `runs: (id,page) => ['scans',id,'runs',page]`, `results: (id,page) => ['scans',id,'results',page]`, `me: ['me']`.
- `useScans()`, `useScan(id|null)`, `useScanStats(id|null)`, `useCreateScan()`, `useUpdateScan()`, `useDeleteScan()`, `usePauseScan()`, `useResumeScan()`, `useScanRuns(scanId,page)`, `useScanResults(scanId,page)`, `useProfile()`, `useUpdateProfile()`.
- Mutations invalidate the relevant keys (create/delete/pause/resume → `['scans']` + the scan; update → both).
- `format.ts`: `relativeTime(iso): string` ("3 min ago"), `dateRange(start,end): string` ("May 12 – May 14"), `duration(start,end|null): string` ("12s", "—" if no end).

- [ ] **Step 1: Write failing tests for format helpers**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { relativeTime, dateRange, duration } from "./format";

describe("format", () => {
  beforeEach(() => vi.useFakeTimers().setSystemTime(new Date("2026-06-24T12:00:00Z")));
  afterEach(() => vi.useRealTimers());

  it("relativeTime renders minutes ago", () => {
    expect(relativeTime("2026-06-24T11:57:00Z")).toMatch(/3 min/);
  });
  it("dateRange renders a compact range", () => {
    expect(dateRange("2026-05-12", "2026-05-14")).toMatch(/May 12.*May 14/);
  });
  it("duration returns em dash when unfinished", () => {
    expect(duration("2026-06-24T12:00:00Z", null)).toBe("—");
  });
  it("duration renders seconds", () => {
    expect(duration("2026-06-24T11:59:48Z", "2026-06-24T12:00:00Z")).toBe("12s");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/lib/format.ts`**

```ts
export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 45) return "just now";
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function dateRange(start: string, end: string): string {
  const fmt = (d: string) =>
    new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${fmt(start)} – ${fmt(end)}`;
}

export function duration(start: string, end: string | null): string {
  if (!end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  return `${min}m ${sec % 60}s`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Implement `src/hooks/queryKeys.ts`**

```ts
export const queryKeys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  scans: ["scans"] as const,
  scan: (id: number) => ["scans", id] as const,
  stats: (id: number) => ["scans", id, "stats"] as const,
  runs: (id: number, page: number) => ["scans", id, "runs", page] as const,
  results: (id: number, page: number) => ["scans", id, "results", page] as const,
};
```

- [ ] **Step 6: Implement `src/hooks/useScans.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scans } from "../api/scans";
import { queryKeys } from "./queryKeys";
import type { ScanCreatePayload, ScanUpdatePayload } from "../types";

export function useScans() {
  return useQuery({ queryKey: queryKeys.scans, queryFn: scans.list });
}

export function useScan(id: number | null) {
  return useQuery({
    queryKey: id ? queryKeys.scan(id) : ["scans", "none"],
    queryFn: () => scans.get(id as number),
    enabled: id != null,
  });
}

export function useScanStats(id: number | null) {
  return useQuery({
    queryKey: id ? queryKeys.stats(id) : ["scans", "none", "stats"],
    queryFn: () => scans.stats(id as number),
    enabled: id != null,
  });
}

export function useCreateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScanCreatePayload) => scans.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.scans }),
  });
}

export function useUpdateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ScanUpdatePayload }) =>
      scans.update(id, payload),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}

export function useDeleteScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.scans }),
  });
}

export function usePauseScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.pause(id),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}

export function useResumeScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.resume(id),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}
```

- [ ] **Step 7: Implement `useRuns.ts`, `useResults.ts`, `useProfile.ts`**

`src/hooks/useRuns.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { runs } from "../api/runs";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanRuns(scanId: number | null, page: number) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, PAGE_SIZE),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RUNS_PAGE_SIZE };
```

`src/hooks/useResults.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { results } from "../api/results";
import { queryKeys } from "./queryKeys";

const PAGE_SIZE = 20;

export function useScanResults(scanId: number | null, page: number) {
  return useQuery({
    queryKey: scanId ? queryKeys.results(scanId, page) : ["scans", "none", "results", page],
    queryFn: () => results.list(scanId as number, page, PAGE_SIZE),
    enabled: scanId != null,
  });
}

export { PAGE_SIZE as RESULTS_PAGE_SIZE };
```

`src/hooks/useProfile.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { users } from "../api/users";
import { queryKeys } from "./queryKeys";
import type { ProfileUpdatePayload } from "../types";

export function useProfile() {
  return useQuery({ queryKey: queryKeys.profile, queryFn: users.getProfile });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => users.updateProfile(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.me });
      qc.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}
```

- [ ] **Step 8: Write integration test `src/hooks/useScans.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { useScans } from "./useScans";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useScans", () => {
  it("fetches the scan list", async () => {
    server.use(http.get("/api/v1/scans", () =>
      HttpResponse.json([{ id: 1, name: "Yosemite" }])));
    const { result } = renderHook(() => useScans(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });
});
```

- [ ] **Step 9: Run all tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/hooks frontend/src/lib/format.ts frontend/src/lib/format.test.ts
git commit -m "feat(ui): query hooks + date/format helpers"
```

---

## Phase D — Dashboard Layout & Scan List

### Task 11: DashboardLayout + IconSidebar

**Files:**
- Modify: `frontend/src/components/layout/DashboardLayout.tsx`
- Create: `frontend/src/components/layout/IconSidebar.tsx`
- Test: `frontend/src/components/layout/IconSidebar.test.tsx`

**Interfaces:**
- `DashboardLayout` owns UI state: `selectedScanId: number | null`, `wizardOpen: boolean`. Renders `IconSidebar` + `ScanListPanel` + right region. Right region logic: if `wizardOpen` → `ScanWizardPanel`; else if `selectedScanId` → `ScanDetailPanel`; else `WelcomePanel`. (ScanListPanel/ScanDetailPanel/ScanWizardPanel/WelcomePanel are stubbed here, built in Tasks 12–18.)
- `IconSidebar`: props `{ onOpenScans():void; theme toggle via useTheme; logout via useAuth; navigate to /settings }`. Renders logo, Scans (tent) button, Settings (gear) link to `/settings`, theme toggle (sun/moon), logout/avatar.

- [ ] **Step 1: Write failing test for IconSidebar**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const toggle = vi.fn();
vi.mock("../../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light", toggle }) }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ logout: vi.fn(), user: { email: "a@b.c" } }) }));

import { IconSidebar } from "./IconSidebar";

describe("IconSidebar", () => {
  it("toggles theme when the theme button is clicked", async () => {
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /theme/i }));
    expect(toggle).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/layout/IconSidebar.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `IconSidebar.tsx`**

```tsx
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "../../contexts/ThemeContext";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/cn";

export function IconSidebar({ onOpenScans }: { onOpenScans: () => void }) {
  const { theme, toggle } = useTheme();
  const { logout, user } = useAuth();
  const { pathname } = useLocation();

  const iconBtn = "flex h-10 w-10 items-center justify-center rounded-lg text-xl transition-colors";
  return (
    <nav className="flex w-[52px] flex-col items-center justify-between border-r border-sand-200 bg-white py-3 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="flex flex-col items-center gap-2">
        <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-forest-600 text-white" aria-hidden>⛺</div>
        <Link to="/" onClick={onOpenScans} aria-label="Scans"
          className={cn(iconBtn, pathname === "/" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
          <span aria-hidden>⛺</span>
        </Link>
        <Link to="/settings" aria-label="Settings"
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
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/layout/IconSidebar.test.tsx`
Expected: PASS.

- [ ] **Step 5: Implement `DashboardLayout.tsx` (with stub right-side components)**

Create stub files first so imports resolve (each refined in later tasks):
- `src/components/layout/ScanListPanel.tsx`: `export function ScanListPanel(_:{selectedScanId:number|null;onSelect:(id:number)=>void;onNewScan:()=>void}){return <div className="w-60 border-r border-sand-200 dark:border-[#222]" />;}`
- `src/components/scans/ScanDetailPanel.tsx`: `export function ScanDetailPanel(_:{scanId:number}){return <div className="flex-1" />;}`
- `src/components/scans/WelcomePanel.tsx`: `export function WelcomePanel(){return <div className="flex flex-1 items-center justify-center text-stone-400">Select a scan</div>;}`
- `src/components/wizard/ScanWizardPanel.tsx`: `export function ScanWizardPanel(_:{onClose:()=>void;onCreated:(id:number)=>void}){return <div className="flex-1" />;}`

`DashboardLayout.tsx`:
```tsx
import { useState } from "react";
import { IconSidebar } from "./IconSidebar";
import { ScanListPanel } from "./ScanListPanel";
import { ScanDetailPanel } from "../scans/ScanDetailPanel";
import { WelcomePanel } from "../scans/WelcomePanel";
import { ScanWizardPanel } from "../wizard/ScanWizardPanel";

export function DashboardLayout() {
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const selectScan = (id: number) => { setWizardOpen(false); setSelectedScanId(id); };

  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar onOpenScans={() => setWizardOpen(false)} />
      <ScanListPanel
        selectedScanId={selectedScanId}
        onSelect={selectScan}
        onNewScan={() => { setSelectedScanId(null); setWizardOpen(true); }}
      />
      {wizardOpen ? (
        <ScanWizardPanel
          onClose={() => setWizardOpen(false)}
          onCreated={(id) => { setWizardOpen(false); setSelectedScanId(id); }}
        />
      ) : selectedScanId != null ? (
        <ScanDetailPanel scanId={selectedScanId} />
      ) : (
        <WelcomePanel />
      )}
    </div>
  );
}
```

- [ ] **Step 6: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout frontend/src/components/scans frontend/src/components/wizard
git commit -m "feat(ui): dashboard layout shell + icon sidebar"
```

---

### Task 12: ScanListPanel + ScanListItem + EmptyState

**Files:**
- Modify: `frontend/src/components/layout/ScanListPanel.tsx`
- Create: `frontend/src/components/layout/ScanListItem.tsx`, `frontend/src/components/layout/EmptyState.tsx`
- Test: `frontend/src/components/layout/ScanListPanel.test.tsx`

**Interfaces:**
- Consumes: `useScans()`, `Scan`, `StatusDot`, `Button`, `dateRange`.
- `ScanListPanel` props: `{ selectedScanId: number|null; onSelect(id:number):void; onNewScan():void }`. Header "Scans" + "+" button (calls `onNewScan`). Loading → Spinner. Empty → `EmptyState`. Otherwise list of `ScanListItem`.
- `ScanListItem` props: `{ scan: Scan; selected: boolean; onClick():void }`. Shows StatusDot (active→success, paused→warning), name (or `${provider} #${rec_area_ids?.[0] ?? id}` fallback), first search window range. Selected → left border `border-forest-600` + `bg-forest-50`.
- `EmptyState` props: `{ onNewScan():void }`.

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ScanListPanel } from "./ScanListPanel";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

describe("ScanListPanel", () => {
  it("renders scans and fires onSelect", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([scan])));
    const onSelect = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={onSelect} onNewScan={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Yosemite")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Yosemite"));
    expect(onSelect).toHaveBeenCalledWith(7);
  });

  it("shows empty state when no scans", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([])));
    const onNewScan = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={vi.fn()} onNewScan={onNewScan} />);
    await waitFor(() => expect(screen.getByText(/no scans yet/i)).toBeInTheDocument());
  });

  it("calls onNewScan from header + button", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([scan])));
    const onNewScan = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={vi.fn()} onNewScan={onNewScan} />);
    await waitFor(() => screen.getByText("Yosemite"));
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onNewScan).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/layout/ScanListPanel.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ScanListItem.tsx`**

```tsx
import { cn } from "../../lib/cn";
import { StatusDot } from "../ui/StatusDot";
import { dateRange } from "../../lib/format";
import type { Scan, ScanStatus } from "../../types";

export function scanTitle(scan: Scan): string {
  return scan.name?.trim() || `${scan.provider} #${scan.rec_area_ids?.[0] ?? scan.id}`;
}

export function scanStatusTone(status: ScanStatus): "success" | "warning" | "neutral" {
  switch (status) {
    case "active": return "success";
    case "paused": return "warning";
    case "completed": return "neutral";
  }
}

export function ScanListItem({ scan, selected, onClick }: {
  scan: Scan; selected: boolean; onClick: () => void;
}) {
  const window = scan.search_windows[0];
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full flex-col items-start gap-1 border-l-2 px-3 py-2.5 text-left transition-colors",
        selected
          ? "border-forest-600 bg-forest-50 dark:bg-[#222]"
          : "border-transparent hover:bg-sand-100 dark:hover:bg-[#1f1f1f]"
      )}
    >
      <span className="flex items-center gap-2">
        <StatusDot tone={scanStatusTone(scan.status)} />
        <span className="truncate text-sm font-medium text-stone-800 dark:text-[#EEE]">
          {scanTitle(scan)}
        </span>
      </span>
      {window && (
        <span className="pl-4 text-xs text-stone-500 dark:text-[#888]">
          {dateRange(window.start_date, window.end_date)}
        </span>
      )}
    </button>
  );
}
```

- [ ] **Step 4: Implement `EmptyState.tsx`**

```tsx
import { Button } from "../ui/Button";

export function EmptyState({ onNewScan }: { onNewScan: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-3xl" aria-hidden>⛺</span>
      <p className="text-sm text-stone-500 dark:text-[#888]">No scans yet</p>
      <Button size="sm" onClick={onNewScan}>+ New Scan</Button>
    </div>
  );
}
```

- [ ] **Step 5: Implement `ScanListPanel.tsx`**

```tsx
import { useScans } from "../../hooks/useScans";
import { ScanListItem } from "./ScanListItem";
import { EmptyState } from "./EmptyState";
import { Spinner } from "../ui/Spinner";

export function ScanListPanel({ selectedScanId, onSelect, onNewScan }: {
  selectedScanId: number | null;
  onSelect: (id: number) => void;
  onNewScan: () => void;
}) {
  const { data: scans, isLoading } = useScans();

  return (
    <aside className="flex w-60 flex-col border-r border-sand-200 bg-white dark:border-[#222] dark:bg-[#1A1A1A]">
      <header className="flex items-center justify-between border-b border-sand-200 px-3 py-3 dark:border-[#222]">
        <h2 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">Scans</h2>
        <button
          aria-label="New scan"
          onClick={onNewScan}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700"
        >
          +
        </button>
      </header>
      <div className="flex flex-1 flex-col overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-1 items-center justify-center"><Spinner /></div>
        ) : !scans || scans.length === 0 ? (
          <EmptyState onNewScan={onNewScan} />
        ) : (
          scans.map((scan) => (
            <ScanListItem
              key={scan.id}
              scan={scan}
              selected={scan.id === selectedScanId}
              onClick={() => onSelect(scan.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
```

> The empty-state test queries `/no scans yet/i`, and the "New scan" header button has `aria-label="New scan"` satisfying `name: /new scan/i`.

- [ ] **Step 6: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run src/components/layout`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout
git commit -m "feat(ui): scan list panel, list item, empty state"
```

---

### Task 13: ScanDetailPanel shell + header + WelcomePanel

**Files:**
- Modify: `frontend/src/components/scans/ScanDetailPanel.tsx`, `frontend/src/components/scans/WelcomePanel.tsx`
- Create: `frontend/src/components/scans/ScanDetailHeader.tsx`
- Test: `frontend/src/components/scans/ScanDetailHeader.test.tsx`

**Interfaces:**
- `ScanDetailPanel` props `{ scanId: number }`. Uses `useScan(scanId)`. Owns `activeTab` state (`"overview"|"results"|"runs"|"settings"`, default `"overview"`). Renders `ScanDetailHeader`, `Tabs`, and the active tab body (tab bodies stubbed here, built Tasks 14–17). On delete success, this panel cannot clear parent selection itself — it calls an `onDeleted` prop. Add `onDeleted?: () => void` to props and wire it from DashboardLayout (update DashboardLayout to pass `onDeleted={() => setSelectedScanId(null)}`).
- `ScanDetailHeader` props `{ scan: Scan; onDeleted():void }`. Uses `usePauseScan`, `useResumeScan`, `useDeleteScan`. Shows StatusDot + title, metadata line (`provider · rec areas · {nights} nights`), buttons: Pause/Resume (toggles by status), Edit (no-op placeholder for now — wired in Task 17 by switching tab to settings; accept `onEdit?:()=>void`), Delete (confirm via `window.confirm`, then mutate + `onDeleted`).

- [ ] **Step 1: Write failing test for ScanDetailHeader**

```tsx
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ScanDetailHeader } from "./ScanDetailHeader";

const scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
} as const;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanDetailHeader", () => {
  it("pauses an active scan", async () => {
    let paused = false;
    server.use(http.post("/api/v1/scans/7/pause", () => {
      paused = true;
      return HttpResponse.json({ ...scan, status: "paused" });
    }));
    wrap(<ScanDetailHeader scan={scan} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /pause/i }));
    await waitFor(() => expect(paused).toBe(true));
  });

  it("deletes after confirm and calls onDeleted", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    server.use(http.delete("/api/v1/scans/7", () => new HttpResponse(null, { status: 204 })));
    const onDeleted = vi.fn();
    wrap(<ScanDetailHeader scan={scan} onDeleted={onDeleted} onEdit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /delete/i }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/ScanDetailHeader.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ScanDetailHeader.tsx`**

```tsx
import { usePauseScan, useResumeScan, useDeleteScan } from "../../hooks/useScans";
import { StatusDot } from "../ui/StatusDot";
import { Button } from "../ui/Button";
import { scanTitle, scanStatusTone } from "../layout/ScanListItem";
import type { Scan } from "../../types";

export function ScanDetailHeader({ scan, onDeleted, onEdit }: {
  scan: Scan; onDeleted: () => void; onEdit: () => void;
}) {
  const pause = usePauseScan();
  const resume = useResumeScan();
  const del = useDeleteScan();
  const isActive = scan.status === "active";

  const meta = [
    scan.provider,
    scan.rec_area_ids?.length ? `areas ${scan.rec_area_ids.join(", ")}` : null,
    `${scan.nights} night${scan.nights === 1 ? "" : "s"}`,
  ].filter(Boolean).join(" · ");

  async function onDelete() {
    if (!window.confirm(`Delete scan "${scanTitle(scan)}"? This removes all its history.`)) return;
    await del.mutateAsync(scan.id);
    onDeleted();
  }

  return (
    <header className="flex items-start justify-between border-b border-sand-200 px-6 py-4 dark:border-[#222]">
      <div>
        <div className="flex items-center gap-2">
          <StatusDot tone={scanStatusTone(scan.status)} />
          <h1 className="text-xl font-bold text-stone-900 dark:text-[#EEE]">{scanTitle(scan)}</h1>
        </div>
        <p className="mt-1 text-sm text-stone-500 dark:text-[#888]">{meta}</p>
      </div>
      <div className="flex gap-2">
        {isActive ? (
          <Button variant="secondary" size="sm" disabled={pause.isPending}
            onClick={() => pause.mutate(scan.id)}>Pause</Button>
        ) : (
          <Button variant="secondary" size="sm" disabled={resume.isPending}
            onClick={() => resume.mutate(scan.id)}>Resume</Button>
        )}
        <Button variant="secondary" size="sm" onClick={onEdit}>Edit</Button>
        <Button variant="danger" size="sm" disabled={del.isPending} onClick={onDelete}>Delete</Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/scans/ScanDetailHeader.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement `ScanDetailPanel.tsx` (tab bodies stubbed)**

Create stubs for the four tab components (refined in Tasks 14–17):
- `src/components/scans/OverviewTab.tsx`: `export function OverviewTab(_:{scan:import("../../types").Scan}){return <div />;}`
- `src/components/scans/ResultsTab.tsx`: `export function ResultsTab(_:{scanId:number}){return <div />;}`
- `src/components/scans/RunHistoryTab.tsx`: `export function RunHistoryTab(_:{scanId:number}){return <div />;}`
- `src/components/scans/SettingsTab.tsx`: `export function SettingsTab(_:{scan:import("../../types").Scan}){return <div />;}`

```tsx
import { useState } from "react";
import { useScan } from "../../hooks/useScans";
import { Tabs } from "../ui/Tabs";
import { Spinner } from "../ui/Spinner";
import { ScanDetailHeader } from "./ScanDetailHeader";
import { OverviewTab } from "./OverviewTab";
import { ResultsTab } from "./ResultsTab";
import { RunHistoryTab } from "./RunHistoryTab";
import { SettingsTab } from "./SettingsTab";

type TabId = "overview" | "results" | "runs" | "settings";
const TABS = [
  { id: "overview", label: "Overview" },
  { id: "results", label: "Results" },
  { id: "runs", label: "Run History" },
  { id: "settings", label: "Settings" },
];

export function ScanDetailPanel({ scanId, onDeleted }: { scanId: number; onDeleted: () => void }) {
  const { data: scan, isLoading } = useScan(scanId);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  if (isLoading || !scan)
    return <div className="flex flex-1 items-center justify-center"><Spinner /></div>;

  return (
    <section className="flex flex-1 flex-col overflow-hidden">
      <ScanDetailHeader scan={scan} onDeleted={onDeleted} onEdit={() => setActiveTab("settings")} />
      <div className="px-6">
        <Tabs tabs={TABS} active={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {activeTab === "overview" && <OverviewTab scan={scan} />}
        {activeTab === "results" && <ResultsTab scanId={scan.id} />}
        {activeTab === "runs" && <RunHistoryTab scanId={scan.id} />}
        {activeTab === "settings" && <SettingsTab scan={scan} />}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Update `DashboardLayout.tsx` to pass `onDeleted`**

Change the `ScanDetailPanel` usage to:
```tsx
<ScanDetailPanel scanId={selectedScanId} onDeleted={() => setSelectedScanId(null)} />
```

- [ ] **Step 7: Implement `WelcomePanel.tsx`**

```tsx
export function WelcomePanel() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <span className="text-5xl" aria-hidden>🏕️</span>
      <h2 className="text-lg font-semibold text-stone-700 dark:text-[#CCC]">Welcome to CampBuddy</h2>
      <p className="max-w-xs text-sm text-stone-500 dark:text-[#888]">
        Select a scan from the list, or create a new one to start monitoring campsite availability.
      </p>
    </div>
  );
}
```

- [ ] **Step 8: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/scans frontend/src/components/layout/DashboardLayout.tsx
git commit -m "feat(ui): scan detail shell, header actions, welcome panel"
```

---

### Task 14: OverviewTab (StatsRow, RunHealthBar, SearchWindowsList)

**Files:**
- Modify: `frontend/src/components/scans/OverviewTab.tsx`
- Create: `frontend/src/components/scans/StatsRow.tsx`, `RunHealthBar.tsx`, `SearchWindowsList.tsx`
- Test: `frontend/src/components/scans/RunHealthBar.test.tsx`

**Interfaces:**
- `OverviewTab` props `{ scan: Scan }`. Fetches first page of runs (`useScanRuns(scan.id, 1)`) and results (`useScanResults(scan.id, 1)`) to compute stats. Renders `StatsRow`, `RunHealthBar`, `SearchWindowsList`.
- `StatsRow` props `{ sitesFound: number; inCart: number; totalRuns: number; successRate: number }`. 4 cards.
- `RunHealthBar` props `{ runs: ScanRun[] }`. Renders up to 20 vertical bars (oldest→newest, so reverse the desc list), colored by outcome, each with `title` tooltip = `${relativeTime(started_at)} · ${outcomeLabel}`.
- `SearchWindowsList` props `{ windows: SearchWindow[] }`. Date-range chips.
- Helper `outcomeLabel(outcome): string` and `outcomeTone(outcome): "success"|"warning"|"error"|"neutral"` — define in `RunHealthBar.tsx` and export for reuse by RunHistoryTab.

- [ ] **Step 1: Write failing test for RunHealthBar**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunHealthBar } from "./RunHealthBar";

const runs = [
  { id: 2, scan_id: 1, started_at: "2026-06-24T11:00:00Z", finished_at: "2026-06-24T11:00:05Z", outcome: "success", sites_found: 3, error_message: null },
  { id: 1, scan_id: 1, started_at: "2026-06-24T10:00:00Z", finished_at: "2026-06-24T10:00:04Z", outcome: "error", sites_found: 0, error_message: "boom" },
] as const;

describe("RunHealthBar", () => {
  it("renders one bar per run with a tooltip", () => {
    render(<RunHealthBar runs={[...runs]} />);
    const bars = screen.getAllByTitle(/ago|now/);
    expect(bars).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/RunHealthBar.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `RunHealthBar.tsx`**

```tsx
import { cn } from "../../lib/cn";
import { relativeTime } from "../../lib/format";
import type { RunOutcome, ScanRun } from "../../types";

export function outcomeLabel(outcome: RunOutcome | null): string {
  switch (outcome) {
    case "success": return "Success";
    case "no_results": return "No Results";
    case "error": return "Error";
    default: return "Running";
  }
}

export function outcomeTone(outcome: RunOutcome | null): "success" | "warning" | "error" | "neutral" {
  switch (outcome) {
    case "success": return "success";
    case "no_results": return "warning";
    case "error": return "error";
    default: return "neutral";
  }
}

const barColor: Record<string, string> = {
  success: "bg-[#22C55E]", warning: "bg-[#EAB308]", error: "bg-[#DC2626]", neutral: "bg-stone-300 dark:bg-[#333]",
};

export function RunHealthBar({ runs }: { runs: ScanRun[] }) {
  const ordered = [...runs].slice(0, 20).reverse(); // oldest → newest
  if (ordered.length === 0)
    return <p className="text-sm text-stone-400">No runs yet</p>;
  return (
    <div className="flex items-end gap-1">
      {ordered.map((run) => (
        <span
          key={run.id}
          title={`${relativeTime(run.started_at)} · ${outcomeLabel(run.outcome)}`}
          className={cn("h-8 w-2 rounded-sm", barColor[outcomeTone(run.outcome)])}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/scans/RunHealthBar.test.tsx`
Expected: PASS.

- [ ] **Step 5: Implement `StatsRow.tsx`**

```tsx
function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <p className="text-xs uppercase tracking-wide text-stone-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone ?? "text-stone-900 dark:text-[#EEE]"}`}>{value}</p>
    </div>
  );
}

export function StatsRow({ sitesFound, inCart, totalRuns, successRate }: {
  sitesFound: number; inCart: number; totalRuns: number; successRate: number;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Sites Found" value={String(sitesFound)} tone="text-[#60A5FA]" />
      <Stat label="In Cart" value={String(inCart)} tone="text-campfire-600" />
      <Stat label="Total Runs" value={String(totalRuns)} />
      <Stat label="Success Rate" value={`${successRate}%`} tone="text-[#22C55E]" />
    </div>
  );
}
```

- [ ] **Step 6: Implement `SearchWindowsList.tsx`**

```tsx
import { dateRange } from "../../lib/format";
import type { SearchWindow } from "../../types";

export function SearchWindowsList({ windows }: { windows: SearchWindow[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Search Windows</h3>
      <div className="flex flex-wrap gap-2">
        {windows.map((w, i) => (
          <span key={i}
            className="rounded-full bg-sand-100 px-3 py-1 text-sm text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
            {dateRange(w.start_date, w.end_date)}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Implement `OverviewTab.tsx`**

```tsx
import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { SearchWindowsList } from "./SearchWindowsList";
import type { Scan } from "../../types";

export function OverviewTab({ scan }: { scan: Scan }) {
  const { data: stats } = useScanStats(scan.id);
  const { data: runs = [] } = useScanRuns(scan.id, 1); // first page powers the health bar

  return (
    <div className="space-y-6">
      <StatsRow
        sitesFound={stats?.sites_found ?? 0}
        inCart={stats?.in_cart ?? 0}
        totalRuns={stats?.total_runs ?? 0}
        successRate={stats?.success_rate ?? 0}
      />
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Recent Run Health</h3>
        <RunHealthBar runs={runs} />
      </div>
      <SearchWindowsList windows={scan.search_windows} />
    </div>
  );
}
```

> Stats come from the real aggregate endpoint `GET /scans/{id}/stats` (`useScanStats`), computed across ALL runs/results server-side — no first-page approximation. The run health bar still uses the first page of runs (the last ≤20 runs) for its visualization. Update the OverviewTab test to mock `GET /api/v1/scans/{id}/stats` returning `{sites_found, in_cart, total_runs, success_rate}` and assert the StatsRow reflects those values.

- [ ] **Step 8: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/scans
git commit -m "feat(ui): overview tab — stats, run health bar, search windows"
```

---

### Task 15: ResultsTab + ResultCard

**Files:**
- Modify: `frontend/src/components/scans/ResultsTab.tsx`
- Create: `frontend/src/components/scans/ResultCard.tsx`
- Test: `frontend/src/components/scans/ResultsTab.test.tsx`

**Interfaces:**
- `ResultsTab` props `{ scanId: number }`. Owns `page` state. Uses `useScanResults(scanId, page)`. `hasNext = data.length === RESULTS_PAGE_SIZE`. Renders list of `ResultCard` + `Pagination`. Loading→Spinner, empty→"No results yet".
- `ResultCard` props `{ result: ScanResult }`. Shows site name + facility, booking date range + campsite type, cart badge (accent "In cart" if `cart_added` else neutral "Not in cart"), "Book →" link (`href=booking_url` target=_blank rel=noopener).

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ResultsTab } from "./ResultsTab";

const result = {
  id: 1, scan_id: 7, campsite_id: "A1", facility_name: "Upper Pines", site_name: "Site 42",
  campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03",
  booking_url: "https://recreation.gov/x", first_seen_at: "2026-06-24T11:00:00Z",
  cart_added: true, notified: true,
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ResultsTab", () => {
  it("renders result cards with a booking link and cart badge", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([result])));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByText(/in cart/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /book/i })).toHaveAttribute("href", "https://recreation.gov/x");
  });

  it("shows empty state when no results", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([])));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText(/no results yet/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/ResultsTab.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ResultCard.tsx`**

```tsx
import { Badge } from "../ui/Badge";
import { dateRange } from "../../lib/format";
import type { ScanResult } from "../../types";

export function ResultCard({ result }: { result: ScanResult }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="space-y-1">
        <p className="font-medium text-stone-900 dark:text-[#EEE]">{result.site_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">{result.facility_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          {dateRange(result.booking_date, result.booking_end_date)} · {result.campsite_type}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        {result.cart_added ? <Badge tone="accent">In cart</Badge> : <Badge tone="neutral">Not in cart</Badge>}
        <a href={result.booking_url} target="_blank" rel="noopener noreferrer"
          className="text-sm font-medium text-forest-700 hover:underline dark:text-forest-400">
          Book →
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `ResultsTab.tsx`**

```tsx
import { useState } from "react";
import { useScanResults, RESULTS_PAGE_SIZE } from "../../hooks/useResults";
import { ResultCard } from "./ResultCard";
import { Pagination } from "../ui/Pagination";
import { Spinner } from "../ui/Spinner";

export function ResultsTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const { data: results, isLoading } = useScanResults(scanId, page);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!results || results.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No results yet</p>;

  return (
    <div className="space-y-3">
      {results.map((r) => <ResultCard key={r.id} result={r} />)}
      <Pagination
        page={page}
        hasNext={results.length === RESULTS_PAGE_SIZE}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}
```

- [ ] **Step 5: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run src/components/scans/ResultsTab.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/scans/ResultsTab.tsx frontend/src/components/scans/ResultCard.tsx
git commit -m "feat(ui): results tab with cards + pagination"
```

---

### Task 16: RunHistoryTab + RunRow

**Files:**
- Modify: `frontend/src/components/scans/RunHistoryTab.tsx`
- Create: `frontend/src/components/scans/RunRow.tsx`
- Test: `frontend/src/components/scans/RunHistoryTab.test.tsx`

**Interfaces:**
- `RunHistoryTab` props `{ scanId: number }`. Owns `page`. Uses `useScanRuns(scanId, page)`. `hasNext = data.length === RUNS_PAGE_SIZE`. List of `RunRow` + `Pagination`. Empty → "No runs yet".
- `RunRow` props `{ run: ScanRun }`. StatusDot via `outcomeTone`, relative timestamp, `outcomeLabel`, sites count, duration. If `error_message`, an expandable `<details>` showing it.

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { RunHistoryTab } from "./RunHistoryTab";

const run = {
  id: 1, scan_id: 7, started_at: "2026-06-24T11:00:00Z", finished_at: "2026-06-24T11:00:08Z",
  outcome: "error", sites_found: 0, error_message: "provider timeout",
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("RunHistoryTab", () => {
  it("renders a run row with outcome and expandable error", async () => {
    server.use(http.get("/api/v1/scans/7/runs", () => HttpResponse.json([run])));
    wrap(<RunHistoryTab scanId={7} />);
    await waitFor(() => expect(screen.getByText(/error/i)).toBeInTheDocument());
    expect(screen.getByText(/provider timeout/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/RunHistoryTab.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `RunRow.tsx`**

```tsx
import { StatusDot } from "../ui/StatusDot";
import { relativeTime, duration } from "../../lib/format";
import { outcomeLabel, outcomeTone } from "./RunHealthBar";
import type { ScanRun } from "../../types";

export function RunRow({ run }: { run: ScanRun }) {
  return (
    <div className="border-b border-sand-200 py-3 dark:border-[#222]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusDot tone={outcomeTone(run.outcome)} />
          <span className="text-sm font-medium text-stone-800 dark:text-[#EEE]">
            {outcomeLabel(run.outcome)}
          </span>
          <span className="text-sm text-stone-400">{relativeTime(run.started_at)}</span>
        </div>
        <div className="flex gap-4 text-sm text-stone-500 dark:text-[#888]">
          <span>{run.sites_found} sites</span>
          <span>{duration(run.started_at, run.finished_at)}</span>
        </div>
      </div>
      {run.error_message && (
        <details className="mt-2 pl-6 text-sm text-[#DC2626]">
          <summary className="cursor-pointer select-none">Error details</summary>
          <pre className="mt-1 whitespace-pre-wrap break-words">{run.error_message}</pre>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Implement `RunHistoryTab.tsx`**

```tsx
import { useState } from "react";
import { useScanRuns, RUNS_PAGE_SIZE } from "../../hooks/useRuns";
import { RunRow } from "./RunRow";
import { Pagination } from "../ui/Pagination";
import { Spinner } from "../ui/Spinner";

export function RunHistoryTab({ scanId }: { scanId: number }) {
  const [page, setPage] = useState(1);
  const { data: runs, isLoading } = useScanRuns(scanId, page);

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;
  if (!runs || runs.length === 0)
    return <p className="py-8 text-center text-sm text-stone-400">No runs yet</p>;

  return (
    <div>
      {runs.map((r) => <RunRow key={r.id} run={r} />)}
      <Pagination
        page={page}
        hasNext={runs.length === RUNS_PAGE_SIZE}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}
```

- [ ] **Step 5: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run src/components/scans/RunHistoryTab.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/scans/RunHistoryTab.tsx frontend/src/components/scans/RunRow.tsx
git commit -m "feat(ui): run history tab with expandable errors"
```

---

### Task 17: ScanForm + SettingsTab (inline edit)

**Files:**
- Create: `frontend/src/components/scans/ScanForm.tsx`
- Modify: `frontend/src/components/scans/SettingsTab.tsx`
- Test: `frontend/src/components/scans/SettingsTab.test.tsx`

**Interfaces:**
- `ScanForm` is the shared, controlled form used by both the SettingsTab and the wizard steps. To keep the wizard split into 3 steps, the form fields are organized so the wizard can render subsets. Implement a single hook `useScanFormState(initial?: Partial<ScanCreatePayload>)` returning `{ state, set, toScanCreatePayload(), toScanUpdatePayload() }`.
  - Create this hook in `frontend/src/components/scans/useScanFormState.ts`.
  - `state` fields: `name: string`, `provider: string`, `recAreaIds: string`, `campgroundIds: string`, `campsiteIds: string`, `windows: SearchWindow[]`, `nights: number`, `daysOfWeek: number[]`, `weekendsOnly: boolean`, `pollingInterval: number`, `notifyEmail: boolean`, `notifyTelegram: boolean`, `notifyNewOnly: boolean`.
  - `set(key, value)` updates one field.
  - `parseIds(csv): number[] | null` — splits on commas, trims, drops empties, Number(); returns null if empty.
  - `toScanCreatePayload()` builds a `ScanCreatePayload`; `toScanUpdatePayload()` builds a `ScanUpdatePayload`.
- `SettingsTab` props `{ scan: Scan }`. Initializes `useScanFormState` from the scan, renders all fields (reusing field sub-components defined inline), Save button calls `useUpdateScan().mutate({ id, payload: toScanUpdatePayload() })`, shows "Saved" confirmation.

> The form is the most field-heavy unit. Build the state hook first (with a unit test for `parseIds`/payload building), then the visual form. The wizard (Task 18) reuses the same hook.

- [ ] **Step 1: Write failing test for the form state hook**

`src/components/scans/useScanFormState.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useScanFormState } from "./useScanFormState";

describe("useScanFormState", () => {
  it("parses comma-separated ids and builds a create payload", () => {
    const { result } = renderHook(() => useScanFormState());
    act(() => {
      result.current.set("provider", "RecreationDotGov");
      result.current.set("recAreaIds", "2991, 2992 ,");
      result.current.set("windows", [{ start_date: "2026-07-01", end_date: "2026-07-03" }]);
      result.current.set("nights", 2);
    });
    const payload = result.current.toScanCreatePayload();
    expect(payload.rec_area_ids).toEqual([2991, 2992]);
    expect(payload.search_windows).toHaveLength(1);
    expect(payload.nights).toBe(2);
  });

  it("omits empty id fields as null", () => {
    const { result } = renderHook(() => useScanFormState());
    const payload = result.current.toScanCreatePayload();
    expect(payload.campground_ids).toBeNull();
    expect(payload.campsite_ids).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/useScanFormState.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement `useScanFormState.ts`**

```ts
import { useState, useCallback } from "react";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, SearchWindow } from "../../types";

export interface ScanFormState {
  name: string;
  provider: string;
  recAreaIds: string;
  campgroundIds: string;
  campsiteIds: string;
  windows: SearchWindow[];
  nights: number;
  daysOfWeek: number[];
  weekendsOnly: boolean;
  pollingInterval: number;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyNewOnly: boolean;
}

function fromScan(scan?: Scan): ScanFormState {
  return {
    name: scan?.name ?? "",
    provider: scan?.provider ?? "RecreationDotGov",
    recAreaIds: scan?.rec_area_ids?.join(", ") ?? "",
    campgroundIds: scan?.campground_ids?.join(", ") ?? "",
    campsiteIds: scan?.campsite_ids?.join(", ") ?? "",
    windows: scan?.search_windows ?? [],
    nights: scan?.nights ?? 1,
    daysOfWeek: scan?.days_of_week ?? [],
    weekendsOnly: scan?.weekends_only ?? false,
    pollingInterval: scan?.polling_interval ?? 300,
    notifyEmail: scan?.notify_via_email ?? true,
    notifyTelegram: scan?.notify_via_telegram ?? false,
    notifyNewOnly: scan?.notify_on_new_only ?? true,
  };
}

function parseIds(csv: string): number[] | null {
  const ids = csv.split(",").map((s) => s.trim()).filter(Boolean).map(Number).filter((n) => !Number.isNaN(n));
  return ids.length ? ids : null;
}

export function useScanFormState(scan?: Scan) {
  const [state, setState] = useState<ScanFormState>(() => fromScan(scan));

  const set = useCallback(<K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toScanCreatePayload = (): ScanCreatePayload => ({
    provider: state.provider,
    name: state.name.trim() || null,
    polling_interval: state.pollingInterval,
    rec_area_ids: parseIds(state.recAreaIds),
    campground_ids: parseIds(state.campgroundIds),
    campsite_ids: parseIds(state.campsiteIds),
    search_windows: state.windows,
    nights: state.nights,
    days_of_week: state.daysOfWeek.length ? state.daysOfWeek : null,
    weekends_only: state.weekendsOnly,
    notify_via_email: state.notifyEmail,
    notify_via_telegram: state.notifyTelegram,
    notify_on_new_only: state.notifyNewOnly,
  });

  const toScanUpdatePayload = (): ScanUpdatePayload => {
    const { provider: _omit, ...rest } = toScanCreatePayload();
    return rest;
  };

  return { state, set, toScanCreatePayload, toScanUpdatePayload };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/scans/useScanFormState.test.ts`
Expected: PASS.

- [ ] **Step 5: Create shared field components in `ScanForm.tsx`**

These are the reusable field groups consumed by SettingsTab and the wizard steps.

```tsx
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import { PROVIDERS } from "../../types";
import type { ScanFormState } from "./useScanFormState";
import type { SearchWindow } from "../../types";

type Setter = <K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => void;

const DAYS = [
  { i: 0, label: "Mon" }, { i: 1, label: "Tue" }, { i: 2, label: "Wed" },
  { i: 3, label: "Thu" }, { i: 4, label: "Fri" }, { i: 5, label: "Sat" }, { i: 6, label: "Sun" },
];

const POLLING_OPTIONS = [
  { value: "60", label: "1 min" }, { value: "300", label: "5 min" },
  { value: "600", label: "10 min" }, { value: "900", label: "15 min" },
  { value: "1800", label: "30 min" },
];

export function ProviderSitesFields({ state, set }: { state: ScanFormState; set: Setter }) {
  return (
    <div className="space-y-4">
      <Input label="Scan name (optional)" value={state.name}
        onChange={(e) => set("name", e.target.value)} placeholder="Yosemite summer trip" />
      <Select label="Provider" value={state.provider} onChange={(v) => set("provider", v)}
        options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
      <Input label="Recreation Area IDs (comma-separated)" value={state.recAreaIds}
        onChange={(e) => set("recAreaIds", e.target.value)} placeholder="2991, 2992" />
      <Input label="Campground IDs (optional)" value={state.campgroundIds}
        onChange={(e) => set("campgroundIds", e.target.value)} />
      <Input label="Campsite IDs (optional)" value={state.campsiteIds}
        onChange={(e) => set("campsiteIds", e.target.value)} />
    </div>
  );
}

export function DatesFiltersFields({ state, set }: { state: ScanFormState; set: Setter }) {
  const updateWindow = (idx: number, patch: Partial<SearchWindow>) =>
    set("windows", state.windows.map((w, i) => (i === idx ? { ...w, ...patch } : w)));
  const addWindow = () => set("windows", [...state.windows, { start_date: "", end_date: "" }]);
  const removeWindow = (idx: number) => set("windows", state.windows.filter((_, i) => i !== idx));
  const toggleDay = (d: number) =>
    set("daysOfWeek", state.daysOfWeek.includes(d)
      ? state.daysOfWeek.filter((x) => x !== d)
      : [...state.daysOfWeek, d]);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <span className="block text-sm text-stone-600 dark:text-[#888]">Search windows</span>
        {state.windows.map((w, i) => (
          <div key={i} className="flex items-end gap-2">
            <Input type="date" value={w.start_date} onChange={(e) => updateWindow(i, { start_date: e.target.value })} />
            <Input type="date" value={w.end_date} onChange={(e) => updateWindow(i, { end_date: e.target.value })} />
            <Button type="button" variant="ghost" size="sm" onClick={() => removeWindow(i)}>Remove</Button>
          </div>
        ))}
        <Button type="button" variant="secondary" size="sm" onClick={addWindow}>+ Add window</Button>
      </div>
      <Input label="Consecutive nights" type="number" min={1} value={state.nights}
        onChange={(e) => set("nights", Math.max(1, Number(e.target.value) || 1))} />
      <div>
        <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">Days of week</span>
        <div className="flex flex-wrap gap-1.5">
          {DAYS.map((d) => (
            <button key={d.i} type="button" onClick={() => toggleDay(d.i)}
              className={`rounded-full px-3 py-1 text-sm ${
                state.daysOfWeek.includes(d.i)
                  ? "bg-forest-600 text-white"
                  : "bg-sand-100 text-stone-600 dark:bg-[#222] dark:text-[#AAA]"
              }`}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
      <Toggle label="Weekends only" checked={state.weekendsOnly} onChange={(v) => set("weekendsOnly", v)} />
    </div>
  );
}

export function NotificationsFields({ state, set, telegramAvailable }: {
  state: ScanFormState; set: Setter; telegramAvailable: boolean;
}) {
  return (
    <div className="space-y-4">
      <Select label="Polling interval" value={String(state.pollingInterval)}
        onChange={(v) => set("pollingInterval", Number(v))} options={POLLING_OPTIONS} />
      <Toggle label="Notify via email" checked={state.notifyEmail} onChange={(v) => set("notifyEmail", v)} />
      <Toggle label="Notify via Telegram" checked={state.notifyTelegram}
        disabled={!telegramAvailable} onChange={(v) => set("notifyTelegram", v)} />
      <Toggle label="Notify on new sites only" checked={state.notifyNewOnly}
        onChange={(v) => set("notifyNewOnly", v)} />
    </div>
  );
}
```

- [ ] **Step 6: Write failing test for SettingsTab**

`src/components/scans/SettingsTab.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0, has_telegram: true } }),
}));
import { SettingsTab } from "./SettingsTab";

const scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
} as const;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("SettingsTab", () => {
  it("saves edits via PATCH", async () => {
    let patched: any = null;
    server.use(http.patch("/api/v1/scans/7", async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json({ ...scan, name: patched.name });
    }));
    wrap(<SettingsTab scan={scan} />);
    const nameInput = screen.getByDisplayValue("Yosemite");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Yosemite Fall");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(patched?.name).toBe("Yosemite Fall"));
  });
});
```

- [ ] **Step 7: Implement `SettingsTab.tsx`**

```tsx
import { useState } from "react";
import { useScanFormState } from "./useScanFormState";
import { ProviderSitesFields, DatesFiltersFields, NotificationsFields } from "./ScanForm";
import { Button } from "../ui/Button";
import { useUpdateScan } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";
import type { Scan } from "../../types";

export function SettingsTab({ scan }: { scan: Scan }) {
  const form = useScanFormState(scan);
  const update = useUpdateScan();
  const { user } = useAuth();
  const [saved, setSaved] = useState(false);

  async function onSave() {
    setSaved(false);
    await update.mutateAsync({ id: scan.id, payload: form.toScanUpdatePayload() });
    setSaved(true);
  }

  return (
    <div className="max-w-xl space-y-6">
      <ProviderSitesFields state={form.state} set={form.set} />
      <DatesFiltersFields state={form.state} set={form.set} />
      <NotificationsFields state={form.state} set={form.set} telegramAvailable={!!user?.has_telegram} />
      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
        {saved && <span className="text-sm text-[#22C55E]">Saved</span>}
        {update.isError && <span className="text-sm text-[#DC2626]">Save failed</span>}
      </div>
    </div>
  );
}
```

> Note: the provider field is shown but PATCH omits it (`toScanUpdatePayload` strips provider — the API's `ScanUpdate` has no provider field). That's intentional; provider is fixed after creation.

- [ ] **Step 8: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run src/components/scans`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/scans
git commit -m "feat(ui): shared scan form state + inline settings tab editing"
```

---

## Phase E — Creation Wizard

### Task 18: ScanWizardPanel + steps + VerticalStepIndicator

**Files:**
- Modify: `frontend/src/components/wizard/ScanWizardPanel.tsx`
- Create: `frontend/src/components/wizard/VerticalStepIndicator.tsx`
- Test: `frontend/src/components/wizard/ScanWizardPanel.test.tsx`

**Interfaces:**
- `ScanWizardPanel` props `{ onClose():void; onCreated(id:number):void }`. Owns `step` state (0,1,2) and a single `useScanFormState()`. Reuses the field groups from `ScanForm.tsx` for each step (Step1=ProviderSites, Step2=DatesFilters, Step3=Notifications). Telegram availability comes from `useAuth().user?.has_telegram` (the `/auth/me` response now includes `has_telegram`). Navigation: Back/Next; on final step "Create Scan" calls `useCreateScan().mutateAsync(toScanCreatePayload())` then `onCreated(scan.id)`. Cancel calls `onClose`. Basic validation: cannot advance past Step 1 without at least one of rec_area/campground/campsite ids; cannot create without ≥1 search window with both dates.
- `VerticalStepIndicator` props `{ steps: string[]; current: number }`.

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, email: "a@b.c", has_telegram: true } }) }));
import { ScanWizardPanel } from "./ScanWizardPanel";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanWizardPanel", () => {
  it("walks through the steps and creates a scan", async () => {
    server.use(http.post("/api/v1/scans", async ({ request }) => {
      const body: any = await request.json();
      expect(body.rec_area_ids).toEqual([2991]);
      return HttpResponse.json({ ...body, id: 99, user_id: 1, status: "active", created_at: "x" });
    }));
    const onCreated = vi.fn();
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={onCreated} />);

    // Step 1
    await userEvent.type(screen.getByLabelText(/recreation area ids/i), "2991");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    // Step 2 — add a window
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    // first two empty inputs are the date pickers
    await userEvent.type(dates[0], "2026-07-01");
    await userEvent.type(dates[1], "2026-07-03");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    // Step 3 — create
    await userEvent.click(screen.getByRole("button", { name: /create scan/i }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(99));
  });
});
```

> Note: this test is intentionally end-to-end across the three steps. If date `type` inputs are awkward in jsdom, set values via `fireEvent.change`. The test author may adjust selectors but must preserve the create-payload assertion.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/wizard/ScanWizardPanel.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `VerticalStepIndicator.tsx`**

```tsx
import { cn } from "../../lib/cn";

export function VerticalStepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="space-y-4">
      {steps.map((label, i) => (
        <li key={label} className="flex items-center gap-3">
          <span className={cn(
            "flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold",
            i < current ? "bg-forest-600 text-white"
              : i === current ? "border-2 border-forest-600 text-forest-700 dark:text-forest-400"
              : "border border-sand-200 text-stone-400 dark:border-[#333]"
          )}>
            {i < current ? "✓" : i + 1}
          </span>
          <span className={cn("text-sm", i === current ? "font-semibold text-stone-800 dark:text-[#EEE]" : "text-stone-400")}>
            {label}
          </span>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Implement `ScanWizardPanel.tsx`**

```tsx
import { useState } from "react";
import { useScanFormState } from "../scans/useScanFormState";
import { ProviderSitesFields, DatesFiltersFields, NotificationsFields } from "../scans/ScanForm";
import { VerticalStepIndicator } from "./VerticalStepIndicator";
import { Button } from "../ui/Button";
import { useCreateScan } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";

const STEPS = ["Provider & Sites", "Dates & Filters", "Notifications"];

export function ScanWizardPanel({ onClose, onCreated }: {
  onClose: () => void; onCreated: (id: number) => void;
}) {
  const form = useScanFormState();
  const create = useCreateScan();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const hasAnyIds = !!(form.state.recAreaIds.trim() || form.state.campgroundIds.trim() || form.state.campsiteIds.trim());
  const validWindows = form.state.windows.length > 0 && form.state.windows.every((w) => w.start_date && w.end_date);

  function next() {
    setError(null);
    if (step === 0 && !hasAnyIds) { setError("Enter at least one Recreation Area, Campground, or Campsite ID."); return; }
    setStep((s) => Math.min(2, s + 1));
  }

  async function onCreate() {
    setError(null);
    if (!validWindows) { setError("Add at least one search window with start and end dates."); return; }
    try {
      const scan = await create.mutateAsync(form.toScanCreatePayload());
      onCreated(scan.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create scan");
    }
  }

  return (
    <section className="flex flex-1 overflow-hidden">
      <div className="w-56 border-r border-sand-200 p-6 dark:border-[#222]">
        <h2 className="mb-6 text-sm font-semibold text-stone-800 dark:text-[#EEE]">New Scan</h2>
        <VerticalStepIndicator steps={STEPS} current={step} />
      </div>
      <div className="flex flex-1 flex-col overflow-y-auto p-6">
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

- [ ] **Step 5: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run src/components/wizard`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/wizard
git commit -m "feat(ui): scan creation wizard with 3 steps + validation"
```

---

## Phase F — Settings Page

### Task 19: SettingsPage + ProfileForm

**Files:**
- Modify: `frontend/src/components/settings/SettingsPage.tsx`
- Create: `frontend/src/components/settings/ProfileForm.tsx`
- Test: `frontend/src/components/settings/ProfileForm.test.tsx`

**Interfaces:**
- `SettingsPage`: full-screen page with `IconSidebar` on the left and the `ProfileForm` centered. (Reuses IconSidebar; pass `onOpenScans={() => navigate("/")}`.)
- `ProfileForm`: hydrates from `useProfile()` (`GET /users/me` → `{id, email, telegram_chat_id, recreationgov_email, scan_limit}`). While loading, show a Spinner; once loaded, render the controlled fields email, telegram_chat_id, recreationgov_email, recreationgov_password (masked with reveal toggle), pre-filled from the profile. The password is never returned by the API, so it always starts blank and is sent only when non-empty. Save calls `useUpdateProfile().mutateAsync(payload)` sending only changed/non-empty fields. Show "Saved" on success.

> Implementation pattern: split into an outer `ProfileForm` that calls `useProfile()` + Spinner gate, and an inner `ProfileFields({ profile })` whose `useState` initializes from the `profile` prop — this avoids `useEffect` state-sync. The recreation.gov password field is never hydrated (API never returns it).

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ProfileForm } from "./ProfileForm";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ProfileForm", () => {
  it("hydrates from GET /users/me, submits only changed fields, shows Saved", async () => {
    server.use(http.get("/api/v1/users/me", () =>
      HttpResponse.json({ id: 1, email: "a@b.c", telegram_chat_id: null, recreationgov_email: null, scan_limit: 5 })));
    let body: any = null;
    server.use(http.patch("/api/v1/users/me", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ id: 1, email: "a@b.c", telegram_chat_id: body.telegram_chat_id ?? null, recreationgov_email: null, scan_limit: 5 });
    }));
    wrap(<ProfileForm />);
    const telegram = await screen.findByLabelText(/telegram chat id/i); // waits for hydration
    await userEvent.type(telegram, "123456");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(body.telegram_chat_id).toBe("123456"));
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/ProfileForm.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ProfileForm.tsx`**

```tsx
import { useState } from "react";
import { useProfile, useUpdateProfile } from "../../hooks/useProfile";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { Toggle } from "../ui/Toggle";
import { Spinner } from "../ui/Spinner";
import type { Profile, ProfileUpdatePayload } from "../../types";

export function ProfileForm() {
  const { data: profile, isLoading } = useProfile();
  if (isLoading || !profile)
    return <div className="flex justify-center py-8"><Spinner /></div>;
  return <ProfileFields profile={profile} />;
}

function ProfileFields({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const [email, setEmail] = useState(profile.email);
  const [telegram, setTelegram] = useState(profile.telegram_chat_id ?? "");
  const [recEmail, setRecEmail] = useState(profile.recreationgov_email ?? "");
  const [recPassword, setRecPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [saved, setSaved] = useState(false);

  async function onSave() {
    setSaved(false);
    const payload: ProfileUpdatePayload = {};
    if (email && email !== profile.email) payload.email = email;
    if (telegram !== (profile.telegram_chat_id ?? "")) payload.telegram_chat_id = telegram;
    if (recEmail !== (profile.recreationgov_email ?? "")) payload.recreationgov_email = recEmail;
    if (recPassword) payload.recreationgov_password = recPassword;
    await update.mutateAsync(payload);
    setSaved(true);
    setRecPassword("");
  }

  return (
    <div className="w-full max-w-md space-y-4">
      <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Settings</h1>
      <Input label="Email address" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <Input label="Telegram Chat ID" value={telegram} onChange={(e) => setTelegram(e.target.value)} />
      <Input label="Recreation.gov email" type="email" value={recEmail}
        onChange={(e) => setRecEmail(e.target.value)} />
      <Input label="Recreation.gov password" type={showPassword ? "text" : "password"}
        value={recPassword} onChange={(e) => setRecPassword(e.target.value)}
        placeholder="Leave blank to keep current" />
      <Toggle label="Show password" checked={showPassword} onChange={setShowPassword} />
      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
        {saved && <span className="text-sm text-[#22C55E]">Saved</span>}
        {update.isError && <span className="text-sm text-[#DC2626]">Save failed</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `SettingsPage.tsx`**

```tsx
import { useNavigate } from "react-router-dom";
import { IconSidebar } from "../layout/IconSidebar";
import { ProfileForm } from "./ProfileForm";

export function SettingsPage() {
  const navigate = useNavigate();
  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar onOpenScans={() => navigate("/")} />
      <div className="flex flex-1 items-start justify-center overflow-y-auto p-10">
        <ProfileForm />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests + lint**

Run: `cd frontend && npm run lint && npx vitest run`
Expected: PASS (full suite).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings
git commit -m "feat(ui): settings page + profile form"
```

---

## Phase G — Docker & Integration

### Task 20: Dockerfile, nginx, compose service, README

**Files:**
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`, `frontend/public/favicon.svg`
- Modify: `docker-compose.yml`, `README.md` (add frontend dev/run notes)

**Interfaces:**
- Multi-stage Docker build: node 20 builds `dist/`, nginx serves it. nginx proxies `/api/` → `http://api:8000/api/` and SPA-fallbacks to `index.html`.
- compose `frontend` service builds `./frontend`, maps `127.0.0.1:3000:80`, depends on `api`.

- [ ] **Step 1: Create `frontend/public/favicon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#2E6F40"/><path d="M16 7 L26 25 H6 Z" fill="#FAF9F6"/><path d="M16 13 L21 25 H11 Z" fill="#2E6F40"/></svg>
```

- [ ] **Step 2: Create `frontend/nginx.conf`**

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://api:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

- [ ] **Step 3: Create `frontend/Dockerfile`**

```dockerfile
# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# --- serve stage ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 4: Create `frontend/.dockerignore`**

```
node_modules
dist
.git
*.local
```

- [ ] **Step 5: Add the `frontend` service to `docker-compose.yml`**

Append under `services:` (match existing indentation):
```yaml
  frontend:
    build: ./frontend
    ports:
      - "127.0.0.1:3000:80"
    depends_on:
      - api
    restart: unless-stopped
```

> Verify the existing `api` service is named `api` and listens on 8000 (the nginx `proxy_pass` and the spec assume this). If the API service has a different name/port, update `nginx.conf` `proxy_pass` accordingly before building.

- [ ] **Step 6: Verify production build succeeds**

Run: `cd frontend && npm run build`
Expected: `dist/` produced, no errors.

- [ ] **Step 7: Build the Docker image**

Run: `docker build -t campbuddy-frontend ./frontend`
Expected: image builds through both stages successfully.

- [ ] **Step 8: Update README**

Add a "Web UI" section documenting: `cd frontend && npm install && npm run dev` (dev server on :3000 proxying to API on :8000), `npm test`, and `docker compose up frontend`.

- [ ] **Step 9: Run full test suite + lint one final time**

Run: `cd frontend && npm run lint && npm test`
Expected: ALL PASS.

- [ ] **Step 10: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/.dockerignore frontend/public docker-compose.yml README.md
git commit -m "feat(ui): docker + nginx deployment and README docs"
```

---

## Self-Review Notes

- **Spec coverage:** Login (T9), 3 routes + ProtectedRoute (T7), three-panel layout + icon sidebar (T11), scan list + status dots + empty state (T12), detail header + actions (T13), Overview/Results/RunHistory/Settings tabs (T14–T17), creation wizard 3 steps (T18), settings/profile page (T19), light+dark mode (T5, applied throughout), Docker/nginx (T20). Color system encoded in T2 + Global Constraints. API client + cookie auth + pagination (T4, T10).
- **API gaps CLOSED (backend merged in 962d673):** (a) Overview stats use the real aggregate `GET /scans/{id}/stats` (`useScanStats`); (b) ProfileForm hydrates from `GET /users/me` (`useProfile`); (c) Telegram gate in wizard/settings uses the real `has_telegram` flag on `GET /auth/me`. Tasks 3, 4, 10, 14, 17, 18, 19 were amended accordingly.
- **Type consistency:** `scanTitle` defined once (T12) and reused (T13). `outcomeLabel`/`outcomeTone` defined once (T14) and reused (T16). `useScanFormState` defined once (T17) and reused by wizard (T18). `RESULTS_PAGE_SIZE`/`RUNS_PAGE_SIZE` exported from hooks (T10) and consumed in T15/T16.
- **Responsive:** desktop-first; `NaturePanel` hidden on mobile (`md:flex`), stats grid collapses `grid-cols-2 md:grid-cols-4`. Full single-panel mobile collapse of the three-panel layout is minimal in Phase 1 (panels remain side-by-side, horizontally scrollable on narrow screens) — note as a refinement if stricter mobile behavior is required.
