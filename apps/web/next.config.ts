import type { NextConfig } from "next";

// Server-side only. The browser always talks to this app, which forwards /api to the backend,
// so the session cookie is same-origin and the backend needs no CORS.
const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

// The practice runner executes the learner's own (or pasted) code in workers. Each worker script
// is served with its own Content-Security-Policy, and a worker's policy is the one on its script's
// response. JavaScript gets no network at all. Python and SQL may fetch only their own runtime
// files, with paths pinned to this app's origin(s) so they cannot call /api (which would carry
// the session cookie). RUNNER_ORIGINS must list every origin you open the app from.
const runnerOrigins = (process.env.RUNNER_ORIGINS ?? "http://localhost:3100,http://127.0.0.1:3100").split(",");
const onlyPaths = (...paths: string[]) =>
  runnerOrigins.flatMap((origin) => paths.map((path) => `${origin}${path}`)).join(" ");

const workerPolicies = {
  "/runner/js-worker.js": "default-src 'none'; script-src 'unsafe-eval'; connect-src 'none'",
  "/runner/python-worker.js": `default-src 'none'; script-src 'self' 'wasm-unsafe-eval' 'unsafe-eval'; connect-src ${onlyPaths("/pyodide/", "/runner/harness.py")}`,
  "/runner/sql-worker.js": `default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src ${onlyPaths("/runner/pglite/")}`,
};

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
  async headers() {
    return [
      ...Object.entries(workerPolicies).map(([source, policy]) => ({
        source,
        headers: [{ key: "Content-Security-Policy", value: policy }],
      })),
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
