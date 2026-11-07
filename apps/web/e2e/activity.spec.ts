import { expect, expectNoA11yViolations, login, runSeed, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-19 (progress, history, retry and cancel are visible and work from the screen), AI call log

test.describe("activity", () => {
  test.beforeEach(async ({ page }) => {
    runSeed("activity", "seed");
    await login(page);
    await page.goto("/tasks");
  });
  test.afterAll(() => runSeed("activity", "reset"));

  test("counts, progress and the failure reason are visible", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: "Activity" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Failed/ })).toContainText("1");
    const running = page.getByRole("listitem", { name: "Build the daily apply list" });
    await expect(running.getByRole("progressbar")).toBeVisible();
    await expect(running.getByText("Researching Acme: Python Developer")).toBeVisible();
    const failed = page.getByRole("listitem", { name: "Research interview topics" });
    await expect(failed.getByText("Unexpected error; see the server log.").first()).toBeVisible();
    await expect(failed.getByText("Stopped at: Reading page 2 of 3")).toBeVisible();
  });

  test("a failed task shows its history, and Retry queues it again", async ({ page }) => {
    const failed = page.getByRole("listitem", { name: "Research interview topics" });
    const history = failed.getByRole("list", { name: "History" });
    await expect(history.getByText("Reading page 1 of 3")).toBeVisible(); // open by default when failed
    await failed.getByRole("button", { name: /^Retry/ }).click();
    await expect(failed.getByText("Waiting")).toBeVisible();
    await expect(failed.getByText(/another try/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Failed/ })).toContainText("0");
  });

  test("a waiting task can be cancelled, then run again", async ({ page }) => {
    const waiting = page.getByRole("listitem", { name: "Build the daily digest" });
    await waiting.getByRole("button", { name: /^Cancel/ }).click();
    await expect(waiting.getByText("Cancelled by you.").first()).toBeVisible();
    await waiting.getByRole("button", { name: /^Run again/ }).click();
    await expect(waiting.getByText("Waiting")).toBeVisible();
  });

  test("clicking a count filters the list", async ({ page }) => {
    await page.getByRole("button", { name: /Done/ }).click();
    await expect(page.getByRole("listitem", { name: "Back up the database" })).toBeVisible();
    await expect(page.getByRole("listitem", { name: "Research interview topics" })).toHaveCount(0);
  });

  test("the AI calls tab lists calls and can show only the problems", async ({ page }) => {
    await page.getByRole("tab", { name: "AI calls" }).click();
    await expect(page.getByText(/tokens used today/)).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(4); // header + three calls
    await page.getByRole("switch", { name: "Only problems" }).click();
    await expect(page.getByRole("row")).toHaveCount(2);
    await expect(page.getByText("The model service is busy.")).toBeVisible();
  });

  test("Today shows the failed count and links here", async ({ page }) => {
    await page.goto("/");
    const tile = page.getByRole("link", { name: /Background tasks failed/ });
    await expect(tile).toContainText("1");
    await tile.click();
    await expect(page).toHaveURL(/\/tasks$/);
  });

  for (const theme of ["light", "dark"] as Theme[]) {
    test(`accessible in ${theme} and on a phone`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto("/tasks");
      await expect(page.getByRole("heading", { level: 1, name: "Activity" })).toBeVisible();
      await page.screenshot({ path: `e2e/.shots/${theme}/activity.png`, fullPage: true });
      await expectNoA11yViolations(page);
      await page.setViewportSize({ width: 375, height: 812 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
