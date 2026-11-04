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

/** Reads the `title` of an RFC 9457 problem response, falling back to a generic message. */
export function problemTitle(error: unknown, fallback = "Something went wrong"): string {
  if (error && typeof error === "object" && "title" in error) {
    const title = (error as { title: unknown }).title;
    if (typeof title === "string") return title;
  }
  return fallback;
}
