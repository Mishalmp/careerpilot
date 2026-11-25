# Production readiness and security: what exists, what does not (2026-11-09)

Honest scorecard. "Verified" says how it was checked in this session; anything marked "not verified" was not. This extends `12-dynamic-platform-and-production-readiness.md` and is written after the unauthorized-key incident (`15-incident-2026-11-09-unauthorized-api-key.md`).

Marks: **Yes** (built and tested), **Partly**, **No** (not built), **You** (only the owner can do it).

## 1. What happened to the money, and what it taught

A second API key, created under the owner's console account, spent $24.49 on Opus while the app's own key spent $0.02. The app cannot stop a stolen key. Only the provider can: a **monthly spend limit in the console**, a separate workspace with its own small limit, auto-reload off, and a prepaid balance kept small. These are owner actions (**You**) and are listed in the incident page. The app's own budgets (section 3) protect against *this app* misbehaving, which is a different risk.

## 2. Security checklist

| Area | Status | Detail and how it was checked |
|---|---|---|
| Passwords | **Yes** | Argon2 hashing, 12-character minimum at creation (`core/security.py`, `modules/auth/service.py`); login body capped at 1,024 characters so hashing cannot be used as a CPU attack. |
| Brute force | **Yes** | Login throttle by failure count and window (`auth/throttle.py`), tested. |
| Sessions | **Partly** | Random server-side token, HttpOnly, SameSite=Lax, 7-day life. **`cookie_secure` defaults to false (fine on localhost); it must be true behind HTTPS.** No second factor (single local user). |
| CSRF | **Yes** | `Authenticated` enforces the CSRF header on every unsafe method; Origin check middleware rejects foreign origins. |
| Authorization | **Yes** | Every query is scoped by `owner_id`; each resource has a cross-owner test. |
| Input validation | **Yes** | Pydantic schemas everywhere; links must be http(s); pasted job links are validated and never opened (`tracker/links.py`). |
| SSRF | **Yes** | One safe fetcher: private addresses, size, time and blocked sites refused. **Fixed today:** it wrongly refused ordinary sites on networks that translate IPv4 to IPv6 (NAT64, like this one); it now judges the IPv4 address inside, so `64:ff9b::7f00:1` (loopback) is still refused and real sites work. Tested. |
| Prompt injection | **Yes** | Untrusted text wrapped by `data_block`; quotes must appear in the fetched page; verdicts and scores come from code; no tool can send, delete or change settings. |
| Model spend | **Yes** | Token cap, **dollar budgets (daily $1, monthly $12 by default) checked before each call**, per-call `max_tokens`, one retry that no longer echoes a cut-off reply, cached job readings. See section 3. |
| Secrets in the repo | **Yes** | `.env` git-ignored and never committed; a test (`test_hardening.py`) fails if an Anthropic key, Telegram bot token, private key or AWS key appears in any tracked file. |
| Secrets in logs | **Yes** | Telegram client never puts the token-bearing address in an error or log (httpx request log silenced); errors tested for the token. API keys are `SecretStr`. |
| Response headers (API) | **Yes** | `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cache-Control: no-store`, HSTS when `cookie_secure` is on. Tested. |
| Response headers (web) | **Partly** | New page CSP (`next.config.ts`): same-origin scripts/connections, no framing, no plugins, forms to self. **Inline scripts are still allowed** (no nonce yet), so it blocks exfiltration and framing but is not a full XSS defence. The runner's workers keep their own stricter policies. Verified by the browser suite (see section 6). |
| Public API docs | **Yes** | `/docs` and `/openapi.json` are off unless `CAREERPILOT_EXPOSE_API_DOCS=true`. Tested. |
| Rate and size limits | **Yes** | Per-address requests per minute (default 1,200, 0 = off) and a request-size cap (12 MB) return plain 429/413. Tested. In-memory, single process. |
| Dependencies | **Yes (today)** | `pip-audit` on the locked production set: no known vulnerabilities. `npm audit --omit=dev`: 0 vulnerabilities. Lockfiles are committed. **No scheduled re-check (no CI)**, so this is a snapshot. |
| Static analysis | **Yes** | Ruff with the security rules, pyright strict, import-linter (25 contracts), ESLint. |
| Learner code | **Yes** | Runs only in browser workers under their own CSP (ADR 0007); never on the server. |
| Telegram | **Yes** | Only the one configured chat id is answered; backlog dropped on start; no command sends or submits anything; the model is never called from it. Needs a token from @BotFather (**You**). |
| Application-level encryption of stored CV text, contacts, notes | **No** | Stored as plain text in Postgres. Protection today is the machine's disk encryption. **BitLocker status could not be read (needs administrator); please check Settings > Privacy & security > Device encryption / BitLocker.** |
| Database at rest | **No** | Docker volume unencrypted; relies on disk encryption. |
| Backups | **Yes** | Encrypted with a key that lives only in the environment; restore always creates a new database (tested earlier). Not re-run today. |
| Encryption in transit | **No** | Local HTTP only. Going beyond localhost needs a TLS reverse proxy (for example Caddy) and `cookie_secure=true`; not built or tested. |
| DB least privilege | **No** | The app uses the same Postgres role that owns the schema (superuser in the dev container). Production wants a migration role and a limited app role. |
| Multi-factor / account recovery | **No** | Single local user; password reset is a command-line action only (by design). |
| Data export and deletion | **No** | No "export all my data" or "delete my account" feature (needed once there are other users). |
| Audit trail | **Partly** | AI calls (with cost), task history, MCP writes, outreach approvals are recorded; sign-in events and settings changes are not. |

## 3. Cost control (measured)

Live run on 2026-11-08 with the real key: 19 model calls, about $0.022 in total, matching the console's $0.02.

| Task | Measured | Earlier estimate |
|---|---|---|
| Research one job (about 10 pages, Haiku) | about $0.011 | $0.012 |
| Read one job description (Haiku) | about $0.0001 | $0.0005 |
| Connection check (Sonnet) | under $0.001 | n/a |

At those prices the planned usage costs a few dollars a month. Safeguards: dollar caps (`CAREERPILOT_LLM_DAILY_BUDGET_USD`, `..._MONTHLY_BUDGET_USD`), a worst-case price check before each call (input size at 3 characters per token plus the full `max_tokens`), exact costs stored per call and shown in Activity, repeat scoring reuses the stored reading, a reply cut off for length is retried shorter instead of echoed back, and when the provider says the balance is empty the client names that, pauses for ten minutes instead of asking repeatedly, and says which features keep working.

## 4. Operations checklist

| Area | Status | Detail |
|---|---|---|
| Liveness/readiness | **Yes** | `/healthz` and `/readyz` (database and migration head). |
| Structured logs with request ids | **Yes** | One line per request, no bodies. |
| Background work visible and retryable | **Yes** | Activity shows tasks, attempts, steps and, new today, **result lines** ("Remote OK: 99 listed, 0 fit your searches. Left out: ...") and the AI calls with their cost. |
| Migrations | **Yes** | Alembic with a drift test; head is 0024. |
| CI/CD | **No** | No pipeline and no GitHub repository yet (tasks X09, X10). Everything is run by hand. |
| Alerts and metrics | **No** | Nothing pages anyone. A Telegram alert on failed tasks or budget use would be a small next step. |
| Worker liveness | **No** | No heartbeat; a dead worker is noticed only because nothing new appears. |
| Error tracking | **No** | Logs only. |
| Disaster recovery targets | **No** | Backups exist; recovery time and data-loss targets are not written down. |
| Environments | **Partly** | Dev and E2E databases are separate; no staging/production profile files. |

## 5. Job coverage, honestly

Read automatically (all terms allow it): company boards on Greenhouse, Lever and Ashby, and five free feeds (Remote OK, Remotive, We Work Remotely, Himalayas, Arbeitnow). **New today:** a checked list of 64 real company boards (`content/job-boards.yaml`, verified live on 2026-11-09 and 2026-11-10), most with roles in India (for example Paytm 162, Okta 104, Databricks 89, Zscaler 82, MongoDB 77, Pure Storage 65, Meesho 51, InMobi 46, HighRadius 46), followed with one click on the Discover page.

Not read, by design: LinkedIn, Indeed, Glassdoor, Naukri (terms forbid automation, accounts get banned). The legal ways in are built: paste their job links on the Jobs page (or send them to the Telegram bot) and the app stores them for you to click and apply yourself; it then finds the company's own site and published hiring emails by rules.

Not built, and why: **Adzuna** (not free: Adzuna's sign-up page offers 25 free test calls, then 8 GBP a month for 5,000 calls; this document first called it a free key, which was wrong) and **Jooble** (key by request form; price and India coverage not stated on its page), **JSearch** (paid beyond a small free plan), **job-alert emails** (needs a mailbox connection and your decision). The honest consequence: **India on-site and hybrid coverage is thin** (a few Indian companies on the list above, plus whatever you paste) until one of those is added.

Why the list was empty on Nov 8: the daily list is built from the tracker; discovered listings only reached the tracker if you accepted each by hand; your one search was "India on site or hybrid", and the free feeds are almost all remote jobs, so no listing fitted. Nothing showed why. Fixed: listings that fit your searches and your CV are copied in automatically (cap `auto_add_limit`), every run writes a result line saying what it read and what it left out and why, and an empty Apply list shows what the last build found.

## 6. Verification status at the end of this session

See `STATUS.md` for the exact numbers of the last full runs (API suite, browser suite, type and lint checks).
