# 06: Concepts primer (for an intermediate engineer)

Plain explanations of the ideas this system uses, how each shows up in CareerPilot, how it fails, and what you could say about it in an interview. Each section becomes an explorer concept page (task W01). Where I describe external facts (for example how a library behaves) I say so; where I describe our code, the file named is the place to check.

Format per concept: **Idea** · **In this app** · **How it fails** · **Interview angle**.

## 1. Sessions, cookies and CSRF
**Idea**: after you sign in, the server stores a session row and gives the browser an opaque id in a cookie. `HttpOnly` stops page scripts reading it; `SameSite=Lax` stops the browser sending it on most cross-site requests. CSRF (cross-site request forgery) is a site tricking your browser into sending a state-changing request with your cookie; the fix is a secret token the attacker's page cannot read, sent in a header on unsafe methods (POST, PATCH, DELETE).
**In this app**: the `Authenticated` dependency checks the session and the CSRF header together; `tests/test_security.py` walks every route and fails if one is unprotected.
**Fails**: a new route that reads the cookie by hand skips CSRF; a session never expires; the cookie lacks `Secure` over HTTPS.
**Interview**: "cookie vs token auth", "why SameSite is not enough alone", "where would you store a JWT and why (usually not localStorage)".

## 2. Password hashing
**Idea**: store a slow, salted hash (argon2/bcrypt), never the password. Slowness makes guessing expensive. Rehash on login when parameters are raised.
**In this app**: check the hashing parameters in the users module (task B09 reviews them).
**Fails**: fast hashes (SHA-256), no salt, no throttle on guesses (our throttle is in memory today; B08 persists it).

## 3. SSRF (server-side request forgery)
**Idea**: if the server fetches URLs a user supplies, an attacker can make it call internal addresses (cloud metadata, localhost, private ranges). Defence: resolve the host yourself, reject private/loopback/link-local/reserved ranges for every address, re-check on every redirect, cap size and time, allow only http(s).
**In this app**: everything that fetches goes through `core/fetcher.Fetcher`; research adds robots.txt and rate limits (R03). Blocked sites (LinkedIn, Indeed, Glassdoor, Naukri) are refused for terms-of-service reasons, not security.
**Fails**: DNS rebinding (name resolves to a public IP at check time and a private one at connect time: connect to the checked IP), IPv6 forms (`::ffff:127.0.0.1`), decimal/octal IP spellings, redirects to internal hosts, huge responses. H21 extends the tests.
**Interview**: "how do you build a link preview service safely".

## 4. Prompt injection
**Idea**: a model cannot reliably tell instructions from data in the same text. Fetched pages, job descriptions, notes and your own answers may contain "ignore previous instructions...". Defences stack: (1) wrap untrusted text as data with clear delimiters and say so in the system prompt; (2) give the model no dangerous tools in the same call; (3) validate output shape; (4) verify claims in code (quotes must appear in the source); (5) human approval before anything enters the knowledge base or leaves the machine; (6) least privilege.
**In this app**: `core/prompts.data_block`, `core/evidence.quote_appears`, outreach has no send action, the research inbox needs approval, MCP writes preview first.
**Fails**: a model "obeys" hidden text and produces a plausible but wrong summary; defence (4) catches fabricated quotes but not a true-but-misleading quote, which is why the owner approves.
**Interview**: "indirect vs direct injection", "why filtering keywords is not a defence".

## 5. Transactions, isolation and locking
**Idea**: a transaction groups writes so they all happen or none do. Default isolation in Postgres (read committed) means each statement sees committed data as of its start. Lost updates are prevented by optimistic concurrency (a version column checked in the `UPDATE ... WHERE version = x`) or by `SELECT ... FOR UPDATE`. Deadlocks come from taking locks in different orders; keep transactions short.
**In this app**: services own `commit`; repositories hold SQL; applications have a `version`; the LLM usage row must not be lost when a call fails (H07 audits this). Long work happens outside open transactions.
**Fails**: a transaction held open during a network call; two tabs overwrite each other (we return a conflict); `idle in transaction` sessions block migrations (H08 sets timeouts).
**Interview**: "explain read committed vs repeatable read", "how do you prevent double booking".

## 6. Idempotency
**Idea**: doing an operation twice has the same effect as once. Needed because networks retry. Techniques: natural unique keys, an `Idempotency-Key` header stored with the first response, upserts, and "check state then act" inside a transaction.
**In this app**: task keys, discovery unique constraints, `Idempotency-Key` on creates (B13), quiz answer tokens (L17), checkpoint submit-once (L19).
**Fails**: dedupe only in application code (race between two requests), keys that are not scoped by owner, reusing a key with a different body (should be rejected).
**Interview**: "design an idempotent payment API".

## 7. Queues, leases and retries
**Idea**: a queue decouples "ask for work" from "do work". A worker claims a task with a lease (a time-limited claim) and must finish or renew it; if it dies, the lease expires and another worker takes over, so handlers must be idempotent. Retries use exponential backoff with jitter (random spread) to avoid thundering herds. Tasks that always fail go to a dead-letter state for a human.
**In this app**: the `tasks` table with `FOR UPDATE SKIP LOCKED` (each worker locks different rows without waiting), unique keys, backoff, watchdog; `worker.py` handlers raise `TaskFailure` with a user-readable message.
**Postgres queue vs Celery/Redis**: see `05` section 2. The key point is the **dual-write problem**: with an external broker you commit a database row and publish a message in two steps; a crash between them loses or duplicates work (the fix is an outbox table, which is a Postgres queue anyway). With the queue in the same database, enqueue is part of the same transaction.
**Fails**: non-idempotent handlers; leases shorter than the work; one slow kind starving others (per-kind limits, H02); clock-based leases using worker time (use DB time).
**Interview**: "at-least-once vs exactly-once delivery", "how do you handle poison messages".

## 8. Server-sent events and progress
**Idea**: SSE is a one-way stream from server to browser over HTTP, with automatic reconnect and a `Last-Event-ID` header to resume. Good for progress (we only push server to client). WebSockets are two-way and heavier.
**In this app**: task progress events (B05); polling fallback if the stream is blocked.
**Fails**: proxies buffering the stream, auth on long-lived connections, missing resume so the page shows stale progress.

## 9. Embeddings, chunking and vector search
**Idea**: an embedding model turns text into a vector; similar meaning gives nearby vectors. To search long notes you split them into chunks (size and overlap are trade-offs: small chunks are precise but lose context, big ones blur). Nearest-neighbour search finds the closest chunks; an index (HNSW in pgvector) makes it fast with approximate results.
**In this app**: notes are chunked and embedded locally; chunks live in Postgres with pgvector; `embedding_version` (H12) prevents mixing models.
**Fails**: changing the model without re-embedding; chunks that cut a sentence in half; filter-after-search returning too few rows for one owner (H16 checks pgvector's iterative scan).

## 10. Hybrid search and reciprocal rank fusion (RRF)
**Idea**: keyword search (exact terms, names, error codes) and vector search (meaning) fail differently. Run both, then merge ranked lists. RRF scores each item by `sum(1 / (k + rank))` across lists (k about 60), which needs no score normalisation.
**In this app**: full-text + vector merged by RRF, then a similarity gate refuses weak matches.
**Try it (explorer widget)**: edit two ranked lists and see the fused order.
**Fails**: stop-word and language issues in keyword search; gate threshold set by feel instead of by the eval set.

## 11. RAG and how to evaluate it
**Idea**: retrieval-augmented generation: retrieve passages, put them in the prompt, ask the model to answer only from them and cite. Quality has two parts: **retrieval** (did the right passage come back? recall@k, MRR) and **generation** (is the answer faithful to the passages, does it refuse when the answer is not there?). Evaluate them separately with a labelled question set including unanswerable questions.
**In this app**: `careerpilot eval-rag`, a gate test, and the rule to record numbers before and after any change to chunking, embeddings, ranking or prompts. Answers with invalid citations are withheld.
**Fails**: tiny eval sets (noise), tuning to the test set, citation that points to a passage that does not support the claim (faithfulness check, H14).
**Interview**: "how would you know your RAG got better".

## 12. MCP (Model Context Protocol)
**Idea**: an open protocol that lets an AI client (like Claude) discover and call **tools**, read **resources** and use **prompts** from a server, over stdio (local process) or HTTP. The server describes each tool with a name, description and typed input schema; the client's model decides when to call it. The newest spec revision we found (2026-07-28) moves toward stateless requests and optional extensions; we plan to align (H17).
**In this app**: the MCP server exposes tools that call services; writes **preview** until `confirm=true` and are audited; there is no send/delete/settings tool; user-facing problems use `ToolError`.
**Why those rules**: a tool result can contain injected text, and the model can be talked into misuse; so the dangerous actions simply do not exist, and writes need a second explicit step.
**Fails**: overly broad tools, vague descriptions (the model picks wrong tool), huge outputs, spec drift.

## 13. Agents vs workflows
**Idea** (Anthropic's guidance): a **workflow** is code-controlled steps with model calls inside (chaining, routing, parallel, orchestrator-workers, evaluator-optimizer); an **agent** lets the model choose steps and tools in a loop. Use the simplest thing that works; agents cost more, are harder to test and can wander.
**In this app**: the research run is a workflow (fixed stages, budgets); mock interviews are a turn loop with code deciding when to stop; QA agents (T13, T14) are real agents, kept outside production and reviewed by a human.
**Fails**: unbounded loops, no budget, no stop condition, trusting agent output without verification.

## 14. Grounding, quote verification and hallucination control
**Idea**: models can state false things fluently. Make claims checkable: require the supporting quote, then check in code that the quote occurs in the source text (after normalising whitespace/quotes) and that it fits the claim. A second, independent call that does not see the answer key can test MCQ keys ("blind answer"). Label what could not be verified.
**In this app**: `core/evidence.quote_appears`; question statuses `verified` / `unverified` (`03`).
**Fails**: quote exists but does not support the claim (needs the fit check and human approval); source itself is wrong (reliability score, owner review).

## 15. Token budgets, cost and caching
**Idea**: you pay per input/output token; costs differ per model. Control with: smaller inputs (extract main content), cheaper models for easy steps, caps per call/run/day in money not just tokens, and **prompt caching** (reuse a long unchanged prefix at a discount; measure before adopting). Long outputs should stream to avoid timeouts.
**In this app**: daily token cap today; USD caps planned (E08, E09); caching decision E10; research budgets (`03`).
**Fails**: caps that count tokens only; retry storms multiplying cost; no visibility.

## 16. Spaced repetition and FSRS
**Idea**: memory fades; reviewing just before you would forget is the efficient moment. FSRS models each card with **stability** (how long until recall drops to the target), **difficulty**, and **retrievability** (current recall probability), and schedules the next review for a target retention (we start at 90%). You grade each review Again/Hard/Good/Easy.
**In this app**: Python `fsrs` package (pinned) behind a scheduler interface (L08); rating from correctness, confidence and time (L09).
**Try it**: simulate answer patterns and see intervals.
**Fails**: too many new cards per day (reviews pile up; we cap), grading honesty (self-rated cards), changing parameters without migration.

## 17. Content Security Policy (CSP)
**Idea**: a response header that tells the browser which sources of scripts/styles/frames are allowed, limiting the damage of XSS. Inline scripts are blocked unless they carry a nonce or hash.
**In this app**: the pages currently send no CSP (adding one is H20); learner code runs in browser workers under their own CSP (ADR 0007); the theme-initialisation script must be compatible (D05).
**Fails**: loosening CSP for convenience (`unsafe-inline`), third-party scripts, new libraries needing `eval`.

## 18. Database migrations (expand/contract)
**Idea**: change schema in safe steps so old and new code both work: add nullable column → deploy code that writes both → backfill → switch reads → drop old. Never rename or drop in one step on a live system. Create big indexes concurrently. Test up and down.
**In this app**: Alembic, a drift test comparing models to migrations; migration 0012 once broke `/readyz` by running a function at import time (lesson recorded; H09 prevents repeats).

## 19. Observability
**Idea**: logs (what happened), metrics (how much, how fast), traces (where time went), tied together by a request id. Alert on symptoms users feel.
**In this app**: request and task ids in logs (B16), `/system/status` (B01), metrics endpoint (B17).

## 20. Multi-tenancy
**Idea**: many users share one deployment; isolation is enforced in every query (`owner_id`), tested for every resource, and extended to caches, files, background tasks, rate limits and costs. Row-level security in Postgres is a stronger option for later.
**In this app**: rule "every query scoped by owner_id" plus a cross-owner test per resource.
**Fails**: a join that forgets the filter; a cache keyed without the owner; an admin tool that bypasses scoping.

## 21. Backups and restore testing
**Idea**: a backup you have not restored is a hope. Encrypt backups, keep the key apart, restore into a **new** database, compare row counts, rehearse.
**In this app**: `core/backup.py` (AES-256-GCM, version check against the server), restore never writes into the live database; scheduled restore drill (H10).

## 22. Testing strategy ideas
**Pyramid**: many fast unit tests, fewer integration tests against a real database, a few end-to-end browser tests. **Property tests** state rules ("a checkpoint never repeats a question") and let a tool find counter-examples. **Mutation tests** change the code to see whether tests notice. **Evals** are tests for model behaviour: a labelled set, a metric, a threshold. **AI QA agents** explore the UI like a person and report; they are non-deterministic, so their output is a lead for a human, not a gate. Details in `10-test-strategy.md`.

## 23. How to talk about this project honestly
Claim only what the repository proves: for example "a Postgres-backed queue with SKIP LOCKED, idempotent keys and a watchdog, tested with crash drills" (after T11), not "scales to millions". Say what you chose not to do (no Celery/Redis, why) and what you would change at larger scale (stage table in `09`). W05 turns this into a reviewed list.

## 24. Reading list (checked sources, verify before relying)
Anthropic: "Building effective agents"; Claude Code best practices; the MCP specification and changelog (modelcontextprotocol.io); Radix Colors docs; shadcn/ui docs; FSRS algorithm wiki (open-spaced-repetition); Postgres documentation on `SKIP LOCKED` and transaction isolation; OWASP cheat sheets (SSRF, CSRF, session management, LLM top 10); WCAG 2.2 quick reference.
