import { execFileSync } from "node:child_process";

import type { Page } from "@playwright/test";

import { expect, expectNoA11yViolations, login, seedJobs, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-07 (inbox, nothing enters Learn until approved), REQ-08 (source + quote shown), P08/LU07

async function csrf(page: Page): Promise<string> {
  const me = await page.request.get("/api/v1/auth/me");
  return ((await me.json()) as { csrf_token: string }).csrf_token;
}

async function resetLearn(page: Page) {
  const token = await csrf(page);
  const topics = (await (await page.request.get("/api/v1/learn/topics?archived=true")).json()) as { id: string }[];
  for (const t of topics) await page.request.delete(`/api/v1/learn/topics/${t.id}`, { headers: { "X-CSRF-Token": token } });
}

async function jobId(page: Page): Promise<string> {
  const list = (await (await page.request.get("/api/v1/jobs?q=Acme")).json()) as { items: { id: string }[] };
  return list.items[0].id;
}

/** Insert a finished run with three findings straight into the throwaway E2E database. */
function seedInbox(target: string) {
  execFileSync("python", ["-m", "uv", "run", "python", "scripts/seed_e2e_findings.py", target], {
    cwd: "../api",
    stdio: "pipe",
  });
}

test.describe("research inbox", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await seedJobs(page);
    await resetLearn(page);
    seedInbox("reset"); // each test starts with no research data
  });

  test("starting research without a search service explains how to set one up", async ({ page }) => {
    await page.goto(`/jobs/${await jobId(page)}`);
    await page.getByRole("tab", { name: "Research" }).click();
    await page.getByRole("button", { name: "Research interview topics" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "No search service is set up" })).toBeVisible();
    await expect(page.getByText("CAREERPILOT_SEARCH_PROVIDER")).toBeVisible();
  });

  test("findings show their source and quote; approving moves them into Learn", async ({ page }) => {
    seedInbox(await jobId(page));
    await page.goto("/learn");
    await expect(page.getByRole("heading", { name: /Research inbox/ })).toBeVisible();
    const card = page.getByRole("listitem").filter({ hasText: "What is a database transaction?" });
    await expect(card.getByText("Relevance 90")).toBeVisible();
    await expect(card.getByRole("link", { name: /Backend interview guide/ })).toHaveAttribute("href", "https://blog.example.com/interviews");
    // Nothing is in Learn before approval.
    await expect(page.getByText("Nothing to learn yet")).toBeVisible();

    await card.getByRole("button", { name: /Approve/ }).click();
    await expect(card).toHaveCount(0);
    await expect(page.getByRole("link", { name: "database transactions" })).toBeVisible();
    await page.getByRole("link", { name: "database transactions" }).click();
    await expect(page.getByText("What is a database transaction?")).toBeVisible();
    await expect(page.getByText("Verified", { exact: true })).toBeVisible();
    await expect(page.getByText("1 source")).toBeVisible();
  });

  test("rejecting removes a finding and creates nothing", async ({ page }) => {
    seedInbox(await jobId(page));
    await page.goto("/learn");
    const card = page.getByRole("listitem").filter({ hasText: "How do you version a REST API?" });
    await card.getByRole("button", { name: /Reject/ }).click();
    await expect(card).toHaveCount(0);
    await expect(page.getByText("Nothing to learn yet")).toBeVisible();
  });

  test("the job page lists the research run and how many findings wait", async ({ page }) => {
    const id = await jobId(page);
    seedInbox(id);
    await page.goto(`/jobs/${id}`);
    await page.getByRole("tab", { name: "Research" }).click();
    const runs = page.getByRole("list", { name: "Research runs" });
    await expect(runs.getByText("Finished", { exact: true })).toBeVisible();
    await expect(runs.getByText("3 waiting in your inbox")).toBeVisible();
    await expect(runs.getByText(/discarded 1 whose quote was not on the page/)).toBeVisible();
  });

  test("an empty inbox explains how to fill it", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.getByText("Your research inbox is empty")).toBeVisible();
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`research inbox is accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await seedJobs(page);
    await resetLearn(page);
    seedInbox(await jobId(page));
    await page.goto("/learn");
    await expect(page.getByRole("heading", { name: /Research inbox/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Approve: What is a database transaction/ })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/learn-inbox.png`, fullPage: true });
    await expectNoA11yViolations(page);
  });
}
