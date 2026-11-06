import AxeBuilder from "@axe-core/playwright";
import { expect, test as base, type Page } from "@playwright/test";

// Test-only account, created in the throwaway careerpilot_e2e database by
// apps/api/scripts/prepare_e2e.py (same values there).
export const E2E_EMAIL = "e2e@example.com";
export const E2E_PASSWORD = "e2e test password 2026";

export type Theme = "light" | "dark";

/** Sets the stored theme before the page loads, the same way the app stores it (a cookie). */
export async function setTheme(page: Page, theme: Theme, density: "comfortable" | "compact" = "comfortable") {
  await page.context().addCookies([
    { name: "cp-theme", value: theme, url: "http://localhost:3101" },
    { name: "cp-density", value: density, url: "http://localhost:3101" },
  ]);
}

/** Signs in through the real login form. */
export async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
}

/**
 * Creates a job through the real API (with the session cookie and CSRF header the app uses).
 * Must be called after login(). A duplicate (409) is fine: the job already exists from an earlier test.
 */
export async function createJob(page: Page, fields: { company_name: string; title: string; [k: string]: unknown }) {
  const me = await page.request.get("/api/v1/auth/me");
  expect(me.ok(), "createJob must be called after login()").toBeTruthy();
  const { csrf_token } = (await me.json()) as { csrf_token: string };
  const res = await page.request.post("/api/v1/jobs", { data: fields, headers: { "X-CSRF-Token": csrf_token } });
  if (res.status() !== 409) expect(res.ok(), await res.text()).toBeTruthy();
}

/** A few realistic jobs so list pages are checked with data, not only empty states. */
export async function seedJobs(page: Page) {
  await createJob(page, { company_name: "Acme Corp", title: "Python Full Stack Developer", work_mode: "Remote" });
  await createJob(page, { company_name: "Globex", title: "Software Engineer", location_text: "Bengaluru" });
  await createJob(page, { company_name: "Initech", title: "Backend Developer (Python)", jd_url: "https://example.com/jobs/1" });
}

/** Fails on serious or critical accessibility violations (WCAG 2.x A/AA rules). */
export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes) e.g. ${v.nodes[0]?.html.slice(0, 120)}`),
  ).toEqual([]);
}

export const test = base;
export { expect };
