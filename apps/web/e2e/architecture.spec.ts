import { expect, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-14 (interactive diagrams, flow player), REQ-15 (concept pages), V04-V10, V17

test.describe("architecture explorer", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/architecture");
    await expect(page.getByRole("heading", { level: 1, name: "How CareerPilot works" })).toBeVisible();
  });

  test("system diagram shows the parts, and selecting one shows where its code is", async ({ page }) => {
    const region = page.getByRole("region", { name: /System overview diagram/ });
    await expect(region).toBeVisible();
    await expect(region.getByText("PostgreSQL + pgvector")).toBeVisible();
    await region.getByText("Worker", { exact: true }).first().click();
    const details = page.getByRole("complementary", { name: "Details: Worker" });
    await expect(details).toBeVisible();
    await expect(details.getByText("apps/api/src/careerpilot/worker.py")).toBeVisible();
  });

  test("the list view is a text version of the same diagram", async ({ page }) => {
    await page.getByRole("button", { name: "List" }).click();
    await expect(page.getByText("Uses:").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Search provider/ })).toBeVisible();
  });

  test("the modules diagram lists every backend module", async ({ page }) => {
    await page.getByRole("tab", { name: "Modules" }).click();
    await page.getByRole("button", { name: "List" }).click();
    for (const name of ["Tracker", "Learn", "Auth", "Architecture explorer"]) {
      await expect(page.getByRole("button", { name: new RegExp(name) }).first()).toBeVisible();
    }
  });

  test("flow player steps forward and back, and shows what happens on failure", async ({ page }) => {
    await page.getByRole("tab", { name: /Flows/ }).click();
    await page.getByRole("tab", { name: "Answer a question" }).click();
    await expect(page.getByText("Step 1 of 4")).toBeVisible();
    await page.getByRole("button", { name: "What if this fails?" }).click();
    await expect(page.getByText(/same token arrives twice/i)).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Step 2 of 4")).toBeVisible();
    await expect(page.getByText(/same token arrives twice/i)).toHaveCount(0);
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByText("Step 1 of 4")).toBeVisible();
    await page.getByRole("tab", { name: "Answer a question" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByText(/Step \d of 4/)).toBeVisible();
  });

  test("the research flow is shown as built, with its failure branches", async ({ page }) => {
    await page.getByRole("tab", { name: /Flows/ }).click();
    await page.getByRole("tab", { name: /Research interview topics/ }).click();
    await expect(page.getByText("Planned, not built yet")).toHaveCount(0);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "What if this fails?" }).click();
    await expect(page.getByText(/search provider is down/i)).toBeVisible();
  });

  test("concepts can be searched and opened, with proof and related links", async ({ page }) => {
    await page.getByRole("tab", { name: /Concepts/ }).click();
    await page.getByRole("searchbox", { name: "Search concepts" }).fill("queue");
    await page.getByRole("link", { name: /Queues, leases and retries/ }).click();
    await expect(page).toHaveURL(/\/architecture\/concepts\/queues/);
    await expect(page.getByRole("heading", { level: 1, name: /Queues/ })).toBeVisible();
    await expect(page.getByText("SKIP LOCKED").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Proven by" })).toBeVisible();
    await page.getByRole("link", { name: "Idempotency" }).click();
    await expect(page).toHaveURL(/concepts\/idempotency/);
  });

  test("an unknown concept shows an error with a way back", async ({ page }) => {
    await page.goto("/architecture/concepts/not-a-concept");
    await expect(page.getByText("No such concept")).toBeVisible();
    await expect(page.getByRole("link", { name: "How it works" }).first()).toBeVisible();
  });

  test("no horizontal scroll on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/architecture");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`architecture pages are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await page.goto("/architecture");
    await expect(page.getByRole("region", { name: /System overview diagram/ })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `e2e/.shots/${theme}/architecture.png`, fullPage: true });
    await expectNoA11yViolations(page);
    await page.getByRole("tab", { name: "Modules" }).click();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `e2e/.shots/${theme}/architecture-modules.png`, fullPage: true });
    await expectNoA11yViolations(page);
    await page.getByRole("tab", { name: /Flows/ }).click();
    await page.waitForLoadState("networkidle");
    await expectNoA11yViolations(page);
    await page.getByRole("tab", { name: /Concepts/ }).click();
    await expectNoA11yViolations(page);
    await page.goto("/architecture/concepts/queues");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoA11yViolations(page);
  });
}
