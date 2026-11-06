import { expect, expectNoA11yViolations, login, seedJobs, setTheme, test, type Theme } from "./fixtures";

// covers: P02 (Today), P05 (Job detail) page checklist

test.describe("today", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await seedJobs(page);
    await page.goto("/");
  });

  test("shows the summary cards and the pipeline", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
    await expect(page.getByText("Jobs tracked")).toBeVisible();
    await expect(page.getByText("Follow-ups due").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible();
    await expect(page.getByText("New", { exact: true }).first()).toBeVisible();
  });

  test("Add job leads to the jobs page", async ({ page }) => {
    await page.getByRole("link", { name: "Add job" }).click();
    await expect(page).toHaveURL(/\/jobs/);
  });

  test("works on a phone without horizontal scrolling", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("job detail", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await seedJobs(page);
    await page.goto("/jobs");
    await page.getByRole("link", { name: "Globex" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Globex");
  });

  test("tabs switch between overview, research, description and edit", async ({ page }) => {
    await expect(page.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
    await page.getByRole("tab", { name: "Research" }).click();
    await expect(page.getByRole("heading", { name: /genuine\?/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /How well does it fit you/ })).toBeVisible();
    await page.getByRole("tab", { name: "Description" }).click();
    await expect(page.getByText("No description saved")).toBeVisible();
  });

  test("status can be changed from the header", async ({ page }) => {
    const select = page.getByRole("combobox", { name: "Change status" });
    await select.selectOption("Shortlisted");
    await expect(select).toHaveValue("Shortlisted");
    await page.reload();
    await expect(page.getByRole("combobox", { name: "Change status" })).toHaveValue("Shortlisted");
  });

  test("deleting asks first, can be cancelled, and then removes the job", async ({ page }) => {
    await page.getByRole("tab", { name: "Edit" }).click();
    await page.getByRole("button", { name: "Delete job" }).first().click();
    const dialog = page.getByRole("dialog", { name: "Delete this job?" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(/\/jobs\/.+/);

    await page.getByRole("button", { name: "Delete job" }).first().click();
    await dialog.getByRole("button", { name: "Delete job" }).click();
    await expect(page).toHaveURL(/\/jobs$/);
    await expect(page.getByRole("link", { name: "Globex" })).toHaveCount(0);
  });

  test("an unknown job shows an error with a way back", async ({ page }) => {
    await page.goto("/jobs/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Could not load this job")).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to jobs" })).toBeVisible();
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`today and job detail are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await seedJobs(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
    await expectNoA11yViolations(page);
    await page.goto("/jobs");
    await page.getByRole("link", { name: "Acme Corp" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Acme Corp");
    await expectNoA11yViolations(page);
    for (const tab of ["Research", "Description", "Edit"]) {
      await page.getByRole("tab", { name: tab }).click();
      await expectNoA11yViolations(page);
    }
  });
}
