import { test, expect } from "@playwright/test";
import {
  closeWindowPicker,
  completeProviderStep,
  fillWindow,
  isoDaysFromToday,
  mockApi,
  openWindowPicker,
  openWizard,
  pickDay,
} from "./support/app";

// Issue #51 — the wizard must not reach the Notifications step without at least
// one fully-specified window that has not already ended.
test.describe("scan wizard — search window validation", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await openWizard(page);
    await completeProviderStep(page);
    await expect(page.getByRole("button", { name: /add window/i })).toBeVisible();
  });

  test("blocks advancing when no search window has been added", async ({ page }) => {
    await page.getByRole("button", { name: "Next →" }).click();

    await expect(page.getByText("Add at least one search window with start and end dates.")).toBeVisible();
    await expect(page.getByRole("button", { name: /add window/i })).toBeVisible();
    await expect(page.getByLabel("Polling interval")).toBeHidden();
  });

  test("blocks advancing when a window is missing its end date", async ({ page }) => {
    await page.getByRole("button", { name: /add window/i }).click();
    await openWindowPicker(page, 0);
    await pickDay(page, isoDaysFromToday(14));
    await closeWindowPicker(page);
    await page.getByRole("button", { name: "Next →" }).click();

    await expect(page.getByText("Add at least one search window with start and end dates.")).toBeVisible();
    await expect(page.getByLabel("Polling interval")).toBeHidden();
  });

  test("blocks advancing when every window has already ended", async ({ page }) => {
    // The range picker can't select a past date directly, so this simulates
    // the realistic path instead: pick a valid near-future window, then let
    // time pass (the user leaves the wizard open) until it's ended.
    await page.getByRole("button", { name: /add window/i }).click();
    await fillWindow(page, 0, isoDaysFromToday(2), isoDaysFromToday(4));

    await page.clock.install();
    await page.clock.fastForward(6 * 24 * 60 * 60 * 1000); // +6 days, past the window's end
    // The blocking check is computed at render time, so force a re-render
    // after the clock jump rather than relying on one happening on its own.
    await page.getByRole("switch", { name: "Weekends only" }).click();
    await page.getByRole("button", { name: "Next →" }).click();

    await expect(page.getByText("At least one search window must end today or later.")).toBeVisible();
    await expect(page.getByLabel("Polling interval")).toBeHidden();
  });

  test("advances once a future window is added, and clears the error", async ({ page }) => {
    await page.getByRole("button", { name: "Next →" }).click();
    await expect(page.getByText("Add at least one search window with start and end dates.")).toBeVisible();

    await page.getByRole("button", { name: /add window/i }).click();
    await fillWindow(page, 0, isoDaysFromToday(14), isoDaysFromToday(16));
    await page.getByRole("button", { name: "Next →" }).click();

    await expect(page.getByLabel("Polling interval")).toBeVisible();
    await expect(page.getByText("Add at least one search window with start and end dates.")).toBeHidden();
  });

  test("creates the scan with the future window once validation passes", async ({ page }) => {
    const start = isoDaysFromToday(14);
    const end = isoDaysFromToday(16);
    await page.getByRole("button", { name: /add window/i }).click();
    await fillWindow(page, 0, start, end);
    await page.getByRole("button", { name: "Next →" }).click();

    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes("/api/v1/scans") && r.method() === "POST"),
      page.getByRole("button", { name: /create scan/i }).click(),
    ]);

    expect(request.postDataJSON().search_windows).toEqual([{ start_date: start, end_date: end }]);
  });
});
