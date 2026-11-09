import { expect, test } from "./fixtures";

// covers: page security headers (docs/phase-7/16): the page policy is sent, scripts and requests stay
// on this origin, and the runner's workers keep their own stricter policy (a second one would break WebAssembly)

test("pages carry a content security policy that keeps everything on this origin", async ({
  request,
}) => {
  const res = await request.get("/login");
  const csp = res.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("connect-src 'self'");
  expect(csp).not.toContain("unsafe-eval"); // production build: only development needs it
  expect(res.headers()["x-frame-options"]).toBe("DENY");
});

test("the practice runner's workers keep only their own policy", async ({
  request,
}) => {
  const res = await request.get("/runner/python-worker.js");
  const csp = res.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("connect-src");
  expect(csp).toContain("'wasm-unsafe-eval'");
  expect(csp).not.toContain("frame-ancestors"); // not the page policy
});

test("the API answers with its own locked-down headers and hides its docs", async ({
  request,
}) => {
  const api = await request.get("/api/v1/auth/me");
  expect(api.headers()["content-security-policy"]).toBe(
    "default-src 'none'; frame-ancestors 'none'",
  );
  expect(api.headers()["x-content-type-options"]).toBe("nosniff");
  expect((await request.get("/api/docs")).status()).toBe(404);
});
