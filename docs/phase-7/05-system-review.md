# 05: Senior system review (issues, redesigns, failure behaviour)

Written from the code as of commit `80f06d9` and the Phase 7 requirements. Every item has a **severity** (S1 fix before new features, S2 fix in Phase 7, S3 fix when touched), a **decision** and the **task ids** that implement it (`07-tasks.md`). Claims marked *(verify)* were not measured; measure them at the task named.

Honest baseline: 809 backend tests and 42 web tests pass locally. GitHub CI has never run (no remote). No real Claude API call has ever been made, so every model feature is tested with fakes only. There is no browser end-to-end suite and no accessibility test.

## 1. Ranked findings
| # | Sev | Finding | Why it matters | Decision | Tasks |
|---|---|---|---|---|---|
| 1 | S1 | No live model call has ever been made | Prompts, JSON repair, token accounting and cost caps are unproven against the real API | Run `llm-check` and a small eval set with a real key before building more AI features | E01-E04 |
| 2 | S1 | CI never ran | Config errors surface late; "green" is local only | Create the remote, run CI, fix | X09, X10 |
| 3 | S1 | Long operations run inside requests (company check, intel, scoring read, mock turn, ask) | A slow model or site holds a connection; a client timeout loses the result | Move to tasks (202 + id) with progress events | B04, B05, H01 |
| 4 | S2 | Token cap is in tokens, not dollars; no per-run budget | Daily cap does not bound money when models differ | Store price table, compute USD per call, caps in USD per call/run/day | E08, E09 |
| 5 | S2 | Login throttle is in memory | Resets on restart, not shared across processes | Move counters to the database (or Redis later) | B08 |
| 6 | S2 | MCP server follows an older protocol revision | Spec version 2026-07-28 changed negotiation and added extensions | Review the spec diff, update server, keep tools read-only/preview-only | H17, H18 |
| 7 | S2 | RAG: no embedding version on chunks, eval set small, no reranker | Changing models silently mixes vectors; quality numbers are noisy | Add `embedding_version`, grow eval set to >= 60 questions (H14 targets 100), test a reranker only if recall is the problem | H12-H14 |
| 8 | S2 | Tasks have no heartbeat/lease expiry visible, no dead-letter view, no per-kind concurrency | A crashed worker leaves `running` rows; a flood of one kind starves others | Lease column + watchdog (exists in part), tasks screen, per-kind limits | B02, H02-H05 |
| 9 | S2 | No retention or growth policy for `llm_calls`, `audit_events`, `intel_sources`, `discovered_jobs`, `tasks` | Tables grow without bound | Retention job + indexes + size on status page | B10, H11 |
| 10 | S2 | No statement/lock/idle timeouts on the database connection | One bad query can hold locks | Set `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout` per connection | H08 |
| 11 | S2 | Frontend: no E2E, no a11y test, no error boundary per route, ad-hoc styles | Regressions are found by hand | Playwright suite + axe + design system | T01-T05, D18-D20 |
| 12 | S2 | Sync work in async handlers (CPU: chunking, rule scoring) | Blocks the event loop under load *(verify)* | Measure; move heavy CPU to worker or threadpool | B11, T10 |
| 13 | S3 | Seeded curriculum is hard-coded content (159 topics) | Conflicts with "nothing predefined" | One-time import into `topics`, then editable | L02, L07 |
| 14 | S3 | Profile is a YAML file | No UI; hard for another user | Move to DB table with edit screen and history | B03, B20 |
| 15 | S3 | No idempotency keys on create endpoints | Retry after timeout can duplicate | `Idempotency-Key` on creates used by retries | B13, H06 |
| 16 | S3 | No structured request id across API, worker and logs | Hard to trace a failure | Request/task id in every log line and error body | B16 |
| 17 | S3 | Backups are manual | Data loss risk | Scheduled backup task + age on status; restore drill | H10, H26 |
| 18 | S3 | Only Postgres runs in Docker | "Whole stack in containers" not met | Dockerfiles + compose profile | K01-K10 |

## 2. Queue design: stay on Postgres, or Celery/Redis?
**Today**: a `tasks` table, `FOR UPDATE SKIP LOCKED` claim, idempotent key, retries with backoff, handlers in `worker.py`.
| Option | Pros | Cons | Fit |
|---|---|---|---|
| Keep Postgres queue (current) | One system to run and back up; transactional with business writes (insert the task in the same commit as the row that needs it, so no lost jobs); easy to inspect with SQL; enough for hundreds of tasks per minute | You write the pieces (leases, priorities, fairness, scheduling); polling latency unless LISTEN/NOTIFY | **Chosen for stages 1 to 4** |
| procrastinate (Postgres queue library) | Same model as ours, with periodic tasks, LISTEN/NOTIFY and retries built in | Another dependency; maintainers have asked for help (check project health before adopting) | Candidate if our code grows past ~400 lines |
| Celery + Redis | Mature, many features, scales out | Two more services; task messages are outside your transaction (a crash between commit and publish loses or duplicates work, so you need an outbox pattern); Windows support is poor; more to learn and run | Only at stage 5 |
| Cloud queue (SQS etc.) | Managed | Cost, lock-in, no local story | Later, if hosted |
**Decision (D-queue, in `01`/`07` as part of B04)**: keep the Postgres queue behind one interface (`enqueue`, `claim`, `complete`, `fail`, `heartbeat`), add what is missing, and document the trigger for moving (queue depth or latency that Postgres cannot meet). Handlers do not change on a move.
**Failure modes and defined behaviour**
| Failure | Behaviour | Test |
|---|---|---|
| Worker killed mid-task | Lease expires; watchdog returns task to `queued` with attempt+1; handler is idempotent | TC-TSK drill |
| Handler raises `TaskFailure` | Message shown to the user; retry with backoff up to max; then `dead` with a Retry button | |
| Handler raises unexpected error | Logged with task id; user sees generic text; retried the same way | |
| Duplicate enqueue | Unique key ignores it, returns the existing task | |
| Poison task (always fails) | `dead` after max attempts, never blocks others | |
| Flood of one kind | Per-kind concurrency limit; others still run | |
| Clock jump | Leases use database time (`now()` in SQL), not worker time | |
| Database down | Worker backs off and reconnects; API returns 503 on `/readyz` | |

## 3. Database
**Transactions**: services own `commit`; repositories never commit. Rule check: grep for `commit(` outside services (add as a lint test). Use the default isolation (read committed) and handle write conflicts with a version column (already on applications) or `SELECT ... FOR UPDATE` for counters (daily caps).
**Idempotency**: task keys, discovered-job unique constraints, `Idempotency-Key` for creates (B06).
**Constraints in the database, not only in Python**: enums via CHECK, foreign keys with deliberate `ON DELETE`, unique natural keys per owner, MCQ option rules (`03` section 4).
**Indexes**: every `owner_id` filter has a composite index starting with `owner_id`; add partial indexes for hot filters (`tasks(status, run_at) WHERE status = 'queued'`, `review_cards(owner_id, due_at)`); verify with `EXPLAIN` on 50k-row seed data (B11). Do not add speculative indexes.
**Migrations**: expand/contract (add nullable column, backfill, switch code, then drop); never rename in one step; each migration tested up and down against a copy; drift test stays. Long locks: `CREATE INDEX CONCURRENTLY` outside a transaction when tables are large.
**Connections**: pool size small and explicit; timeouts set (finding 10); one session per request; no session shared across tasks.
**pgvector**: HNSW index for the chunks table once > 10k chunks *(verify threshold by measurement; H16 checks recall with the owner filter at scale)*; store `embedding_version` (H12); re-embed as a task; never mix versions in one query.
**Retention** (B10; archive plan H11): `llm_calls` keep 180 days of detail then roll up per day; `audit_events` keep; `tasks` completed keep 30 days; `discovered_jobs` rejected keep 90 days.
**Backups**: encrypted, restore only into a new DB (existing); add a scheduled restore drill into a temporary database as a task (H10) and show "last verified restore" on status; rehearse disaster recovery once (H26).

## 4. RAG (notes search)
Current: chunk, embed (local model), hybrid search (vector + Postgres full text) merged by reciprocal rank fusion, similarity gate, answers need valid citations.
| Risk | Defined behaviour | Task |
|---|---|---|
| Poor chunk boundaries | Eval set includes boundary cases; chunking changes require `eval-rag` before/after numbers in the PR (existing rule) | H14 |
| Embedding model change | `embedding_version` on chunks; query only same-version chunks; re-embed task; status shows "N chunks stale" | H12 |
| Small eval set | Grow to at least 60 questions incl. 10 unanswerable ones (H14 targets 100); report recall@k, MRR, "refuses when it should" | H14 |
| Prompt injection inside notes | Notes wrapped as data; answers must cite passage ids that exist; uncited answers withheld | exists; add adversarial notes tests (H14) |
| Private notes to the model | Only with key and consent (D6); show a "what leaves the machine" preview in Settings | P15, H22 |
| Stale index after note edit | Content hash per document; reindex task on change | H15 |
| Reranker | Add only if recall@k is good but top-1 is poor; measure before adopting | H13 |
Concepts for you to learn are in `06` (chunking, embeddings, hybrid search, RRF, evaluation).

## 5. MCP server
Current: tools call services (never repositories), writes preview until `confirm=true` and are audited, no send/delete/settings tools, `ToolError` for user-facing errors.
| Risk | Defined behaviour | Task |
|---|---|---|
| Spec drift (latest revision 2026-07-28: stateless requests, per-request capability negotiation, optional extensions such as Tasks) | Read the changelog, update the server, keep pinned SDK version and a test that lists tools and schemas | H17 |
| Tool output carrying injected text from fetched pages | Mark untrusted fields; tests with hostile content | H18 |
| Over-broad tool surface | Keep tool list small, descriptive names, typed inputs, documented in explorer | V10 (concept page) |
| Auth for non-local use | Local stdio only for now; any network transport needs auth (stage 3+) | H17 |
| Long tools | Return a task id and a status tool, not a long call | B05 |

## 6. LLM layer
| Concern | Defined behaviour | Task |
|---|---|---|
| Provider outage / 429 / 529 | Retry with exponential backoff and jitter (max 3), respect `retry-after`; then a clear user message; no partial writes | E11, H07 |
| Timeouts | Per-call timeout; stream long outputs; tasks have their own deadline | E11, E12 |
| Invalid JSON | `call_llm_json` repair once with the validation error, then fail clearly | exists; E03/E04 tests |
| Cost | Price table per model; USD recorded per call; caps per call, run, day; status shows spend | E08, E09, H19 |
| Model change | Model id in settings and stored with each result and prompt version | B03, E07 |
| Prompt versions | New file per version; evals compare versions; never edit a used one (existing rule) | E03, E07 |
| Caching | Use prompt caching for large repeated prefixes (rubrics, system prompts) after measuring; not before | E10 |
| Privacy | Redact profile and contacts before any call; log what was sent (hash + size), not content | H22 |
| No key | Features degrade: deterministic parts work, AI parts show "needs API key" | E01, B01 |

## 7. Research agent risks (new)
| Risk | Defined behaviour |
|---|---|
| Prompt injection in fetched pages ("ignore previous instructions", hidden text) | Page text wrapped as data; extraction schema validated; quotes must verify; no tool use on fetched text; injected instructions never change budgets or actions |
| SSRF / internal addresses | Only through `Fetcher` (resolves DNS, blocks private ranges, re-checks redirects) |
| Cost runaway | Budgets (`03` section 3); hard stop at USD cap; run ends `partial` |
| Hallucinated questions | Grounding rules; unverified items labelled and excluded from checkpoints |
| Low-quality or SEO-spam sources | Domain reliability list (editable), prefer official/engineering/doc sources, show reliability |
| Robots / terms | Respect robots.txt, per-host rate limit, identify with a plain user agent, blocked-site list |
| Search API down | Run fails fast with message; manual paste route still works |
| Duplicate findings | Dedupe by normalised text and URL; merge sources |
| Copyright | Link + short quote + paraphrase only (D7) |

## 8. Security review items
| Item | Status | Action |
|---|---|---|
| Session cookie HttpOnly, SameSite=Lax, CSRF header on unsafe methods, route audit test | exists | keep; add new routes to the audit automatically |
| Login throttle persistence | in memory | B08 |
| Password hashing | argon2 *(verify in code)* | confirm parameters, add rehash on login |
| Page CSP and theme script | Only the code-runner workers have a CSP; normal pages send none (checked in `next.config.ts` 2026-11-06). The theme needs a pre-paint script | Done: theme script is a same-origin file (D05). Next: add a page CSP with nonces and test it (H20) |
| Output encoding for researched text | React escapes; markdown rendering must be sanitised | use a safe renderer, never `dangerouslySetInnerHTML` without sanitising; H20, R13 |
| Secrets | env only; never in the browser | add secret scanning (gitleaks or detect-secrets) as pre-commit and CI, X07; key handling runbook H25 |
| Dependency audit | pip-audit + npm audit in CI | keep |
| Uploads | none today | if added, type/size limits and no execution |
| Rate limiting on expensive routes | partial | B07 |
| Audit log of writes | partial | B06 |
| SSRF suite for the research fetcher | exists for fetcher | H21 |
| Dynamic scan | not done | T12 |
| Multi-user | owner_id everywhere; cross-owner tests per resource | keep as hard rule |

## 9. Frontend gaps
No design system; styles vary by page; no loading/empty/error standard; no keyboard navigation plan; no E2E or accessibility tests; client state mixes server data and UI state; generated API client is good (keep). Fixes: design tokens and primitives (D-group), a standard page checklist (`07`), TanStack Query conventions (keys, invalidation, optimistic updates with rollback), route-level error boundaries, Playwright + axe in CI (T01-T04), visual snapshots for key screens (T05, D20), manual screen-reader pass (T20).

## 10. Failure-mode catalogue (cross-cutting)
| Situation | Expected behaviour | Where tested |
|---|---|---|
| API restarts during a request | Client retries safe GETs; unsafe writes show error and are safe to repeat (idempotency) | T11, H06 |
| Network offline | Banner; reads from cache; writes disabled with reason | P16, T03 |
| Session expired | Redirect to login, return to same page, keep unsent form text | P16, T02 |
| Two tabs edit the same job | Version conflict shown with "reload" | exists; T03 |
| DB constraint violation | 409/422 problem+json with field; no 500 | B14, T07 |
| Model returns refusal/empty | Treated as failure with message; no write | E03, E04 |
| Disk full | Backup fails with clear message; status red | T11, B01 |
| Clock skew | Server time authoritative for deadlines and leases | H05, T11 |
| Huge input | Size limits at API and UI; truncation marked | T07 |

## 11. Multi-user readiness checklist (stage 3)
All tables have `owner_id` and cross-owner tests; settings and API keys per user; per-user caps and quotas; admin-free signup decision (invite only); password reset path without email (admin command) or with email provider later; per-user backups; shared global caches (fetch cache, embeddings model) contain no private data; audit log shows actor. Each unchecked item is covered by B03, B09, B20 and the per-table isolation tests that every L/R task already requires.

## 12. Deletion pass (rule 3)
After Phase 7: remove `prep_topics` code paths after import (L07), remove duplicated card/button styles replaced by primitives (D-group), remove unused CSS, remove in-request long handlers once moved to tasks (B05), remove the YAML profile loader after DB profile (B03). Each is listed as a task step, not a wish.
