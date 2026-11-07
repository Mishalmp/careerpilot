import { expect, login, seedJobs, setTheme, test } from "./fixtures";

// covers: REQ-04 (responsive from phone to desktop), alignment: no page overflows, clips or has tiny targets

const ROUTES = ["/", "/jobs", "/discover", "/apply", "/learn", "/prep", "/practice", "/mock", "/ask", "/stories", "/insights", "/offers", "/profile", "/tasks", "/architecture"];
const SIZES = [
  { name: "phone", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "laptop", width: 1280, height: 800 },
] as const;

type Problem = string;

/** Looks at the drawn page and reports anything that is cut off, sticks out, or is too small to tap. */
async function inspect(page: import("@playwright/test").Page): Promise<Problem[]> {
  return page.evaluate(() => {
    const problems: string[] = [];
    const vw = document.documentElement.clientWidth;
    const label = (el: Element) => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}.${[...el.classList].slice(0, 3).join(".")} "${(el.textContent ?? "").trim().slice(0, 30)}"`;
    const inScroller = (el: Element) => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX;
        if (o === "auto" || o === "scroll") return true;
      }
      return false;
    };
    if (document.documentElement.scrollWidth > vw) problems.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${vw})`);
    const h1s = document.querySelectorAll("h1").length;
    if (h1s !== 1) problems.push(`${h1s} h1 headings`);
    for (const el of document.querySelectorAll("main *")) {
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none" || el.closest("[aria-hidden='true']")) continue;
      if (box.right > vw + 1 && !inScroller(el)) problems.push(`sticks out of the screen: ${label(el)}`);
      // Text clipped by its own box (a long word in a fixed-width box).
      if (!el.classList.contains("sr-only") && el.children.length === 0 && el.textContent?.trim() && style.overflow === "hidden" && style.textOverflow !== "ellipsis" && el.scrollWidth > el.clientWidth + 1) {
        problems.push(`text is cut off: ${label(el)}`);
      }
      // WCAG 2.2 target size (minimum): 24 x 24 CSS px, unless it is a link inside a sentence.
      const tag = el.tagName;
      const isControl = tag === "BUTTON" || tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || (tag === "A" && style.display !== "inline");
      if (isControl && (el as HTMLInputElement).type !== "hidden" && !el.classList.contains("sr-only") && (box.width < 24 || box.height < 24)) {
        problems.push(`target smaller than 24px: ${label(el)} (${Math.round(box.width)}x${Math.round(box.height)})`);
      }
    }
    return [...new Set(problems)];
  });
}

test.describe("layout on every page and screen size", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await seedJobs(page);
  });

  for (const size of SIZES) {
    test(`no overflow, clipped text or tiny targets at ${size.name} (${size.width}px)`, async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      const report: Record<string, Problem[]> = {};
      for (const route of ROUTES) {
        await page.goto(route);
        await page.getByRole("heading", { level: 1 }).first().waitFor();
        await page.waitForLoadState("networkidle");
        const problems = await inspect(page);
        if (problems.length) report[route] = problems;
        await page.screenshot({ path: `e2e/.shots/layout/${size.name}${route === "/" ? "/today" : route}.png`, fullPage: true });
      }
      expect(report).toEqual({});
    });
  }

  test("the phone navigation drawer opens, lists every page, and closes on choosing one", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).click();
    const nav = page.getByRole("dialog", { name: "Navigation" });
    for (const label of ["Today", "Jobs", "Apply list", "Learn", "Activity", "Profile"]) {
      await expect(nav.getByRole("link", { name: label })).toBeVisible();
    }
    await nav.getByRole("link", { name: "Activity" }).click();
    await expect(page).toHaveURL(/\/tasks$/);
    await expect(page.getByRole("dialog", { name: "Navigation" })).toHaveCount(0);
  });

  test("dark mode keeps the same layout", async ({ page }) => {
    await setTheme(page, "dark");
    await page.setViewportSize({ width: 375, height: 812 });
    for (const route of ["/", "/profile", "/tasks", "/apply"]) {
      await page.goto(route);
      await page.getByRole("heading", { level: 1 }).first().waitFor();
      expect(await inspect(page), route).toEqual([]);
    }
  });

  test("an unknown address shows a friendly page with a way back", async ({ page }) => {
    await page.goto("/this-page-does-not-exist");
    await expect(page.getByText("That page does not exist")).toBeVisible();
    await page.getByRole("link", { name: "Go to Today" }).click();
    await expect(page).toHaveURL(/\/$/);
  });
});
