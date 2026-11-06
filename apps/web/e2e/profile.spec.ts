import { expect, expectNoA11yViolations, login, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-28 (profile derived from the CV, editable)

const CV = `Mishal MP - Software Engineer
Senior Python Full Stack Developer at Acme (2022 - present). 4+ years of professional experience.
Built REST APIs with FastAPI and Django, PostgreSQL and Docker; React and TypeScript front ends.
Open to SDE and Software Developer roles.`;

test.describe("profile", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    // start from a profile with no skills or titles
    const me = await page.request.get("/api/v1/auth/me");
    const csrf = ((await me.json()) as { csrf_token: string }).csrf_token;
    await page.request.patch("/api/v1/profile", {
      headers: { "X-CSRF-Token": csrf },
      data: { skills: [], role_titles: [], years_experience: null },
    });
    await page.request.delete("/api/v1/profile/cv", { headers: { "X-CSRF-Token": csrf } });
    await page.goto("/profile");
  });

  test("starts empty and explains what to do", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: "Your profile" })).toBeVisible();
    await expect(page.getByText("Nothing yet. Paste your CV")).toBeVisible();
    await expect(page.getByRole("button", { name: "Read my CV" })).toBeDisabled();
  });

  test("reading a CV fills skills, titles and years, and edits are saved", async ({ page }) => {
    await page.getByLabel("CV text").fill(CV);
    await page.getByRole("button", { name: "Read my CV" }).click();
    const titles = page.getByRole("list", { name: "Role titles" });
    await expect(titles.getByText("Python Full Stack Developer")).toBeVisible();
    await expect(titles.getByText("SDE")).toBeVisible();
    const skills = page.getByRole("list", { name: "Skills" });
    for (const s of ["python", "fastapi", "django", "docker"]) await expect(skills.getByText(s, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Years of experience")).toHaveValue("4");
    // The CV text is not shown again.
    await expect(page.getByLabel("CV text")).toHaveValue("");

    await page.getByRole("button", { name: "Remove django" }).click();
    await expect(skills.getByText("django", { exact: true })).toHaveCount(0);
    await page.getByLabel("Add to Skills").fill("kafka");
    await page.getByLabel("Add to Skills").press("Enter");
    await expect(skills.getByText("kafka")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("list", { name: "Skills" }).getByText("kafka")).toBeVisible();
    await expect(page.getByRole("list", { name: "Skills" }).getByText("django", { exact: true })).toHaveCount(0);
  });

  test("a too-short CV is refused with the reason", async ({ page }) => {
    await page.getByLabel("CV text").fill("too short cv");
    await expect(page.getByRole("button", { name: "Read my CV" })).toBeDisabled();
  });

  test("no horizontal scroll on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

for (const theme of ["light", "dark"] as Theme[]) {
  test(`profile is accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    await login(page);
    await page.goto("/profile");
    await page.getByLabel("CV text").fill(CV);
    await page.getByRole("button", { name: "Read my CV" }).click();
    await expect(page.getByRole("list", { name: "Skills" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/profile.png`, fullPage: true });
    await expectNoA11yViolations(page);
  });
}
