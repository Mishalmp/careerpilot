import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Covers REQ-01/REQ-05 (docs/phase-7): every text/background token pair meets WCAG AA in both themes.
describe("design tokens", () => {
  it("pass the contrast check in light and dark", () => {
    const script = join(process.cwd(), "scripts", "check-contrast.mjs");
    const out = execFileSync(process.execPath, [script], { encoding: "utf8" });
    expect(out).toContain("all pairs pass");
    expect(out).not.toContain("FAIL");
  });
});
