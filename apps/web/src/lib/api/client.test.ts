import { afterEach, describe, expect, it } from "vitest";

import { csrfMiddleware, problemTitle, setCsrfToken } from "./client";

function run(method: string) {
  const request = new Request("http://localhost/api/v1/x", { method });
  const options = {} as Parameters<NonNullable<typeof csrfMiddleware.onRequest>>[0];
  return csrfMiddleware.onRequest!({ ...options, request }) as Request;
}

describe("csrfMiddleware", () => {
  afterEach(() => setCsrfToken(null));

  it("adds the token to state-changing requests", () => {
    setCsrfToken("abc");
    expect(run("POST").headers.get("X-CSRF-Token")).toBe("abc");
    expect(run("DELETE").headers.get("X-CSRF-Token")).toBe("abc");
  });

  it("leaves safe methods alone", () => {
    setCsrfToken("abc");
    expect(run("GET").headers.get("X-CSRF-Token")).toBeNull();
  });

  it("sends nothing before a session exists", () => {
    expect(run("POST").headers.get("X-CSRF-Token")).toBeNull();
  });
});

describe("problemTitle", () => {
  it("reads the title of a problem response", () => {
    expect(problemTitle({ title: "Invalid credentials" })).toBe("Invalid credentials");
  });

  it("falls back for anything else", () => {
    expect(problemTitle(undefined)).toBe("Something went wrong");
    expect(problemTitle({ title: 5 }, "x")).toBe("x");
  });
});
