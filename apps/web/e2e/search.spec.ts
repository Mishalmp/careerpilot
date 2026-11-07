import { csrfToken, expect, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: search conditions (regions, cities, work modes), free job feeds, quick research items

async function clearSearches(page: import("@playwright/test").Page) {
  const headers = { "X-CSRF-Token": await csrfToken(page) };
  const list = (await (await page.request.get("/api/v1/discovery/searches")).json()) as { id: string }[];
  for (const s of list) await page.request.delete(`/api/v1/discovery/searches/${s.id}`, { headers });
  const sources = (await (await page.request.get("/api/v1/discovery/sources")).json()) as { id: string; kind: string }[];
  for (const s of sources) await page.request.delete(`/api/v1/discovery/sources/${s.id}`, { headers });
}

test.describe("discover: searches and feeds", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await clearSearches(page);
    await page.goto("/discover");
  });
  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    await login(page);
    await clearSearches(page);
    await page.close();
  });

  test("one click adds the usual searches, each shown with its regions, cities and ways of working", async ({ page }) => {
    await expect(page.getByText(/No searches yet/)).toBeVisible();
    await page.getByRole("button", { name: /India: on site or hybrid/ }).click();
    const row = page.getByRole("listitem", { name: "Search: India on site or hybrid" });
    await expect(row.getByText("India", { exact: true })).toBeVisible();
    await expect(row.getByText("Bengaluru")).toBeVisible();
    await expect(row.getByText("Delhi NCR")).toBeVisible();
    await expect(row.getByText("Hybrid", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /India: on site or hybrid/ })).toBeDisabled(); // already there

    await page.getByRole("button", { name: /Dubai: on site or remote/ }).click();
    await page.getByRole("button", { name: /Europe and USA: remote/ }).click();
    await expect(page.getByRole("listitem", { name: /^Search:/ })).toHaveCount(3);
  });

  test("a search can be paused, resumed and deleted, and the choice survives a reload", async ({ page }) => {
    await page.getByRole("button", { name: /India: remote/ }).click();
    const row = page.getByRole("listitem", { name: "Search: India remote" });
    await row.getByRole("switch", { name: "Use India remote" }).click();
    await expect(row.getByText("Paused")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("listitem", { name: "Search: India remote" }).getByText("Paused")).toBeVisible();
    await page.getByRole("button", { name: "Delete search India remote" }).click();
    await expect(page.getByRole("listitem", { name: /^Search:/ })).toHaveCount(0);
  });

  test("your own search: cities in any spelling, regions and ways of working", async ({ page }) => {
    await page.getByRole("button", { name: "Build my own search" }).click();
    const add = page.getByRole("button", { name: "Add this search" });
    await expect(add).toBeDisabled(); // needs a name, a region and a way of working
    await page.getByLabel("Name of this search").fill("Bangalore hybrid");
    await page.getByRole("button", { name: "India", exact: true }).click();
    await page.getByLabel("Add to Cities (for on site and hybrid)").fill("Bangalore");
    await page.getByLabel("Add to Cities (for on site and hybrid)").press("Enter");
    await page.getByRole("button", { name: "Hybrid", exact: true }).click();
    await add.click();
    const row = page.getByRole("listitem", { name: "Search: Bangalore hybrid" });
    await expect(row.getByText("Bangalore", { exact: true })).toBeVisible();
    await expect(row.getByText("Hybrid", { exact: true })).toBeVisible();
  });

  test("free job feeds are followed with one click, once", async ({ page }) => {
    await expect(page.getByText(/LinkedIn, Indeed, Glassdoor and Naukri are not/)).toBeVisible();
    await page.getByRole("button", { name: "Follow Remote OK" }).click();
    await expect(page.getByRole("button", { name: "Remote OK is followed" })).toBeDisabled();
    await expect(page.getByText("Remote OK · remoteok/all")).toBeVisible();
  });

  for (const theme of ["light", "dark"] as Theme[]) {
    test(`accessible in ${theme} mode and on a phone`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto("/discover");
      await page.getByRole("button", { name: /India: remote/ }).click();
      await expect(page.getByRole("listitem", { name: "Search: India remote" })).toBeVisible();
      await page.screenshot({ path: `e2e/.shots/${theme}/discover-searches.png`, fullPage: true });
      await expectNoA11yViolations(page);
      await page.setViewportSize({ width: 375, height: 812 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
