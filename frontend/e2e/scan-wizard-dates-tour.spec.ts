import { test, expect } from "@playwright/test";
import { completeProviderStep, mockApi, openWizard } from "./support/app";

// The other specs suppress the onboarding tours; this one deliberately lets the
// dates tour run, so a broken anchor or a missing step fails here rather than
// silently showing an empty popover to a first-time user.
test.describe("scan wizard — dates tour", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.addInitScript(() => localStorage.removeItem("campbuddy:tour-seen:wizard-dates"));
  });

  test("introduces quick picks, the summary and the nights rule on first arrival", async ({ page }) => {
    await openWizard(page);
    await completeProviderStep(page);

    const popover = page.locator(".driver-popover");
    await expect(popover).toContainText("Quick picks");
    await expect(popover).toContainText(/replaces everything/i);

    await popover.getByRole("button", { name: "Next" }).click();
    await expect(popover).toContainText("What you'll actually be searching");

    await popover.getByRole("button", { name: "Next" }).click();
    await expect(popover).toContainText("Nights is an exact length");
    await expect(popover).toContainText(/will not match a single free night/i);
    await expect(popover).toContainText(/Quick picks reset it/i);
  });

  test("stays out of the way once the seen flag is set", async ({ page }) => {
    // Gating is asserted from the browser rather than through a dismiss click:
    // React StrictMode double-invokes the effect under `npm run dev`, so the
    // driver instance is built, torn down and rebuilt, and racing that teardown
    // makes a click-to-dismiss assertion flaky for reasons the user never hits.
    await page.addInitScript(() =>
      localStorage.setItem("campbuddy:tour-seen:wizard-dates", "1"),
    );

    await openWizard(page);
    await completeProviderStep(page);

    await expect(page.getByRole("button", { name: "Next weekend" })).toBeVisible();
    await expect(page.locator(".driver-popover")).toBeHidden();
  });

  test("can be replayed from the help icon on the dates step", async ({ page }) => {
    await page.addInitScript(() =>
      localStorage.setItem("campbuddy:tour-seen:wizard-dates", "1"),
    );

    await openWizard(page);
    await completeProviderStep(page);
    await expect(page.locator(".driver-popover")).toBeHidden();

    await page.getByRole("button", { name: "Show tips for this step" }).first().click();

    await expect(page.locator(".driver-popover")).toContainText("Quick picks");
  });
});
