import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Logged-out visitor: every API call is unauthenticated.
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, body: "" }));
});

test("logged-out visitors see the landing page at /", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Sold-out campsite?");

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "How it works" }).click();
  await expect(page.locator("#how-it-works")).toBeInViewport();

  await page.getByRole("link", { name: /start a free scan/i }).first().click();
  await expect(page).toHaveURL(/\/register$/);
});

test("privacy page is reachable from the footer", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: "Privacy" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Privacy policy" })).toBeVisible();
});
