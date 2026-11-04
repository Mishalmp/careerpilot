# 0007: Practice runner details

Status: accepted (2026-11-05). Builds on [0005](0005-browser-first-code-runner.md); the spikes it called for (S1, S2) passed.

## What was proven in a real browser
- **Python** (Pyodide), **SQL** (PGlite, PostgreSQL in WebAssembly) and **JavaScript** each run in a Web Worker, served by this app. Nothing loads from a CDN.
- Cold start is about 3 seconds for Python and for SQL; JavaScript is instant. Runtimes stay warm between runs.
- An infinite loop cannot be interrupted from inside the worker, so the page terminates the worker after a per-test limit (3 s JavaScript, 5 s Python and SQL), reports the stuck test as timed out, marks the rest "not run", and starts a fresh worker on the next run. The page stays responsive.

## Isolating learner code
Learner code (yours, or something pasted from the internet) must not be able to call this app's API with your session.
- Each worker script is served with its **own Content-Security-Policy** (`next.config.ts`). A worker's policy is the one on its script's response.
  - JavaScript: `connect-src 'none'`, so `fetch`, XHR and WebSocket all fail. Verified: `fetch("/api/v1/auth/me")` is blocked.
  - Python and SQL: `connect-src` lists only this app's `/pyodide/`, `/runner/harness.py` and `/runner/pglite/` paths, pinned to the origins in `RUNNER_ORIGINS` (default `localhost:3100` and `127.0.0.1:3100`). Verified: Python reaching `/api/...` is blocked while its own runtime files load.
- If you open the app from another origin, set `RUNNER_ORIGINS` or Python and SQL will fail to load (JavaScript still works).
- Still reachable from a worker: same-origin IndexedDB and Cache Storage (this app stores nothing there). Memory and CPU are not capped except by the time limit.

## Deliberately not done
- **No page-wide CSP yet.** A strict page CSP needs per-request nonces, which forces dynamic rendering and fights the static shell this app uses. The page itself renders only trusted data (Markdown without raw HTML, http(s)-only links), so the worker policies cover the new risk. Revisit with TLS and an identity provider before any exposure beyond localhost.
- **No server-side execution.** See 0005.

## Editor: CodeMirror 6, not Monaco
The plan said Monaco. Monaco needs several megabytes, a CDN by default, and worker plumbing that does not fit the bundler cleanly; its IntelliSense is not needed to solve interview problems. CodeMirror 6 is small, bundles normally, and has Python, JavaScript/TypeScript and PostgreSQL modes. Tab indents; Escape then Tab leaves the editor for keyboard users.

## Problems and results
- One YAML file per problem in `content/problems/`. Function problems declare a signature once; Python, JavaScript and TypeScript starters are generated. Tests are JSON, so the same tests run in every language. SQL problems give a schema plus several datasets, so a query that hard-codes the sample answer fails the next dataset.
- Tests run in the browser, so **hidden tests are hidden from the screen, not from the browser**, and submitted pass counts are self-reported. That is fine for solo practice and is not a grading system. The server checks that a submission matches the problem (language, test count, `passed` equals the per-test results) and keeps the newest 30 per problem.
- TypeScript is transpiled with sucrase (types removed, not checked); the tests decide correctness.
- The comparison rules (strict equality, unordered, unordered-nested, float tolerance) exist twice, in `harness.py` and `js-worker.js`. Both are tested against one shared list, `public/runner/compare-cases.json`. The Python harness is also the file the API tests use to check every problem.

## How problems are kept honest (tests in `test_problem_content.py`)
Every function problem has an independently written reference solution in `tests/problem_solutions.py`; it must pass all tests. An empty starter and a "return the first argument" answer must each fail. Every SQL reference runs on real PostgreSQL against every dataset. Topic keys must exist in the curriculum, every `practice:` link in the guides must resolve, and every problem must be linked from some guide.
