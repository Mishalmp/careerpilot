import { expect, expectNoA11yViolations, login, seedJobs, setTheme, test, type Theme } from "./fixtures";

// covers: tracker flows (REQ-04 UX), page checklist for P03/P04/P06

test.describe("jobs", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await seedJobs(page);
    await page.goto("/jobs");
  });

  test("lists seeded jobs in a table with one status control per row", async ({ page }) => {
    await expect(page.getByRole("link", { name: "Acme Corp" })).toBeVisible();
    const row = page.getByRole("row", { name: /Acme Corp/ });
    await expect(row.getByRole("combobox", { name: /Change status of Python Full Stack Developer at Acme Corp/ })).toHaveValue("New");
  });

  test("add a job through the dialog, then see it; adding it again says it is already tracked", async ({ page }) => {
    const company = `Hooli ${Date.now()}`;
    await page.getByRole("button", { name: "Add job" }).first().click();
    const dialog = page.getByRole("dialog", { name: "Add a job" });
    await dialog.getByLabel("Company").fill(company);
    await dialog.getByLabel("Role").fill("SDE 2");
    await dialog.getByRole("button", { name: "Add job" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("link", { name: company })).toBeVisible();

    await page.getByRole("button", { name: "Add job" }).first().click();
    await dialog.getByLabel("Company").fill(company);
    await dialog.getByLabel("Role").fill("SDE 2");
    await dialog.getByRole("button", { name: "Add job" }).click();
    await expect(dialog.getByText("Already tracked.")).toBeVisible();
  });

  test("change status in place and keep it after reload", async ({ page }) => {
    const select = page.getByRole("combobox", { name: /Change status of Software Engineer at Globex/ });
    await select.selectOption("Shortlisted");
    await expect(select).toHaveValue("Shortlisted");
    await page.reload();
    await expect(page.getByRole("combobox", { name: /Change status of Software Engineer at Globex/ })).toHaveValue("Shortlisted");
  });

  test("skipping a stage asks for a note, and the move is blocked until it is given", async ({ page }) => {
    const select = page.getByRole("combobox", { name: /Change status of Backend Developer \(Python\) at Initech/ });
    await select.selectOption("Offer Received");
    const dialog = page.getByRole("dialog", { name: "Add a note" });
    await expect(dialog).toBeVisible();
    const move = dialog.getByRole("button", { name: /Move to Offer Received/ });
    await expect(move).toBeDisabled();
    await dialog.getByLabel(/Note/).fill("Referral skipped screening");
    await move.click();
    await expect(dialog).toBeHidden();
    await expect(select).toHaveValue("Offer Received");
  });

  test("search narrows the list; no match shows an empty state with a way back", async ({ page }) => {
    await page.getByRole("searchbox", { name: "Search company or role" }).fill("Globex");
    await expect(page.getByRole("link", { name: "Globex" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Acme Corp" })).toHaveCount(0);
    await page.getByRole("searchbox", { name: "Search company or role" }).fill("zzzz-no-such-job");
    await expect(page.getByText("No jobs match these filters")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page.getByRole("link", { name: "Acme Corp" })).toBeVisible();
  });

  test("board view shows a column per status and cards can be reached", async ({ page }) => {
    await page.getByRole("button", { name: "Board" }).click();
    await expect(page.getByRole("button", { name: "Board" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("heading", { name: /^New/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "Acme Corp" })).toBeVisible();
  });

  test("opening a job goes to its detail page", async ({ page }) => {
    await page.getByRole("link", { name: "Acme Corp" }).click();
    await expect(page).toHaveURL(/\/jobs\/.+/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Acme Corp");
  });

  test("works on a phone: no horizontal page scroll", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/jobs");
    await expect(page.getByRole("link", { name: "Acme Corp" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`jobs table and board are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await seedJobs(page);
    await page.goto("/jobs");
    await expect(page.getByRole("link", { name: "Acme Corp" })).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByRole("button", { name: "Board" }).click();
    await expect(page.getByRole("heading", { name: /^New/ })).toBeVisible();
    await expectNoA11yViolations(page);
  });
}
