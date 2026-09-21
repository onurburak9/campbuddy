import { test, expect } from "@playwright/test";
import {
  completeProviderStep,
  dateValues,
  isoDaysFromToday,
  mockApi,
  nightsBetween,
  openWizard,
  weekdayOf,
} from "./support/app";

const FRIDAY = 5;
const SUNDAY = 0;

// Issue #52 — quick-pick templates on the Dates & Filters step. Assertions are
// structural (weekday, span, month bounds) rather than re-deriving the same date
// arithmetic the implementation uses, so a bug there can't pass the test.
test.describe("scan wizard — quick-pick date templates", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await openWizard(page);
    await completeProviderStep(page);
    await expect(page.getByRole("button", { name: "Next weekend" })).toBeVisible();
  });

  test("'Next weekend' fills one future Friday-to-Sunday window", async ({ page }) => {
    await page.getByRole("button", { name: "Next weekend" }).click();

    const [start, end, ...rest] = await dateValues(page);
    expect(rest).toEqual([]);
    expect(weekdayOf(start)).toBe(FRIDAY);
    expect(weekdayOf(end)).toBe(SUNDAY);
    expect(nightsBetween(start, end)).toBe(2);
    expect(start > isoDaysFromToday(0)).toBe(true);
  });

  test("'Next 2 weekends' fills two Friday-to-Sunday windows a week apart", async ({ page }) => {
    await page.getByRole("button", { name: "Next 2 weekends" }).click();

    const values = await dateValues(page);
    expect(values).toHaveLength(4);
    const [firstStart, firstEnd, secondStart, secondEnd] = values;
    expect([firstStart, secondStart].map(weekdayOf)).toEqual([FRIDAY, FRIDAY]);
    expect([firstEnd, secondEnd].map(weekdayOf)).toEqual([SUNDAY, SUNDAY]);
    expect(nightsBetween(firstStart, secondStart)).toBe(7);
  });

  test("'All of <month>' spans the chosen month without enabling weekends-only", async ({ page }) => {
    const monthSelect = page.getByLabel("Month");
    const nextMonth = await monthSelect.locator("option").nth(1).getAttribute("value");
    await monthSelect.selectOption(nextMonth!);
    await page.getByRole("button", { name: /^All of / }).click();

    // Checks out on the 1st of the following month so the month's last night counts.
    const [year, month] = nextMonth!.split("-").map(Number);
    const checkout = new Date(year, month, 1);
    const checkoutIso = `${checkout.getFullYear()}-${String(checkout.getMonth() + 1).padStart(2, "0")}-01`;
    expect(await dateValues(page)).toEqual([`${nextMonth}-01`, checkoutIso]);
    await expect(page.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "false");
  });

  test("'Weekends in <month>' uses one month-long window plus the weekends-only filter", async ({ page }) => {
    const monthSelect = page.getByLabel("Month");
    const nextMonth = await monthSelect.locator("option").nth(1).getAttribute("value");
    await monthSelect.selectOption(nextMonth!);
    await page.getByRole("button", { name: /^Weekends in / }).click();

    expect(await dateValues(page)).toHaveLength(2);
    await expect(page.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByLabel("Consecutive nights")).toHaveValue("2");
  });

  test("summarises the config in nights, never surfacing the exclusive end date", async ({ page }) => {
    const monthSelect = page.getByLabel("Month");
    const nextMonth = await monthSelect.locator("option").nth(1).getAttribute("value");
    await monthSelect.selectOption(nextMonth!);
    await page.getByRole("button", { name: /^All of / }).click();

    const summary = page.getByTestId("search-summary");
    await expect(summary).toContainText(/^Any 1 night between /);
    // The window's end_date is the 1st of the following month; the summary must
    // talk about the last bookable night instead.
    const [year, month] = nextMonth!.split("-").map(Number);
    const followingMonth = new Date(year, month, 1).toLocaleDateString("en-US", { month: "short" });
    await expect(summary).not.toContainText(followingMonth);
  });

  test("keeps the summary in step when nights is edited after applying a template", async ({ page }) => {
    await page.getByRole("button", { name: "Next weekend" }).click();
    await expect(page.getByTestId("search-summary")).toContainText("2 nights");

    await page.getByLabel("Consecutive nights").fill("1");

    await expect(page.getByTestId("search-summary")).toContainText("Any 1 night between ");
  });

  test("applying a template replaces the existing windows rather than appending", async ({ page }) => {
    await page.getByRole("button", { name: "Next 2 weekends" }).click();
    expect(await dateValues(page)).toHaveLength(4);

    await page.getByRole("button", { name: "Next weekend" }).click();

    expect(await dateValues(page)).toHaveLength(2);
  });

  test("a generated window stays editable and removable", async ({ page }) => {
    await page.getByRole("button", { name: "Next weekend" }).click();
    const edited = isoDaysFromToday(40);
    await page.locator('input[type="date"]').first().fill(edited);
    expect((await dateValues(page))[0]).toBe(edited);

    await page.getByRole("button", { name: "Remove" }).click();
    expect(await dateValues(page)).toEqual([]);
  });

  test("a template satisfies the future-window guard and creates the scan", async ({ page }) => {
    await page.getByRole("button", { name: /^Weekends in / }).click();
    await page.getByRole("button", { name: "Next →" }).click();

    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes("/api/v1/scans") && r.method() === "POST"),
      page.getByRole("button", { name: /create scan/i }).click(),
    ]);
    const body = request.postDataJSON();
    expect(body.search_windows).toHaveLength(1);
    expect(body.nights).toBe(2);
    expect(body.weekends_only).toBe(true);
  });
});
