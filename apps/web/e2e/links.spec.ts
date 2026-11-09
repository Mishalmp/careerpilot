import {
  csrfToken,
  expect,
  expectNoA11yViolations,
  login,
  setTheme,
  test,
  type Theme,
} from "./fixtures";

// covers: pasted job links (never opened), suggested company boards, and the empty apply list explaining itself

const LINKS = [
  "https://www.linkedin.com/jobs/view/backend-engineer-at-zeta-3700000101/?trk=abc",
  "https://in.indeed.com/viewjob?jk=0123456789abcdef",
  "not a link",
].join("\n");

async function cleanUp(page: import("@playwright/test").Page) {
  const headers = { "X-CSRF-Token": await csrfToken(page) };
  const jobs = (await (
    await page.request.get("/api/v1/jobs?limit=200")
  ).json()) as { items: { id: string; apply_url: string | null }[] };
  for (const j of jobs.items) {
    if (
      j.apply_url?.includes("linkedin.com/jobs/view/3700000101") ||
      j.apply_url?.includes("jk=0123456789abcdef")
    ) {
      await page.request.delete(`/api/v1/jobs/${j.id}`, { headers });
    }
  }
  const sources = (await (
    await page.request.get("/api/v1/discovery/sources")
  ).json()) as { id: string }[];
  for (const s of sources)
    await page.request.delete(`/api/v1/discovery/sources/${s.id}`, { headers });
}

test.describe("job links and suggested boards", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await cleanUp(page);
  });
  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    await login(page);
    await cleanUp(page);
    await page.close();
  });

  test("pasted links are saved without being opened, with the role and company the address spells", async ({
    page,
  }) => {
    await page.goto("/jobs");
    await page.getByRole("button", { name: "Paste links" }).click();
    const dialog = page.getByRole("dialog", { name: "Paste job links" });
    await dialog.getByLabel("Job links").fill(LINKS);
    await dialog.getByRole("button", { name: /Save 3 links/ }).click();

    const results = dialog.getByRole("list", { name: "Results" });
    await expect(results.getByText("Backend Engineer")).toBeVisible();
    await expect(results.getByText(/Zeta · LinkedIn/)).toBeVisible();
    await expect(
      results.getByText(/Unknown company · Indeed · add the company or role/),
    ).toBeVisible();
    await expect(results.getByText("Saved", { exact: true })).toHaveCount(2);
    await expect(results.getByText("Not saved", { exact: true })).toHaveCount(
      1,
    );
    await expectNoA11yViolations(page);
    await dialog.getByRole("button", { name: "Done" }).click();

    await page
      .getByPlaceholder(/Search/)
      .first()
      .fill("Zeta");
    await expect(page.getByText("Backend Engineer").first()).toBeVisible();
  });

  test("pasting the same link again says it is already saved", async ({
    page,
  }) => {
    await page.goto("/jobs");
    for (const expected of ["Saved", "Already saved"]) {
      await page.getByRole("button", { name: "Paste links" }).click();
      const dialog = page.getByRole("dialog", { name: "Paste job links" });
      await dialog
        .getByLabel("Job links")
        .fill(
          "https://www.linkedin.com/jobs/view/backend-engineer-at-zeta-3700000101/",
        );
      await dialog.getByRole("button", { name: /Save 1 link/ }).click();
      await expect(
        dialog
          .getByRole("list", { name: "Results" })
          .getByText(expected, { exact: true }),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Done" }).click();
    }
  });

  test("suggested company boards: filter, follow one, follow the rest", async ({
    page,
  }) => {
    await page.goto("/discover");
    const card = page
      .getByRole("heading", { name: "Companies worth following" })
      .locator("xpath=ancestor::*[contains(@class,'rounded')][1]");
    await expect(card).toBeVisible();
    const list = page.getByRole("list", { name: "Suggested company boards" });
    await expect(list.getByText("Meesho")).toBeVisible(); // "Hiring in India" is the default filter
    await page.getByRole("button", { name: "Follow Meesho" }).click();
    await expect(
      page.getByRole("button", { name: "Meesho is followed" }),
    ).toBeDisabled();
    await page.getByRole("button", { name: /Follow all \d+ shown/ }).click();
    await expect(
      page.getByRole("button", { name: "All followed" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Remote roles" }).click();
    await expect(list.getByText("Cohere")).toBeVisible();
  });

  for (const theme of ["light", "dark"] as Theme[]) {
    test(`discover with suggestions is accessible in ${theme} mode and fits a phone`, async ({
      page,
    }) => {
      await setTheme(page, theme);
      await page.goto("/discover");
      await expect(
        page.getByRole("heading", { name: "Companies worth following" }),
      ).toBeVisible();
      await page.screenshot({
        path: `e2e/.shots/${theme}/discover-suggestions.png`,
        fullPage: true,
      });
      await expectNoA11yViolations(page);
      await page.setViewportSize({ width: 375, height: 812 });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
