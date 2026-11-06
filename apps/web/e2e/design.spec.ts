import { expect, expectNoA11yViolations, login, seedJobs, setTheme, test, type Theme } from "./fixtures";

// covers: REQ-01 (themes, no flash), REQ-02, REQ-04 (shell, responsive), REQ-31 (density)

test.describe("login page", () => {
  for (const theme of ["light", "dark"] as Theme[]) {
    test(`renders and has no serious a11y violations in ${theme}`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto("/login");
      await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(theme === "dark");
      await expectNoA11yViolations(page);
    });
  }

  test("shows a clear error for a wrong password", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("e2e@example.com");
    await page.getByLabel("Password").fill("definitely wrong password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert").filter({ hasText: /.+/ })).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("dev-only routes do not exist in a production build", async ({ page }) => {
    for (const path of ["/dev/ui", "/dev/shell"]) {
      const res = await page.goto(path);
      expect(res?.status(), path).toBe(404);
    }
  });
});

test.describe("theme", () => {
  test("applies before first paint and survives reload (no flash)", async ({ page }) => {
    await setTheme(page, "dark");
    // The class must be present as soon as the document starts parsing, before React runs.
    await page.addInitScript(() => {
      document.addEventListener("readystatechange", () => {
        (window as unknown as { __darkAtParse?: boolean }).__darkAtParse ??= document.documentElement.classList.contains("dark");
      });
    });
    await page.goto("/login");
    expect(await page.evaluate(() => (window as unknown as { __darkAtParse?: boolean }).__darkAtParse)).toBe(true);
    await page.reload();
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
  });

  test("the appearance menu switches theme and remembers it", async ({ page }) => {
    await setTheme(page, "light");
    await page.goto("/login");
    await page.getByRole("button", { name: "Appearance" }).click();
    await page.getByRole("menuitemradio", { name: "Dark" }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    await page.reload();
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    await page.getByRole("button", { name: "Appearance" }).click();
    await page.getByRole("menuitemradio", { name: "Compact" }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.density)).toBe("compact");
  });
});

test.describe("signed-in shell", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("sidebar groups, active item, and navigation", async ({ page }) => {
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const group of ["Workspace", "Prepare", "Analyse", "System"]) await expect(nav.getByText(group)).toBeVisible();
    await expect(nav.getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "page");
    await nav.getByRole("link", { name: "Jobs" }).click();
    await expect(page).toHaveURL(/\/jobs/);
    await expect(nav.getByRole("link", { name: "Jobs" })).toHaveAttribute("aria-current", "page");
  });

  test("sign out returns to the login page", async ({ page }) => {
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("mobile: navigation is a drawer", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await page.getByRole("link", { name: "Jobs" }).click();
    await expect(page).toHaveURL(/\/jobs/);
    await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
    // No horizontal scrolling on a phone.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("existing pages follow the theme and stay accessible", () => {
  const PAGES = ["/", "/jobs", "/discover", "/prep", "/practice", "/ask", "/mock", "/tasks", "/insights", "/offers", "/stories"];
  for (const theme of ["light", "dark"] as Theme[]) {
    for (const path of PAGES) {
      test(`${path} (${theme})`, async ({ page }) => {
        await setTheme(page, theme);
        await login(page);
        await seedJobs(page);
        await page.goto(path);
        await expect(page.locator("main")).toBeVisible();
        await page.waitForLoadState("networkidle");
        await page.screenshot({ path: `e2e/.shots/${theme}${path === "/" ? "/today" : path}.png`, fullPage: true });
        await expectNoA11yViolations(page);
      });
    }
  }
});
