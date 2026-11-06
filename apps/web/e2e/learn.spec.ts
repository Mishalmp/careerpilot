import type { Page } from "@playwright/test";

import { expect, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-06 (nothing predefined), REQ-09 (question types), REQ-11 (reviews), page checklist for P08

async function csrf(page: Page): Promise<string> {
  const me = await page.request.get("/api/v1/auth/me");
  return ((await me.json()) as { csrf_token: string }).csrf_token;
}

/** Start every learning test from an empty Learn area (through the real API). */
async function resetLearn(page: Page) {
  const token = await csrf(page);
  const topics = (await (await page.request.get("/api/v1/learn/topics?archived=true")).json()) as { id: string }[];
  for (const t of topics) {
    await page.request.delete(`/api/v1/learn/topics/${t.id}`, { headers: { "X-CSRF-Token": token } });
  }
}

async function addTopicViaApi(page: Page, title: string) {
  const res = await page.request.post("/api/v1/learn/topics", {
    data: { title },
    headers: { "X-CSRF-Token": await csrf(page) },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { id: string }).id;
}

async function addMcq(page: Page, topicId: string, stem: string) {
  const res = await page.request.post("/api/v1/learn/questions", {
    headers: { "X-CSRF-Token": await csrf(page) },
    data: {
      topic_id: topicId,
      type: "mcq_single",
      stem,
      tags: [],
      explanation: "A transaction is all or nothing.",
      options: [
        { text: "All or nothing", is_correct: true, rationale: "That is atomicity." },
        { text: "Faster reads", is_correct: false },
        { text: "Free storage", is_correct: false },
      ],
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

test.describe("learn", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await resetLearn(page);
  });

  test("starts empty (nothing predefined) and explains what to do", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.getByRole("heading", { level: 1, name: "Learn" })).toBeVisible();
    await expect(page.getByText("Nothing to learn yet")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start review" })).toBeDisabled();
  });

  test("add a topic, then a multiple-choice question, and see them listed", async ({ page }) => {
    await page.goto("/learn");
    await page.getByRole("button", { name: "Add topic" }).first().click();
    const dialog = page.getByRole("dialog", { name: "Add a topic" });
    await dialog.getByLabel("Title").fill("Database transactions");
    await dialog.getByLabel("Area").fill("Databases");
    await dialog.getByRole("button", { name: "Add topic" }).click();
    await expect(dialog).toBeHidden();
    await page.getByRole("link", { name: "Database transactions" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Database transactions" })).toBeVisible();
    await expect(page.getByText("No questions yet")).toBeVisible();

    await page.getByRole("button", { name: "Add question" }).first().click();
    const q = page.getByRole("dialog", { name: "Add a question" });
    await q.getByLabel("Question", { exact: false }).first().fill("What does atomicity guarantee?");
    await q.getByLabel("Option 1", { exact: true }).fill("All or nothing");
    await q.getByLabel("Option 2", { exact: true }).fill("Faster reads");
    await q.getByLabel("Option 3", { exact: true }).fill("Free storage");
    await q.getByLabel("Explanation").fill("A transaction is all or nothing.");
    await q.getByRole("button", { name: "Add question" }).click();
    await expect(q).toBeHidden();
    await expect(page.getByText("What does atomicity guarantee?")).toBeVisible();
    await expect(page.getByText("Verified", { exact: true })).toBeVisible();
  });

  test("a server-side rule error is shown inside the dialog and nothing is lost", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Caching");
    await page.goto(`/learn/topics/${topicId}`);
    await page.getByRole("button", { name: "Add question" }).first().click();
    const q = page.getByRole("dialog", { name: "Add a question" });
    await q.getByLabel("Question", { exact: false }).first().fill("Which is a cache?");
    await q.getByLabel("Option 1", { exact: true }).fill("Same");
    await q.getByLabel("Option 2", { exact: true }).fill("Same");
    await q.getByLabel("Option 3", { exact: true }).fill("Other");
    await q.getByRole("button", { name: "Add question" }).click();
    await expect(q.getByRole("alert")).toContainText("Two options say the same thing");
    await expect(q.getByLabel("Option 3", { exact: true })).toHaveValue("Other");
  });

  test("review: answer with the keyboard, see the explanation, finish, and the streak starts", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Transactions");
    await addMcq(page, topicId, "What does a transaction guarantee?");
    await page.goto("/learn");
    await expect(page.getByRole("button", { name: /Start review/ }).or(page.getByRole("link", { name: /Start review/ })).first()).toBeVisible();
    await page.getByRole("link", { name: /Start review/ }).click();
    await expect(page).toHaveURL(/\/learn\/review/);
    await expect(page.getByRole("heading", { name: "What does a transaction guarantee?" })).toBeVisible();
    // The answer must not be visible before answering.
    await expect(page.getByText("A transaction is all or nothing.")).toHaveCount(0);

    await page.keyboard.press("1");
    await expect(page.getByRole("radio", { name: "All or nothing" })).toBeChecked();
    await page.keyboard.press("Enter");
    await expect(page.getByText("Correct", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("A transaction is all or nothing.")).toBeVisible();
    await expect(page.getByText("That is atomicity.")).toBeVisible();

    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Session complete" })).toBeVisible();
    await page.getByRole("link", { name: "Back to Learn" }).click();
    await expect(page.getByText("1 d")).toBeVisible();
  });

  test("a wrong answer shows which option was right and which was picked", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Transactions");
    await addMcq(page, topicId, "What does a transaction guarantee?");
    await page.goto("/learn/review");
    await page.getByRole("radio", { name: "Faster reads" }).check();
    await page.getByRole("button", { name: "Check answer" }).click();
    await expect(page.getByText("Not quite")).toBeVisible();
    await expect(page.getByText("Your pick")).toBeVisible();
    await expect(page.getByText("Correct", { exact: true }).first()).toBeVisible();
  });

  test("written questions are rated by you after writing", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Idempotency");
    const res = await page.request.post("/api/v1/learn/questions", {
      headers: { "X-CSRF-Token": await csrf(page) },
      data: { topic_id: topicId, type: "explain", stem: "Explain idempotency.", tags: [], rubric: ["Same result when repeated"] },
    });
    expect(res.ok()).toBeTruthy();
    await page.goto("/learn/review");
    await expect(page.getByRole("heading", { name: "Explain idempotency." })).toBeVisible();
    await expect(page.getByRole("button", { name: "Got it" })).toBeDisabled();
    await page.getByLabel("Your answer").fill("Doing it twice has the same effect as once.");
    await page.getByRole("button", { name: "Got it" }).click();
    await expect(page.getByText("Rated by you")).toBeVisible();
  });

  test("with nothing due the review page says you are caught up", async ({ page }) => {
    await page.goto("/learn/review");
    await expect(page.getByText("You are all caught up")).toBeVisible();
  });

  test("deleting a topic asks first and removes it", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Temporary");
    await page.goto(`/learn/topics/${topicId}`);
    await page.getByRole("button", { name: "Delete topic" }).first().click();
    const dialog = page.getByRole("dialog", { name: "Delete this topic?" });
    await dialog.getByRole("button", { name: "Delete topic" }).click();
    await expect(page).toHaveURL(/\/learn$/);
    await expect(page.getByRole("link", { name: "Temporary" })).toHaveCount(0);
  });

  test("an unknown topic shows a way back", async ({ page }) => {
    await page.goto("/learn/topics/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Topic not found")).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to Learn" })).toBeVisible();
  });

  test("no horizontal scrolling on a phone", async ({ page }) => {
    const topicId = await addTopicViaApi(page, "Transactions");
    await addMcq(page, topicId, "What does a transaction guarantee?");
    await page.setViewportSize({ width: 375, height: 812 });
    for (const path of ["/learn", `/learn/topics/${topicId}`, "/learn/review"]) {
      await page.goto(path);
      await expect(page.locator("main")).toBeVisible();
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, path).toBeLessThanOrEqual(0);
    }
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`learn pages are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await resetLearn(page);
    const topicId = await addTopicViaApi(page, "Transactions");
    await addMcq(page, topicId, "What does a transaction guarantee?");
    await page.goto("/learn");
    await expect(page.getByRole("link", { name: "Transactions" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/learn.png`, fullPage: true });
    await expectNoA11yViolations(page);

    await page.goto(`/learn/topics/${topicId}`);
    await expect(page.getByText("What does a transaction guarantee?")).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/learn-topic.png`, fullPage: true });
    await expectNoA11yViolations(page);

    await page.goto("/learn/review");
    await expect(page.getByRole("heading", { name: "What does a transaction guarantee?" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/learn-review.png`, fullPage: true });
    await expectNoA11yViolations(page);
    await page.getByRole("radio", { name: "Faster reads" }).check();
    await page.getByRole("button", { name: "Check answer" }).click();
    await expect(page.getByText("Not quite")).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/learn-review-answer.png`, fullPage: true });
    await expectNoA11yViolations(page);
  });
}
