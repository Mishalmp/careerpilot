import { csrfToken, expect, expectNoA11yViolations, login, runSeed, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-28 (nothing about one person is hard-coded: account setup, CV file, links, roles wanted)

const CV = `Priya Sharma
Senior Python Full Stack Developer at Acme (2022 - present). 4+ years of professional experience.
Built REST APIs with FastAPI and Django, PostgreSQL and Docker; React and TypeScript front ends.
Open to SDE and Software Developer roles.`;

// Later specs expect a user with no name (Today says just "Today"), so leave no profile behind.
test.afterAll(() => runSeed("profile", "reset"));

const cvFile = { name: "cv.txt", mimeType: "text/plain", buffer: Buffer.from(CV) };

/** Account setup finished, through the API, so a test can start from the one-page profile. */
async function completeSetup(page: import("@playwright/test").Page) {
  const headers = { "X-CSRF-Token": await csrfToken(page) };
  await page.request.patch("/api/v1/profile", {
    headers,
    data: {
      full_name: "Priya Sharma",
      current_role: "Backend Developer",
      target_roles: ["Python Developer"],
      regions: ["India"],
      skills: ["python", "sql"],
    },
  });
  const done = await page.request.post("/api/v1/profile/setup/complete", { headers });
  expect(done.ok(), await done.text()).toBeTruthy();
}

test.describe("account setup wizard", () => {
  test.beforeEach(async ({ page }) => {
    runSeed("profile", "reset");
    await login(page);
    await page.goto("/profile");
  });

  test("walks through the questions, reads a CV file, and finishes", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: "Set up your account" })).toBeVisible();
    await expect(page.getByRole("progressbar", { name: "Setup progress" })).toBeVisible();

    // 1. About you
    await page.getByLabel("Full name").fill("Priya Sharma");
    await page.getByLabel("Current role").fill("Backend Developer");
    await page.getByLabel("Contact email").fill("priya@example.com");
    await page.getByLabel("Phone number").fill("+91 98765 43210");
    await page.getByRole("button", { name: "Save and continue" }).click();

    // 2. What you want
    await expect(page.getByRole("heading", { name: "What you are looking for" })).toBeVisible();
    await page.getByLabel("Add to Roles you want").fill("Python Developer");
    await page.getByLabel("Add to Roles you want").press("Enter");
    await expect(page.getByRole("list", { name: "Roles you want" }).getByText("Python Developer")).toBeVisible();
    await page.getByRole("button", { name: "India", exact: true }).click();
    await page.getByRole("button", { name: "Remote", exact: true }).click();
    await expect(page.getByRole("button", { name: "India", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Save and continue" }).click();

    // 3. The CV, as a file
    await expect(page.getByRole("heading", { name: "Your CV" })).toBeVisible();
    await page.getByLabel("CV file").setInputFiles(cvFile);
    await expect(page.getByText(/CV read: cv\.txt/)).toBeVisible();
    const skills = page.getByRole("list", { name: "Skills" });
    for (const s of ["python", "fastapi", "django", "docker"]) await expect(skills.getByText(s, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue" }).click();

    // 4. Public profiles: a link on the wrong site is refused with the reason
    await page.getByLabel("GitHub").fill("https://example.com/priya");
    await page.getByRole("button", { name: "Save and continue" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "github.com" })).toBeVisible();
    await page.getByLabel("GitHub").fill("https://github.com/priya-sharma");
    await page.getByRole("button", { name: "Save and continue" }).click();

    // 5. Review and finish
    await expect(page.getByRole("heading", { name: "Review" })).toBeVisible();
    await expect(page.getByText("Priya Sharma").first()).toBeVisible();
    await expect(page.getByText("priya@example.com · +91 98765 43210")).toBeVisible();
    await page.getByRole("button", { name: "Finish setup" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1, name: /Priya/ })).toBeVisible();
    await expect(page.getByText("Finish setting up your account")).toHaveCount(0);
  });

  test("Today asks you to finish setup, and shows what is missing", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Finish setting up your account")).toBeVisible();
    await expect(page.getByText(/Still needed: your name/)).toBeVisible();
    await page.getByRole("link", { name: /Continue setup/ }).click();
    await expect(page).toHaveURL(/\/profile$/);
  });

  test("a scanned CV says OCR is needed; a wrong file type is refused", async ({ page }) => {
    await page.getByLabel("Full name").fill("Priya Sharma");
    await page.getByLabel("Current role").fill("Developer");
    await page.getByRole("button", { name: "Save and continue" }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByRole("heading", { name: "Your CV" })).toBeVisible();
    await page.getByLabel("CV file").setInputFiles({ name: "cv.pdf", mimeType: "application/pdf", buffer: Buffer.from(Array.from({ length: 400 }, (_, i) => i % 256)) });
    await expect(page.getByRole("alert").filter({ hasText: /could not be read|not supported/ })).toBeVisible();
  });
});

test.describe("profile page", () => {
  test.beforeEach(async ({ page }) => {
    runSeed("profile", "reset");
    await login(page);
    await completeSetup(page);
    await page.goto("/profile");
  });

  test("shows every section on one page and saves edits", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: "Your profile" })).toBeVisible();
    for (const name of ["About you", "What you are looking for", "Public profiles", "Your CV", "Skills and role titles"]) {
      await expect(page.getByRole("heading", { name })).toBeVisible();
    }
    const save = page.getByRole("button", { name: "Save changes" });
    await expect(save).toBeDisabled();
    await page.getByLabel("Current role").fill("Staff Engineer");
    await expect(page.getByText("You have unsaved changes.")).toBeVisible();
    await save.click();
    await expect(page.getByText("All changes are saved.")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Current role")).toHaveValue("Staff Engineer");
  });

  test("reading a CV fills skills and titles; they can be edited and persist", async ({ page }) => {
    await page.getByLabel("CV file").setInputFiles(cvFile);
    const titles = page.getByRole("list", { name: "Role titles" });
    await expect(titles.getByText("Python Full Stack Developer")).toBeVisible();
    await expect(titles.getByText("SDE")).toBeVisible();
    const skills = page.getByRole("list", { name: "Skills" });
    await expect(skills.getByText("fastapi", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Years of experience")).toHaveValue("4");

    await page.getByRole("button", { name: "Remove django" }).click();
    await expect(skills.getByText("django", { exact: true })).toHaveCount(0);
    await page.getByLabel("Add to Skills").fill("kafka");
    await page.getByLabel("Add to Skills").press("Enter");
    await expect(skills.getByText("kafka")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("list", { name: "Skills" }).getByText("kafka")).toBeVisible();
    await expect(page.getByRole("list", { name: "Skills" }).getByText("django", { exact: true })).toHaveCount(0);
  });

  test("pasting text still works, and the CV text is never shown again", async ({ page }) => {
    await page.getByText("Or paste the text").click();
    await page.getByLabel("CV text").fill("too short cv");
    await expect(page.getByRole("button", { name: "Read my CV" })).toBeDisabled();
    await page.getByLabel("CV text").fill(CV);
    await page.getByRole("button", { name: "Read my CV" }).click();
    await expect(page.getByText(/CV read.*paste/)).toBeVisible();
    await expect(page.getByLabel("CV text")).toHaveValue("");
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
  test(`setup wizard and profile are accessible in ${theme}`, async ({ page }) => {
    await setTheme(page, theme);
    runSeed("profile", "reset");
    await login(page);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 1, name: "Set up your account" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/setup.png`, fullPage: true });
    await expectNoA11yViolations(page);
    await completeSetup(page);
    await page.goto("/profile");
    await page.getByLabel("CV file").setInputFiles(cvFile);
    await expect(page.getByRole("list", { name: "Skills" })).toBeVisible();
    await page.screenshot({ path: `e2e/.shots/${theme}/profile.png`, fullPage: true });
    await expectNoA11yViolations(page);
  });
}
