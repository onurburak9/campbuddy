import type { Page, Route } from "@playwright/test";

export const TEST_USER = {
  id: 1,
  email: "e2e@campbuddy.test",
  scan_limit: 5,
  scans_used: 0,
  has_telegram: false,
  is_admin: false,
};

export const YOSEMITE = { id: 2991, name: "Yosemite National Park", type: "Park", state: "CA" };

/** A YYYY-MM-DD date built from local parts, offset from today. */
export function isoDaysFromToday(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export type CreatedScanBody = Record<string, unknown>;

/**
 * Serves every /api/v1 call from a single handler so there is no route-ordering
 * ambiguity, and so an unstubbed call fails loudly instead of reaching the dead
 * dev-server proxy.
 */
export async function mockApi(
  page: Page,
  onCreateScan?: (body: CreatedScanBody) => void,
) {
  await page.addInitScript(() => {
    // Suppress the driver.js onboarding tours; their overlay swallows clicks.
    localStorage.setItem("campbuddy:tour-seen:welcome", "1");
    localStorage.setItem("campbuddy:tour-seen:wizard", "1");
    localStorage.setItem("campbuddy:tour-seen:wizard-dates", "1");
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (body: unknown) => route.fulfill({ json: body });

    if (path === "/auth/me") return json(TEST_USER);
    if (path === "/scans" && method === "GET") return json([]);
    if (path === "/scans" && method === "POST") {
      const body = route.request().postDataJSON() as CreatedScanBody;
      onCreateScan?.(body);
      return json({ ...body, id: 99, user_id: 1, status: "active", created_at: new Date().toISOString() });
    }
    if (path === "/search/recreation-areas" || path === "/search/recreation-areas/resolve") {
      return json([YOSEMITE]);
    }
    if (path.startsWith("/search/")) return json([]);
    if (path.startsWith("/scans/")) return json({});

    return route.fulfill({ status: 404, json: { detail: `unstubbed ${method} ${path}` } });
  });
}

/** Loads the dashboard and opens the new-scan wizard on its first step. */
export async function openWizard(page: Page) {
  await page.goto("/");
  // Targeted by data-tour rather than name: "New scan" also substring-matches
  // the empty-state's "+ New Scan" button once the scan list has loaded.
  const newScan = page.locator('[data-tour="new-scan-button"]');
  await newScan.waitFor();
  await newScan.click();
}

/** Completes step 1 (Provider & Sites) by adding a recreation area by ID. */
export async function completeProviderStep(page: Page) {
  await page.getByLabel("Add by ID").first().fill(String(YOSEMITE.id));
  await page.getByRole("button", { name: "Add", exact: true }).first().click();
  await page.getByRole("button", { name: "Next →" }).click();
}

/** Opens the nth search-window row's range-picker popover. */
export async function openWindowPicker(page: Page, index: number) {
  const name = index === 0 ? "Search dates" : `Search dates (range ${index + 1})`;
  await page.getByRole("button", { name }).click();
}

/**
 * Clicks a day (by ISO date) in the currently-open range-picker popover,
 * paging forward with "Next month" until the target day is rendered.
 */
export async function pickDay(page: Page, iso: string) {
  const cell = page.locator(`[data-day-iso="${iso}"]`);
  for (let i = 0; i < 24 && !(await cell.isVisible()); i++) {
    await page.getByRole("button", { name: "Next month" }).click();
  }
  await cell.click();
}

/** Closes the currently-open range-picker popover. */
export async function closeWindowPicker(page: Page) {
  await page.getByRole("button", { name: "Done" }).click();
}

/** Fills the nth search-window row via its range-picker calendar. */
export async function fillWindow(page: Page, index: number, start: string, end: string) {
  await openWindowPicker(page, index);
  await pickDay(page, start);
  await pickDay(page, end);
  await closeWindowPicker(page);
}

/** Current start/end values of every window's trigger, in DOM order. */
export async function dateValues(page: Page): Promise<string[]> {
  return page.locator("[data-start-date]").evaluateAll((els) =>
    els.flatMap((el) => [el.getAttribute("data-start-date") ?? "", el.getAttribute("data-end-date") ?? ""]),
  );
}

/** Weekday of a YYYY-MM-DD string, read at local noon to dodge UTC parsing. */
export function weekdayOf(iso: string): number {
  return new Date(`${iso}T12:00:00`).getDay();
}

export function nightsBetween(start: string, end: string): number {
  const ms = new Date(`${end}T12:00:00`).getTime() - new Date(`${start}T12:00:00`).getTime();
  return Math.round(ms / 86_400_000);
}
