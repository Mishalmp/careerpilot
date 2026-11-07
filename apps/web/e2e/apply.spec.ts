import type { Page } from "@playwright/test";

import { createJob, expect, runSeed, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: the assisted daily apply list (docs/phase-7/11): sources shown, you decide, no submit action

const seedApply = (mode: "seed" | "reset") => runSeed("apply", mode);

async function trackerStatus(page: Page, company: string): Promise<string> {
  const list = (await (await page.request.get(`/api/v1/jobs?q=${encodeURIComponent(company)}`)).json()) as {
    items: { application: { status: string } }[];
  };
  return list.items[0].application.status;
}

test.describe("apply list", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    // Own jobs, so this spec does not change the status of the jobs other specs rely on.
    await createJob(page, { company_name: "Applyco", title: "Python Backend Developer", apply_url: "https://applyco.example/apply" });
    await createJob(page, { company_name: "Heldco", title: "Python Backend Developer" });
    seedApply("seed");
  });
  test.afterAll(() => seedApply("reset"));

  test("each part says where it came from, and nothing can be submitted", async ({ page }) => {
    await page.goto("/apply");
    await expect(page.getByRole("heading", { name: "Apply list", level: 1 })).toBeVisible();
    const card = page.getByRole("listitem", { name: /Python Backend Developer at Applyco/ });
    await expect(card.getByText("14 LPA to 20 LPA")).toBeVisible();
    await expect(card.getByText("The same job, listed on another site")).toBeVisible();
    await expect(card.getByText(/Salary 14 - 20 LPA/)).toBeVisible();
    await expect(card.getByRole("link", { name: /Python Developer - Acme/ })).toHaveAttribute(
      "href",
      "https://jobs.example.net/acme-python",
    );
    await expect(card.getByText("Typical for this kind of role (not this company)")).toBeVisible();
    await card.getByText(/Where I looked/).first().click();
    await expect(card.getByText(/The post does not state the pay/)).toBeVisible();
    await expect(card.getByRole("heading", { name: "Also listed on" })).toBeVisible();
    await expect(page.getByRole("button", { name: /submit|send/i })).toHaveCount(0);
    await expect(page.getByText(/never submits an application/)).toBeVisible();
  });

  test("approve shortlists the job; I applied records it; nothing is sent", async ({ page }) => {
    await page.goto("/apply");
    const card = page.getByRole("listitem", { name: /at Applyco/ });
    await expect(card.getByRole("link", { name: /Open the apply page/ })).toHaveAttribute("href", "https://applyco.example/apply");
    await card.getByRole("button", { name: /^Approve/ }).click();
    await expect(card.getByText("Approved: apply, then say you did")).toBeVisible();
    expect(await trackerStatus(page, "Applyco")).toBe("Shortlisted");

    await card.getByRole("button", { name: /^I applied/ }).click();
    await expect(page.getByRole("heading", { name: "Decided this week" })).toBeVisible();
    await expect(page.getByRole("listitem", { name: /at Applyco/ }).getByText("Applied", { exact: true })).toBeVisible();
    expect(await trackerStatus(page, "Applyco")).toBe("Applied - Pending");
  });

  test("a held-back job shows the reason and can still be skipped", async ({ page }) => {
    await page.goto("/apply");
    const held = page.getByRole("listitem", { name: /at Heldco/ });
    await expect(page.getByRole("heading", { name: "Held back by the company check" })).toBeVisible();
    await expect(held.getByText("Red flag raised: asks for money.").first()).toBeVisible();
    await expect(held.getByText(/No apply link on file/)).toBeVisible();
    await held.getByRole("button", { name: /^Skip/ }).click();
    await expect(held.getByText("Skipped", { exact: true })).toBeVisible();
    expect(await trackerStatus(page, "Heldco")).toBe("New");
  });

  test("Today points at the list", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("link", { name: /Jobs ready to review/ });
    await expect(link).toContainText("1");
    await link.click();
    await expect(page).toHaveURL(/\/apply$/);
  });

  for (const theme of ["light", "dark"] as Theme[]) {
    test(`accessible in ${theme} mode and on a phone`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto("/apply");
      await expect(page.getByRole("heading", { name: "To review" })).toBeVisible();
      await expectNoA11yViolations(page);
      await page.setViewportSize({ width: 375, height: 812 });
      await expect(page.getByRole("heading", { name: "To review" })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow).toBe(false);
    });
  }
});
