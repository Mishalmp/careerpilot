import type { Page } from "@playwright/test";

import { expect, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-12 (checkpoint exams), L19, LU09

async function csrf(page: Page): Promise<string> {
  const me = await page.request.get("/api/v1/auth/me");
  return ((await me.json()) as { csrf_token: string }).csrf_token;
}

async function resetLearn(page: Page) {
  const token = await csrf(page);
  const topics = (await (await page.request.get("/api/v1/learn/topics?archived=true")).json()) as { id: string }[];
  for (const t of topics) await page.request.delete(`/api/v1/learn/topics/${t.id}`, { headers: { "X-CSRF-Token": token } });
}

/** A topic with `count` multiple-choice questions, each answered once (so they count as studied). */
async function studiedBank(page: Page, title = "Transactions", count = 4) {
  const headers = { "X-CSRF-Token": await csrf(page) };
  const topic = (await (await page.request.post("/api/v1/learn/topics", { data: { title }, headers })).json()) as { id: string };
  for (let i = 0; i < count; i++) {
    const q = (await (
      await page.request.post("/api/v1/learn/questions", {
        headers,
        data: {
          topic_id: topic.id,
          type: "mcq_single",
          stem: `${title} question ${i + 1}?`,
          tags: [],
          explanation: "Because it is atomic.",
          options: [
            { text: "Right", is_correct: true, rationale: "Yes." },
            { text: "Wrong one", is_correct: false },
            { text: "Wrong two", is_correct: false },
          ],
        },
      })
    ).json()) as { id: string };
    await page.request.post(`/api/v1/learn/questions/${q.id}/answer`, {
      headers,
      data: { token: crypto.randomUUID(), selected: [0], confidence: 2 },
    });
  }
}

test.describe("checkpoints", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await resetLearn(page);
  });

  test("with nothing studied it explains what to do first", async ({ page }) => {
    await page.goto("/learn/checkpoints");
    await expect(page.getByText("No checkpoints yet")).toBeVisible();
    await page.getByRole("button", { name: "Start checkpoint" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "already answered" })).toBeVisible();
  });

  test("take an exam, answer some, flag, submit, and read the report", async ({ page }) => {
    await studiedBank(page);
    await page.goto("/learn/checkpoints");
    await page.getByLabel("Questions").selectOption("5");
    await page.getByRole("button", { name: "Start checkpoint" }).click();
    await expect(page).toHaveURL(/\/learn\/checkpoints\/.+/);
    await expect(page.getByRole("timer")).toBeVisible();
    await expect(page.getByText("Question 1 of 4")).toBeVisible();
    // The answers are not shown while taking the exam.
    await expect(page.getByText("Because it is atomic.")).toHaveCount(0);

    // Q1 right, Q2 wrong, Q3 right, Q4 left blank.
    await page.getByRole("radio", { name: "Right" }).check();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("radio", { name: "Wrong one" }).check();
    await page.getByRole("button", { name: "Flag for review" }).click();
    await expect(page.getByRole("button", { name: "Question 2, answered, flagged" })).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("radio", { name: "Right" }).check();

    // Reloading keeps what was saved.
    await page.reload();
    await expect(page.getByRole("button", { name: "Question 1, answered" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Question 2, answered, flagged" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Question 4, not answered" })).toBeVisible();

    await page.getByRole("button", { name: "Submit" }).click();
    const dialog = page.getByRole("dialog", { name: "Submit your answers?" });
    await expect(dialog).toContainText("1 question is unanswered and will count as wrong");
    await dialog.getByRole("button", { name: "Submit" }).click();

    await expect(page.getByRole("heading", { name: "Checkpoint result" })).toBeVisible();
    await expect(page.getByText("50%", { exact: true })).toBeVisible();
    await expect(page.getByText("Not passed yet")).toBeVisible();
    await expect(page.getByText("2 of 4 right")).toBeVisible();
    await expect(page.getByRole("heading", { name: "By topic" })).toBeVisible();
    await expect(page.getByText("2/4 · 50%")).toBeVisible();
    await expect(page.getByText("Because it is atomic.").first()).toBeVisible();
    await expect(page.getByText("Not answered")).toBeVisible();
    await expect(page.getByText(/The 2 questions you missed are due for review now/)).toBeVisible();

    // Missed questions really are in the review queue.
    await page.getByRole("link", { name: "Start review" }).click();
    await expect(page.getByText("2 due")).toBeVisible();

    // And the result is in the history.
    await page.goto("/learn/checkpoints");
    await expect(page.getByText("Not passed")).toBeVisible();
    await expect(page.getByText("50%", { exact: true })).toBeVisible();
  });

  test("an exam in progress can be opened again from the list, and submitted twice safely", async ({ page }) => {
    await studiedBank(page, "Caching", 3);
    await page.goto("/learn/checkpoints");
    await page.getByRole("button", { name: "Start checkpoint" }).click();
    await expect(page.getByRole("timer")).toBeVisible();
    await page.goto("/learn/checkpoints");
    await page.getByRole("button", { name: "Start checkpoint" }).click(); // returns the running one
    await expect(page).toHaveURL(/\/learn\/checkpoints\/.+/);
    await expect(page.getByText("Question 1 of 3")).toBeVisible();
    await page.getByRole("button", { name: "Submit" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Submit" }).click();
    await expect(page.getByRole("heading", { name: "Checkpoint result" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Checkpoint result" })).toBeVisible();
  });

  test("an unknown checkpoint shows a way back", async ({ page }) => {
    await page.goto("/learn/checkpoints/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Could not open this checkpoint")).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to checkpoints" })).toBeVisible();
  });

  test("no horizontal scrolling on a phone", async ({ page }) => {
    await studiedBank(page);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/learn/checkpoints");
    await page.getByRole("button", { name: "Start checkpoint" }).click();
    await expect(page.getByRole("timer")).toBeVisible();
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`checkpoint screens are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await resetLearn(page);
    await studiedBank(page);
    await page.goto("/learn/checkpoints");
    await expect(page.getByRole("button", { name: "Start checkpoint" })).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByRole("button", { name: "Start checkpoint" }).click();
    await expect(page.getByRole("timer")).toBeVisible();
    await page.getByRole("radio", { name: "Right" }).check();
    await page.screenshot({ path: `e2e/.shots/${theme}/checkpoint-exam.png`, fullPage: true });
    await expectNoA11yViolations(page);
    await page.getByRole("button", { name: "Submit" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Submit" }).click();
    await expect(page.getByRole("heading", { name: "Checkpoint result" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/checkpoint-report.png`, fullPage: true });
    await expectNoA11yViolations(page);
  });
}
