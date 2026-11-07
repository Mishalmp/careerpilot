import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

/** Adds the CSRF header to every state-changing request once a session exists. */
export const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (csrfToken && !SAFE_METHODS.has(request.method)) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });
api.use(csrfMiddleware);

/** An RFC 9457 problem response from the API. `code` is set for rule failures like note_required. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    title: string,
    readonly detail?: string,
    readonly code?: string,
  ) {
    super(detail ? `${title}: ${detail}` : title);
  }
}

/** Return the data of an openapi-fetch result, or throw an ApiError built from the problem body. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const body = (result.error ?? {}) as { title?: string; detail?: string; code?: string; errors?: unknown };
  throw new ApiError(
    result.response.status,
    body.title ?? "Request failed",
    typeof body.detail === "string" ? body.detail : validationDetail(body.errors),
    body.code,
  );
}

/**
 * "Validation failed" alone tells you nothing. The API also lists each rejected field with the
 * reason, so say which field and why ("links.0: a github link must be on github.com").
 */
export function validationDetail(errors: unknown): string | undefined {
  if (!Array.isArray(errors) || errors.length === 0) return undefined;
  return errors
    .slice(0, 3)
    .map((e: { loc?: unknown[]; msg?: string }) => {
      const where = (e.loc ?? []).filter((part) => part !== "body").join(".");
      const reason = (e.msg ?? "is not valid").replace(/^Value error, /, "");
      return where ? `${where}: ${reason}` : reason;
    })
    .join("; ");
}

/** Reads the `title` of an RFC 9457 problem response, falling back to a generic message. */
export function problemTitle(error: unknown, fallback = "Something went wrong"): string {
  if (error && typeof error === "object" && "title" in error) {
    const title = (error as { title: unknown }).title;
    if (typeof title === "string") return title;
  }
  return fallback;
}
