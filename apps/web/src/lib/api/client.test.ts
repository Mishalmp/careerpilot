import { afterEach, describe, expect, it } from "vitest";

import { csrfMiddleware, problemTitle, setCsrfToken, validationDetail } from "./client";

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

describe("validationDetail", () => {
  it("names the field and the reason, without the technical prefix", () => {
    expect(
      validationDetail([{ loc: ["body", "links", 0], msg: "Value error, a github link must be on github.com" }]),
    ).toBe("links.0: a github link must be on github.com");
  });

  it("lists at most three problems and says nothing when there are none", () => {
    const many = Array.from({ length: 5 }, (_, i) => ({ loc: ["body", `f${i}`], msg: "bad" }));
    expect(validationDetail(many)?.split("; ")).toHaveLength(3);
    expect(validationDetail([])).toBeUndefined();
    expect(validationDetail("nope")).toBeUndefined();
  });
});
