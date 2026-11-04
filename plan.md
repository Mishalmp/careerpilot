# CareerPilot: Project Plan

One local-first platform to track job applications, research companies, prepare for interviews, practise code in the browser, and learn how RAG and MCP are built, by building them.

Written 2026-11-03 for Mishal MP. Status: plan, awaiting approval. Nothing is built yet.

---

## 0. Decisions in one screen

| Topic | Decision | Why (short) |
|---|---|---|
| Shape | **Modular monolith**: one FastAPI backend package with a separate worker process and an MCP entrypoint, plus a Next.js web app | One person, one machine, one deadline. Microservices would add deployment and contract work that buys nothing here. Module boundaries are enforced so splitting later is possible |
| Database | **PostgreSQL 16+ with pgvector** (Docker for dev) | Relational data, full-text search and vector search in one store. You already know Postgres. One thing to back up |
| Queue and schedule | **Postgres-backed queue** (procrastinate, to be confirmed in a spike), no Redis | The database is already there; enqueue in the same transaction as your writes; fewer moving parts |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, `uv`, `ruff`, `pytest` | Your stack; strict typing; boring and proven |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind, TanStack Query and Table, dnd-kit, Monaco | Your stack; generated API client so types never drift |
| LLM access | **Provider interface**. Default: **Anthropic API key**. Optional, off by default: local `claude -p` using your own plan | See section 15; the token question is answered there |
| RAG | Own implementation in a `knowledge` module: heading-aware chunking, local embeddings (FastEmbed, 384-d), pgvector HNSW, Postgres full-text, reciprocal rank fusion, evals | You learn the parts; the corpus is small; zero embedding cost |
| MCP | Own **MCP server** exposing the platform to Claude Desktop or Claude Code (stdio first) | You learn the protocol; Claude can then operate your tracker. Read tools and write tools are separated, and there is **no send-email tool** |
| Online compiler | **Browser-first runner**: Python via Pyodide, JavaScript and TypeScript in Web Workers, SQL via PGlite (WASM Postgres). No server-side code execution in the MVP | Safest design for a personal tool; no sandbox to escape. A server runner (Judge0 or similar) is a later, optional adapter |
| Auth | Single local user, password plus session cookie, bound to `127.0.0.1`, CSRF and Host-header checks | Local apps are attackable from other websites; cheap to prevent |
| Tenancy | `owner_id` on user-owned tables from day one, enforced in the repository layer | A few lines now; avoids a painful migration if it ever becomes multi-user |
| Research agents | Read-only, step-limited, tool-limited; **every extracted claim must carry a URL and a verbatim quote that code verifies** | Defence against prompt injection and hallucination |
| Humans in the loop | Anything that leaves your machine (email, applications) needs your explicit approval | Legal, ToS and reputation risk |

**Honest effort estimate:** about 50 to 70 focused hours for Phases 0 to 5 (my estimate; see section 14). With 8 weeks of notice and interview preparation as the top priority, the plan is sliced so the platform is **useful by about day 3** and never blocks prep.

---

## 1. Goals and non-goals

### Goals
1. **Track everything** in one place: jobs, applications with status history, contacts, outreach drafts, follow-ups.
2. **Know the company**: verification checklist, ratings and feedback, interview process and questions (company-specific or inferred from similar companies), always with sources.
3. **Prepare**: 45-day roadmap, topic coverage and confidence, spaced review, mock interviews with scoring, project-defense drills.
4. **Practise**: a code editor with runnable questions; clicking a question anywhere in the app opens it in the editor.
5. **Learn RAG and MCP properly** by building them with evaluation and security, not copying a tutorial.
6. **Quality bar of production code** (types, tests, migrations, observability) without production-scale machinery.

### Non-goals (what we deliberately do NOT build)
- No mass auto-apply, no scraping of LinkedIn, Indeed or Glassdoor, no bots that act on portals. (Terms prohibit it; see the earlier plan.)
- No automatic email sending. Drafts only, you send.
- No microservices, Kubernetes, Kafka, GraphQL, or a separate vector database.
- No server-side arbitrary-code execution in the MVP.
- No multi-user features, billing, or public hosting in the MVP.
- No fine-tuned models, no agent framework (LangChain and similar). Plain Python and typed tool loops are easier to understand and test, and learning the mechanics is a goal.

### Anti-over-engineering rules (applied to every pull request)
1. **Rule of three:** no abstraction until there are three real uses; the only up-front interfaces are the ones a decision below names (LLM provider, discovery source, fetch policy, code runner).
2. **One source of truth per thing:** schema in Alembic; API types generated from OpenAPI; seed content only under `content/`; prompts only under `prompts/`.
3. **No duplicate files or copies:** the markdown guides, curriculum and problems live once in `content/`; the existing `career-kit` copies become pointers, then are deleted.
4. **Every new dependency needs a one-line reason in the PR**, and a removal path.
5. **Delete before adding:** each phase ends with a deletion pass (dead code, unused deps, stale docs).
6. **Complexity must be earned by a real case.** Where a real case exists (SSRF, CSRF, idempotent imports, prompt injection, cost caps), do it properly and say why.

---

## 2. Users and key journeys

Single user (you). Journeys the design must make fast:

1. **Add a job in 20 seconds**: paste URL or JD text, get a normalised job with company, location, work mode, salary conversion, skills and a first score; one click to Shortlist.
2. **Daily loop (20 to 30 min)**: open Today, see due follow-ups and the shortlist, review verification and intel, approve drafts, mark portal, site and email modes done.
3. **Prepare for an interview**: open the application, see its company brief, process, likely topics and questions, start a mock, practise linked problems.
4. **Study session**: open Today's roadmap day, read the guide section, solve linked problems, log time and confidence.
5. **Ask my notes**: question in plain English, answer with citations to your guides, knowledge base and intel.
6. **Let Claude help**: Claude Desktop or Code connects through MCP to list due follow-ups, add a job from text, fetch today's prep plan, record a study session.

---

## 3. Requirements

### 3.1 Functional (MoSCoW)

| ID | Requirement | Priority |
|---|---|---|
| F1 | Jobs: create from URL, pasted text or form; fields from the tracker workbook (location, work mode, job type, salary as posted, currency, converted LPA, visa, posted date, JD text and link, apply link, careers page) | Must |
| F2 | Applications: status workflow with allowed transitions, append-only history, three apply modes (portal, company site, email), follow-up dates | Must |
| F3 | Views: table with filters and saved views, Kanban by status with drag and drop, job detail with tabs, status colours as in the workbook | Must |
| F4 | Contacts: name, role, email, phone, **source URL required for published business contacts**; separate email and phone fields | Must |
| F5 | Company verification: 8-point checklist with evidence, verdict by rule, hard-red-flag override | Must |
| F6 | Ratings and feedback summary per company with source and date | Should |
| F7 | Interview Intel: rounds, process, topics, reported questions, difficulty, confidence, source; similar-company fallback labelled as inferred | Must |
| F8 | Prep: 45-day roadmap with start-date-driven dates, 159 topics with confidence and next-review date, study sessions, guide reader | Must |
| F9 | Mock interviews with an LLM interviewer, rubric scores, weak-topic extraction, transcripts stored | Should |
| F10 | Practice: problem list, Monaco editor, run against tests in Python, JavaScript, TypeScript and SQL; submissions history; deep links from guides, topics, intel questions | Must |
| F11 | Knowledge search ("Ask my notes"): hybrid retrieval, citations, "I do not know" when evidence is weak | Should |
| F12 | MCP server: read tools, guarded write tools, resources, prompts | Should |
| F13 | Scoring: JD match percent, chance estimate, fit score and breakdown, priority | Must |
| F14 | Outreach drafts with the humanisation linter, approval state machine, word counts, Gmail draft (optional) | Should |
| F15 | Discovery adapters for public sources (Greenhouse, Lever, Ashby, selected free APIs) behind a per-domain policy registry; Gmail job-alert parser later | Could |
| F16 | Dashboard and analytics: funnel, response and interview rates, prep progress, daily log | Should |
| F17 | Import from the existing workbook; export to CSV and xlsx; optional one-way Google Sheets sync | Must (import and export), Could (Sheets) |
| F18 | Offer comparison calculator (currency conversion with stored rate and date, fixed vs variable, notice and joining date) | Could |
| F19 | Referral and contact CRM: who could refer you, request status | Could |
| F20 | STAR story bank linked to behavioural prep | Could |
| F21 | Desktop reminders for follow-ups and study blocks | Could |

### 3.2 Non-functional

| Area | Target |
|---|---|
| Security | Section 9. No secrets in the repo, logs or LLM prompts; localhost only by default |
| Reliability | All writes transactional; imports and discovery idempotent; jobs retried with backoff; no data loss on crash; tested backup and restore |
| Performance | List views under 200 ms for 10,000 jobs (indexes, keyset pagination); runner starts under 3 s after first load (Pyodide cached) |
| Maintainability | Strict typing, formatter and linter in CI, module boundaries enforced by import rules, migrations for every schema change |
| Observability | Request IDs, structured logs, an LLM call audit table (tokens, cost, latency, prompt version), health endpoint |
| Cost | Daily LLM cost cap enforced in code (default 2 USD); batch discount for non-interactive work (section 12) |
| Privacy | Minimal personal data about third parties; each contact has a source; delete and export available |
| Portability | `docker compose up` for the database; everything else runs natively; later deployable to AWS (ECS and RDS) without redesign |

---

## 4. Architecture

```
                        Browser (Next.js app, localhost:3100)
                           |  REST + SSE (generated TypeScript client)
                           v
 +-------------------- FastAPI API (localhost:8000) -----------------------+
 |  routers -> services -> repositories (owner_id scoped) -> PostgreSQL     |
 |      |                                                                   |
 |      +-- enqueues jobs (same DB transaction) ---------------+            |
 +------------------------------------------------------------|------------+
                                                              v
        Worker process (same codebase)  <---- Postgres queue ----
          discovery | verification | intel | scoring | embedding | digests
                |            |            |
                |            +-- Fetcher (policy registry, SSRF guard, size/time caps)
                +-- LLM layer (provider interface, budget guard, audit table, prompt registry)

 MCP server (stdio; optional Streamable HTTP with bearer token)  -> calls the SAME services
 Claude Desktop / Claude Code -----------------------------------^

 In the browser only: code runner  [Pyodide worker | JS/TS worker | PGlite]  (no server execution)

 PostgreSQL: relational tables + tsvector (FTS) + pgvector (HNSW) + queue tables
 content/ (git): guides, curriculum, problems, prompts  --seed/ingest-->  database
```

### 4.1 Component responsibilities
- **API**: HTTP only: auth, validation, serialisation. Contains no business logic.
- **Services**: business rules (state machine, scoring, verdict rules, lint). The same functions are called by the API, the worker and the MCP server. This is what prevents duplicated logic.
- **Repositories**: the only place SQL lives; always filter by `owner_id`.
- **Worker**: long or flaky work (fetching, LLM calls, embedding). Idempotent tasks with explicit retry rules.
- **LLM layer**: one interface, budget guard, audit, structured outputs with validation and one repair retry.
- **Fetcher**: the only code allowed to make outbound web requests for research; applies the domain policy and the SSRF guard.
- **MCP server**: thin adapter over services; separate read and write tool sets.
- **Runner (browser)**: executes user code in workers; the backend only stores problems and submissions.

### 4.2 Technology choices with alternatives and trade-offs

| Choice | Alternatives | Decision rationale and honest trade-off |
|---|---|---|
| Modular monolith | Microservices; serverless | Fewest moving parts. Trade-off: one deployable; mitigated by module boundaries |
| PostgreSQL + pgvector | SQLite plus sqlite-vec; a separate vector database; Elasticsearch | Postgres gives constraints, transactions, full-text and vectors together, and matches your skills. SQLite is simpler but weaker for concurrent worker and API access and for showing production habits |
| procrastinate (Postgres queue) | Celery plus Redis (familiar to you); arq plus Redis; custom `SKIP LOCKED` queue | Avoids Redis; transactional enqueue; periodic tasks. **Spike S3** confirms async and periodic support. Fallback: Celery plus Redis, a known quantity |
| SQLAlchemy 2 async + Alembic | SQLModel; raw SQL; Django ORM | Your stack. Trade-off: boilerplate; accepted |
| Next.js | Vite SPA; HTMX | Your stack and portfolio value; server components not required, so the app can stay mostly client components with a generated client |
| TanStack Query + Table | Redux; AG Grid | Server state belongs in a query cache; table needs are modest; AG Grid is heavy for this |
| FastEmbed (local ONNX) | Hosted embeddings API; sentence-transformers | No API cost, no data leaves your machine, runs on CPU. Trade-off: model quality below the best hosted models, fine for a few thousand chunks; model name and dimension are versioned so you can change |
| Postgres full-text + vectors, fused with RRF | Vector only; BM25 library | Hybrid beats vector-only on exact terms (names, tool names). Postgres full-text ranking is not true BM25; acceptable here |
| Pyodide, JS Worker, PGlite | Judge0; Piston; own Docker sandbox | No server code execution means no sandbox-escape class of bugs (Judge0 has had critical sandbox escapes disclosed and patched in 2024). Trade-off: results are client-side so grading is not tamper-proof, which does not matter for solo practice; some libraries unavailable in WASM |
| MCP SDK v2 (`mcp`), pinned | Hand-rolled protocol; v1 | The official SDK; v2 is the current stable line per its docs. Pin the major version; confirm the API in spike S5 |
| Provider interface for the LLM | Direct SDK calls everywhere | One of the few interfaces justified up front: tests need a fake, and the auth route may change |
| No LangChain or agent framework | LangChain, LlamaIndex | You are here to learn; typed Python loops are simpler to test and debug |

### 4.3 Process model and ports
`api` (8000), `worker` (no port), `web` (3100, since 3000 is often taken by other dev servers), `postgres` (5433 on the host, localhost only). MCP runs per client over stdio, or on 8765 over HTTP when enabled. Docker Compose runs only Postgres; the rest run natively with `uv` and `pnpm` for fast iteration (npm instead of pnpm, which is not installed; see ADR 0006).

---

## 5. Data model (PostgreSQL)

All user-owned tables carry `owner_id uuid not null`; timestamps are UTC (`timestamptz`); display in IST in the UI. Primary keys are UUIDv7 or bigint identity (decide in Phase 0; default `uuid` for API stability).

### 5.1 Tables

| Table | Key columns and constraints |
|---|---|
| `users` | id, email, password_hash (argon2), created_at |
| `companies` | id, owner_id, name, normalized_name, website, domain, country, registry_id, verification_status, verification_score, size_text, funding_text; **unique (owner_id, normalized_name)** |
| `company_checks` | company_id, check_key (one of 8), result (`yes`/`no`/`unknown`), evidence_url, quote, checked_at; unique (company_id, check_key) |
| `company_ratings` | company_id, source, rating, review_count, url, retrieved_at |
| `jobs` | id, owner_id, company_id, source, source_job_id, **fingerprint** (unique per owner), title, location_text, country, work_mode, job_type, hiring_from_india, currency, salary_min, salary_max, salary_period, salary_text, ctc_lpa_min, ctc_lpa_max, fx_rate_id, posted_at, first_seen_at, last_seen_at, expires_at, jd_text, jd_summary, jd_url, apply_url, careers_url, skills text[], seniority, visa_support, is_open |
| `job_scores` | job_id, scoring_version, jd_match, chance (`high`/`medium`/`low`/`long_shot`), fit_score, breakdown jsonb, reasoning, scored_at |
| `applications` | id, owner_id, job_id (unique), status, applied_at, next_followup_at, resume_version, portal_mode, site_mode, email_mode, notes, version (optimistic concurrency) |
| `application_events` | id, application_id, type, from_status, to_status, at, note (**append-only**) |
| `contacts` | id, company_id, name, role, email, phone, kind (`published_business`/`recruiter`/`referral`), source_url, created_at; **check: kind = published_business requires source_url** |
| `outreach_drafts` | id, application_id, contact_id, variant, subject, body, word_count, lint jsonb, state (`draft`/`approved`/`sent`/`rejected`), approved_at, sent_at, gmail_draft_id |
| `intel_items` | id, company_id (nullable), role_family, source_type (`company_specific`/`inferred`), similar_to_company_id, url, retrieved_at, source_date, rounds, process jsonb, topics text[], questions jsonb, difficulty, confidence, quote |
| `prep_topics` | id, area, title, priority, confidence (1 to 5), status, last_reviewed_at, next_review_at, notes |
| `prep_days` / `prep_day_progress` | day number, focus, core topics, practice, speaking, hours; progress per day with status |
| `study_sessions` | id, topic_id, minutes, kind, at, notes |
| `mock_sessions` | id, kind, transcript jsonb, scores jsonb, weak_topics text[], at, application_id (nullable) |
| `problems` | id, slug, title, difficulty, tags text[], statement_md, starters jsonb, tests jsonb, source (`original`/`external`), external_url, guide_ref |
| `submissions` | id, problem_id, language, code, result jsonb, passed, runtime_ms, at |
| `documents` / `chunks` | document: source_path, content_hash, kind, title, ingested_at. chunk: document_id, ordinal, heading_path, text, context_text, **embedding vector(384)**, tsv tsvector, embedding_model, embedding_version |
| `llm_calls` | id, purpose, provider, model, prompt_name, prompt_version, input_tokens, output_tokens, cost_usd, latency_ms, status, error, request_hash, created_at |
| `fx_rates` | base, quote, rate, as_of, source (**every converted salary stores the rate used**) |
| `domain_policies` | domain, mode (`allowed`/`manual_only`/`blocked`), rate_limit, notes, reviewed_at |
| `blacklist` | owner_id, company pattern, reason |
| `settings` | owner_id, key, value (salary floors per region, daily cost cap, defaults) |
| `audit_log` | id, actor (`ui`/`mcp`/`worker`), action, entity, entity_id, at, details |

### 5.2 Indexes and constraints that matter
`jobs(owner_id, fingerprint)` unique; `applications(owner_id, status, next_followup_at)`; GIN on `chunks.tsv` and `jobs` title and JD vectors if needed; **HNSW** on `chunks.embedding` (cosine); `application_events(application_id, at)`; check constraints for enums and the contact-source rule; foreign keys with sensible `ON DELETE`; partial index on open jobs.

### 5.3 Application state machine
Statuses (as in the workbook): New, Shortlisted, Applied - Pending, Follow-up Sent, Interview Confirmed, Technical Round, Next Round, HR Round, Manager Round, Offer Received, Offer Accepted, Rejected, No Response, On Hold, Withdrawn, Job Closed.
- Forward moves along the pipeline are allowed; jumping over rounds is allowed with a note (rounds vary by company).
- Terminal states (Offer Accepted, Rejected, Withdrawn, Job Closed) can be reopened only explicitly; the reopen is an event.
- Every change writes an event in the same transaction as the update. Optimistic concurrency via `version` and `If-Match` prevents two clients (UI and MCP) overwriting each other.

---

## 6. Module designs

Each module has `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, and `tasks.py` only if it has background work. Modules call each other only through public service functions.

### 6.1 Tracker (jobs, applications, contacts)
- Create-from-text: worker extracts fields with the LLM (structured output), then **code** normalises: salary parsing (ranges, K and M suffixes, periods hourly, monthly, yearly), currency, location, work mode, "hiring from India?" phrases ("worldwide", "US only", "must be authorised to work in…").
- Fingerprint = hash of normalised company, title, location and canonical apply URL. Re-adding the same job updates `last_seen_at` and returns the existing row.
- Salary conversion uses the latest `fx_rates` row; if none, the converted fields stay null and the UI says so. No silent defaults.
- Excel and CSV import (workbook v2 layout) is idempotent by fingerprint and by a stored row key.

### 6.2 Discovery (later phase)
- Adapter interface: `fetch(config) -> Iterable[RawJob]`. One file per source (Greenhouse, Lever, Ashby public boards; selected free APIs). Each adapter's header records the terms reviewed and the date.
- `domain_policies` decides allowed, manual-only or blocked. **LinkedIn, Indeed and Glassdoor are blocked for automated fetching**; for them the platform only accepts pasted URLs and text, and parses official alert emails (Gmail API, phase 6, optional).
- Scheduler runs adapters on a timetable; results flow through the same create-from-raw path as manual adds.

### 6.3 Company verification
1. Deterministic checks in code: site resolves, TLS valid, domain age through RDAP, MX records, careers page present and which applicant-tracking system it uses, registry lookups where an API exists (UK Companies House with a free key; others marked "manual").
2. A research agent reads evidence pages and fills the remaining checks; **each result needs a URL and a verbatim quote, and code verifies the quote appears in the fetched text** before accepting it.
3. A **rule** (not the model) computes the verdict from the 8 checks: 7 to 8 Verified, 5 to 6 Likely genuine, 3 to 4 Needs check, otherwise Suspicious; hard red flags (asks for money, chat-only hiring, no interview, free-mail recruiter) force Suspicious or Scam regardless of score.
4. Anything below Verified shows a prominent "needs your review" state. No check proves a company genuine; the UI says so.

### 6.4 Interview Intel
1. Research agent with templates per source type (company hiring pages, public interview write-ups); allowed sources only; review sites are read **by you** and pasted, never bulk-scraped (their terms restrict it).
2. Extraction into the fixed schema with URL, date, quote; reliability score (age, specificity, corroboration).
3. If fewer than two corroborating recent sources: **similar-company inference**. The model proposes peers from company type, size, stage, domain and stack; you confirm; rows are stored as `inferred` with `similar_to` set and shown with a distinct badge.
4. Topic tags map to `prep_topics`; frequency across rows raises a topic's priority for that application.
5. Output: a one-page **company brief** (process, rounds, topics, three likely questions, three questions to ask) that feeds mocks.

### 6.5 Scoring
- Deterministic parts: required-skills overlap against a normalised skill list from your knowledge base, seniority bands, salary against region floors, region and visa feasibility.
- LLM part: qualitative reading of the JD (what the team builds, red flags), with reasoning stored.
- Weights from the workbook (skills 30, seniority 15, pay 20, company 15, location and visa 10, growth 10) live in settings and are versioned (`scoring_version`) so scores can be recomputed and compared.
- "Chance" is an **estimate**, shown with its factors; after about 50 outcomes a calibration view compares predicted chance to actual results.

### 6.6 Outreach
- Draft generator uses the style guide, verified company facts and two proof points from the knowledge base; produces two variants.
- **The linter is ported as a service module** (`outreach/lint.py`) with tests; the same rules as `outreach_lint.py`; lint result stored with the draft.
- State machine: draft, approved, sent, rejected. Only `approved` can create a Gmail draft (optional integration). There is no send action in the platform.
- Guards: one email per company per role; daily cap (default 10); follow-up schedule with a plain opt-out line; contacts must have a published source.

### 6.7 Prep
- Seeds: `content/curriculum.yaml` (areas, topics, 45-day days) generates `prep_topics` and `prep_days`; the markdown guides are served by a reader with anchored sections.
- Study sessions update confidence and `next_review_at` with a simple spaced-interval rule (1, 3, 7, 14, 30 days) based on the confidence you set.
- **Mock interviews**: a session type (coding, system design, backend deep dive, behavioural, project defense) with a system prompt per type from the prompt registry; one question at a time; scoring rubric (correctness, depth, structure, honesty about limits, time); transcript and weak topics stored; weak topics lower the related confidence suggestions (you confirm).
- Project-defense mode reads the evidence-tagged guide and holds you to it.

### 6.8 Practice and the online compiler
- **Problem format** (`content/problems/<slug>.yaml`): title, difficulty, tags, statement (Markdown), starter code per language, test cases (input and expected output as JSON), hidden test flag, optional `guide_ref`, optional `external_url`. External problems (for example LeetCode) store **title and link only**; statements of third-party sites are not copied.
- **Original problems**: we write about 40 original problems with tests, matching the DSA, Python, JavaScript, SQL and design exercises in your guides.
- **Runner design**
  - *Python*: Pyodide in a dedicated Web Worker, assets self-hosted under `/public` so the page can run a strict CSP with no external network; harness imports the user function, runs each test with a per-test time limit, captures stdout, returns structured results; the worker is **terminated and recreated** on timeout, so infinite loops cannot hang the tab.
  - *JavaScript and TypeScript*: Web Worker; TypeScript transpiled in the browser before running; same harness and limits.
  - *SQL*: PGlite (Postgres in WebAssembly) with a fixture schema and data per problem; compare result sets with explicit rules for column order and row order; show `EXPLAIN` on request.
  - Limits: output size cap, memory warnings, no network from workers, state reset between runs.
- **"Click a question, land in the editor"**: any Markdown question item or intel question can carry `practice:<slug>`; the renderer turns it into a button to `/practice/<slug>`. Topics and mock results also link to problems by tag.
- Submissions are stored (code, result, runtime) for history and weak-topic signals.
- Later, optional: a **server runner adapter** (for Java, C++, Go) using a hardened sandbox, with the container network-isolated and secret-free, only after a security review (see section 9).

### 6.9 Knowledge (RAG)
Pipeline stages, each testable on its own:
1. **Ingest**: documents from `content/` (guides, knowledge base, claim audit), intel items and your notes; content hash per file; re-ingest only on change.
2. **Chunk**: split by Markdown heading path first, then by size (target 300 to 500 tokens, small overlap only where a section is long); each chunk keeps `heading_path` for citation.
3. **Context**: optional short "where this chunk sits" prefix generated by a cheap model with prompt caching (contextual retrieval idea); behind a flag until the eval proves it helps.
4. **Embed**: FastEmbed bge-small (384-d); `embedding_model` and `embedding_version` stored; changing the model creates a new version, never mixes dimensions.
5. **Retrieve**: vector search (HNSW, cosine) plus Postgres full-text; fuse with reciprocal rank fusion; take the top 20; optional cross-encoder rerank to 5 (phase 5+, only if the eval shows a gain).
6. **Answer**: the model gets only retrieved chunks and must cite chunk ids; if the best evidence is weak, it says "I do not know". Citations render as links to the source section.
7. **Evaluate**: a golden set of 30 to 50 questions about your own guides with expected source chunks; metrics recall@k and MRR for retrieval; an LLM judge plus spot checks for faithfulness; **the eval runs on every retrieval change**, results stored.
Edge cases: empty corpus, near-duplicate chunks, stale chunks after file edits, model change, very long sections, tables and code blocks (kept intact), queries with exact identifiers (full-text covers them).

### 6.10 MCP server
Built with the official SDK (v2 line, version pinned). **Tools** (name: purpose, access):
- Read: `search_jobs`, `get_job`, `list_due_followups`, `get_company_brief`, `search_knowledge`, `get_prep_plan_today`, `list_problems`.
- Write (guarded: schema requires `confirm: true`, every call audited): `add_job_from_text`, `update_application_status`, `log_study_session`, `add_note`.
- **Not exposed**: sending email, deleting data, changing settings, anything touching secrets.
**Resources**: `careerpilot://job/{id}`, `careerpilot://prep/day/{n}`, `careerpilot://company/{id}/brief`. **Prompts**: `mock-interview`, `company-brief`, `daily-review`.
Transports: stdio for Claude Desktop and Claude Code; Streamable HTTP optional, bound to localhost with a bearer token and Origin and Host checks. Tool descriptions are written as untrusted inputs to the model; arguments are validated by the same service schemas as the API. Because MCP clients can be steered by injected text, write tools cannot reach outward (no email, no network).
This server is also the learning artefact for "how MCP is built": the docs folder gets a short walkthrough with a diagram of host, client, server, transport and message flow.

### 6.11 LLM layer, prompts and evals
- Interface: `complete`, `structured(schema)`, `stream`; providers: `AnthropicProvider` (default), `ClaudeCliProvider` (optional), `FakeProvider` (tests).
- **Structured output** by forced tool use with a Pydantic schema; one automatic repair attempt; then fail and record.
- **Budget guard**: sums `llm_calls.cost_usd` for the day; blocks non-interactive jobs over the cap and asks before interactive ones.
- **Prompt registry**: `prompts/<name>/vN.md` with front matter (model, temperature, schema), loaded by name and version; changing a prompt creates a new version; **golden tests** with recorded fixtures catch regressions without calling the API in CI.
- **Model tiering** (names and prices from the pricing page I read; no date shown, confirm before relying): Haiku 5.5 for extraction and classification, Sonnet 5.5 for verification reasoning, drafting and mock interviews, Opus 5.5 or Fable 5.1 only on explicit request.
- **Prompt caching** for the large static parts (style guide, knowledge base excerpts); **batch** for non-interactive work (50 percent saving per the pricing page).
- Research agents: step limit (8), page limit (6), token cap, tools `search`, `fetch`, `submit` only, read-only.

### 6.12 Jobs and scheduling
Task kinds: `discover`, `verify_company`, `collect_intel`, `score_job`, `embed_document`, `daily_digest`. Each task is **idempotent** (keyed by entity and version), retried with exponential backoff and jitter up to a limit, then marked failed with the reason; failures are visible in a Tasks screen with a manual retry. A watchdog marks tasks stuck beyond a limit.

---

## 7. API design

- REST under `/api/v1`, OpenAPI is the contract; **TypeScript client generated from it** (no hand-written types).
- Conventions: plural nouns, cursor pagination (keyset), filter parameters validated, consistent `application/problem+json` errors, `If-Match` and `version` for updates that can race, `Idempotency-Key` on creates that imports and MCP may retry, SSE for task progress and mock-interview streaming.
- Resources: `/jobs`, `/applications`, `/companies`, `/contacts`, `/outreach-drafts`, `/intel`, `/prep/topics`, `/prep/days`, `/study-sessions`, `/mocks`, `/problems`, `/submissions`, `/knowledge/search`, `/knowledge/ask`, `/tasks`, `/settings`, `/imports`, `/exports`, `/healthz`.
- Authentication: session cookie (HttpOnly, SameSite=Lax) plus a custom `X-CSRF-Token` header on mutating requests; Host header allow-list; strict CORS (the web origin only).

---

## 8. Frontend design

Routes: `/` Today and dashboard, `/jobs` (table and Kanban), `/jobs/[id]` (Overview, JD, Company check, Intel, Contacts, Outreach, Timeline), `/companies`, `/intel`, `/prep` (Today, Roadmap, Topics, Guides, Mocks, Stories), `/practice` and `/practice/[slug]`, `/ask`, `/outreach` (approval queue), `/analytics`, `/tasks`, `/settings`.
- Layout: left navigation, global quick-add (paste URL or text), command palette.
- Tables: virtualised, saved filters, status colours matching the workbook, keyboard navigation.
- Editor: Monaco with language switch, test panel, run and reset, timer, submissions drawer, "open in guide" link back.
- Accessibility: semantic markup, focus management in dialogs and drag and drop (keyboard alternative to dragging), contrast checks.
- State: TanStack Query for server state; local state for UI; forms with Zod schemas shared with the generated client where possible.
- Rendering untrusted text (JDs, intel, guides): Markdown rendered through a sanitiser with raw HTML disabled; CSP set by the server.

---

## 9. Security and threat model

| Threat | Impact | Controls |
|---|---|---|
| Another website calls your localhost API (CSRF, DNS rebinding) | Reads or edits your data | Bind to 127.0.0.1; Host header allow-list; session cookie `SameSite=Lax`; custom CSRF header (forces a preflight); strict CORS; no wildcard origins |
| XSS from stored job text, intel or guides | Session theft, data exfiltration | Escape by default, sanitised Markdown without raw HTML, CSP, HttpOnly cookies |
| **Prompt injection** from fetched pages or JDs ("ignore your instructions and…") | Corrupted data, leaked context, harmful tool use | Fetched text is data, never instructions; research agents are read-only with only search and fetch tools; structured outputs; **quote verification** against fetched text; no secrets in prompts; write actions require your approval; MCP write tools cannot reach outward |
| **SSRF** through the fetcher | Access to local or cloud-internal endpoints | Allow only http and https; resolve DNS and block private, loopback, link-local and metadata ranges **on every redirect hop**; domain policy registry; size and time caps; no credentials forwarded |
| Terms-of-service violations | Account bans, legal exposure | Policy registry blocks LinkedIn, Indeed and Glassdoor automation; rate limits; documented terms review per adapter |
| Privacy and contact-data misuse | Legal and reputational risk | Contacts need a published source; no personal mobile numbers; export and delete; no bulk mail; daily cap |
| Secret leakage (API keys, tokens) | Cost and account abuse | `.env` not committed; `pydantic-settings`; optional OS keychain; log redaction filter; secret scanning in CI (gitleaks) |
| Code runner abuse | Hung tab, data exposure | Browser-only workers, no network (CSP `connect-src 'self'`), terminate on timeout, output caps; server runner deferred |
| Supply chain | Malicious dependency | Lockfiles, `pip-audit` and `npm audit` in CI, minimal dependencies, pin the MCP SDK major, review new packages |
| LLM data sharing | Sensitive data sent to a third party | Send only what a task needs; never send passwords, IDs or API keys; check Anthropic's data-retention terms for your plan (not verified here); local embeddings keep the corpus off the network |
| Data loss | Lost tracker | Nightly `pg_dump` to an encrypted file, tested restore, export to CSV and xlsx |
| Local disk compromise | Everything readable | Disk encryption (BitLocker), OS account protection; the app does not pretend to protect against a compromised machine |

Authentication details: argon2 password hash, rate-limited login, session expiry, secure random session ids, logout invalidates server-side. If it is ever exposed beyond localhost: TLS, OIDC, and a security review first.

---

## 10. Edge cases catalogue (each becomes a test or a documented decision)

**Jobs and parsing**: duplicate postings across sources and reposts; expired or closed postings; salary ranges, hourly or monthly figures, "competitive", multiple currencies, equity-heavy offers; multi-city locations; "remote" with country limits; company name variants (Pvt Ltd, Inc, trading names); very long or malformed JD text; non-English JDs; HTML and hidden text in pasted content.
**Applications**: invalid transitions; back-dated events; applying twice; withdrawing after an offer; two clients editing the same row (version conflict); time-zone display of follow-ups.
**Outreach**: second email to the same company and role; daily cap reached; follow-up after a reply; bounced address; unsubscribed contact; draft edited after approval (re-lint and re-approve).
**LLM**: timeout, rate limit, outage (fallback or queue), malformed JSON (repair once), cost cap reached, non-determinism (store outputs and prompt versions; reproduce from recorded fixtures), context too large (truncate with a marker, never silently).
**Research and fetch**: robots and policy blocks, paywalls, JavaScript-only pages (marked "needs browser"), redirects to private IPs, huge pages, encoding problems, conflicting sources (kept side by side with confidence), quotes that do not verify (field rejected), review-site pages that block access (manual paste path).
**RAG**: empty corpus, duplicates, stale chunks, changed embedding model, exact-identifier queries, long tables and code, questions the corpus cannot answer.
**Runner**: infinite loops, memory growth, output floods, forbidden imports, state leaking between runs, first-load latency (cache and show progress), offline use.
**Data**: UTC storage and IST display; FX rate missing or stale (shown, not hidden); migration failure (transactional, tested on a copy); restore from backup into a fresh database.
**UX**: very large tables, optimistic updates that fail (rollback with message), drag and drop on touch and keyboard, empty states, long text overflow.
**MCP**: duplicate tool calls (idempotency keys), partial failures, stale `version`, tool output size limits.

---

## 11. Testing and quality gates

| Layer | What |
|---|---|
| Unit | Services (state machine, scoring, verdict rule, salary parser with property-based tests, lint rules, chunker, RRF) |
| Integration | API and repositories against **real Postgres with pgvector** in a container (no database mocks); migrations up and down on a copy |
| LLM and agents | Fake provider; recorded fixtures for golden prompts; quote-verification tests with adversarial pages; budget guard tests |
| RAG evals | Golden questions, recall@k and MRR, faithfulness spot checks; results stored; a drop fails the gate |
| Security tests | SSRF suite (private IPs, redirects, DNS rebinding), CSRF and Host tests, XSS payloads in JD and Markdown, secret redaction |
| Frontend | Vitest and Testing Library for components; Playwright smoke for add job, move status, run a problem in each language, ask a question |
| Runner | Playwright tests for timeouts, infinite loops, output caps, SQL fixtures |
| Contract | OpenAPI is generated; the client is regenerated in CI and diffed (a mismatch fails the build) |

**Quality gates in CI (GitHub Actions on a personal repository; not your employer's GitLab):** `ruff` (lint and format), `pyright` or `mypy` strict, `pytest` with Postgres service, web typecheck, lint, tests and build, Playwright smoke, `pip-audit`, `npm audit`, gitleaks, an import-boundary check for modules, and a "no duplicate content" check (a script that fails if the same markdown or problem file appears twice).
**Definition of done** for every change: tests added, migrations included, docs and ADR updated if a decision changed, no new unexplained dependency, deletion pass done.

---

## 12. Observability, operations and cost

- **Logs**: `structlog` JSON with request id and task id; secrets redacted; one log per LLM call with the audit row id.
- **Health**: `/healthz` (process), `/readyz` (database, migrations current, embedding model loaded).
- **Tasks screen** lists queued, running, failed and retried work with reasons and a retry button.
- **LLM dashboard** from `llm_calls`: cost by day and purpose, tokens, latency, failures, prompt versions.
- **Backups**: `scripts/backup` runs `pg_dump`, encrypts with a key you hold, keeps 14 daily copies; `scripts/restore` is tested in CI against a fresh database.
- **Config**: environment variables with validation at start-up; the app refuses to start with missing or malformed settings.

### Cost estimate (assumptions stated; replace with measurements in Phase 4)
Prices per million tokens from the pricing page I read (no date shown): Haiku 5.5 input 0.10 and output 0.50 USD; Sonnet 5.5 input 2 and output 10 USD. Web search tool pricing was not retrievable and is **not included**.

| Task per day | Assumption | Approx cost |
|---|---|---|
| Extract and score 40 jobs (Haiku) | 12k input, 1.5k output each | 40 x (0.0012 + 0.00075) = 0.08 USD |
| Verify and research 10 companies (Sonnet) | 40k input, 3k output each | 10 x (0.08 + 0.03) = 1.10 USD |
| Draft 10 emails, 2 variants (Sonnet) | 8k input, 1.2k output each | 10 x (0.016 + 0.012) = 0.28 USD |
| One mock interview of about 20 turns (Sonnet) | about 120k input with caching, 8k output | about 0.2 USD |
| **Total, worst case without batch or caching** | | **about 1.7 USD per day, roughly 50 USD per month** |

Batch (50 percent saving) and prompt caching reduce this materially; the daily cap (default 2 USD) bounds it. Plan type matters: the support article I read says Max, Ultra and Team plans include monthly API credits that can cover usage with a Console key (Pro is not named); check yours.

---

## 13. Scaling and extension path

| Pressure | What changes | What does not |
|---|---|---|
| More data (100k jobs, 1M chunks) | Partial and covering indexes, partition `jobs` by `first_seen_at`, tune HNSW parameters; move vectors to a dedicated store only if needed | Schema shape, services, API |
| More workers | Run several worker processes (the queue already uses row locking); split queues by task kind | Task code (idempotent) |
| More users | Add OIDC and real accounts; `owner_id` is already enforced; per-user budgets and settings | Repository layer |
| Hosted deployment | API and worker on ECS, RDS Postgres with pgvector, S3 for backups, secrets in Secrets Manager; the same Docker image for API and worker | Application code |
| More sources | New adapter files plus a policy row | Core |
| More languages in the runner | Server runner adapter behind the same interface | Frontend and problem format |
| Other LLM providers | New provider class | Services and prompts |
| Extra features | New module folder with the same layout | Existing modules |

---

## 14. Delivery plan

Time-box: building takes at most **2 hours a day** in the first three weeks; interview preparation (about 4 to 5 hours) and applying (20 to 30 minutes) come first. Hours below are estimates for focused work including review; I do the heavy coding, you review and run it.

| Phase | Days | Scope | Acceptance criteria | Est. hours |
|---|---|---|---|---|
| **0 Foundation** | 1 | Repository, `uv` and `pnpm` setup, Docker Postgres with pgvector, Alembic baseline, config, structured logging, auth with CSRF and Host checks, CI skeleton, ADRs 1 to 6, module-boundary check | `make dev` starts everything; login works; CI green; migration up and down passes | 5 to 6 |
| **1 Tracker + Prep (first usable)** | 2 to 5 | Jobs and applications with the state machine and history, table and Kanban, job detail, contacts, workbook import, prep roadmap and topics seeded from `content/`, guide reader, study sessions, dashboard | Import the v2 workbook round trip; move a job through all statuses with history; Today screen shows the roadmap day and due follow-ups; tests for state machine and import idempotency | 14 to 18 |
| **2 Practice runner** | 6 to 9 | Problem format, 25 original problems, Monaco editor, Python (Pyodide), JavaScript and TypeScript workers, SQL (PGlite), submissions, deep links from guides and topics | Every language runs tests; infinite loop is stopped within the limit; CSP blocks network; clicking a guide question opens the right problem | 12 to 15 |
| **3 Knowledge (RAG) + MCP** | 10 to 14 | Ingest, chunk, embed, hybrid retrieval, answers with citations, golden eval set; MCP server with read tools and guarded write tools; learning notes | Eval recall@5 at or above the target set after the first run (target decided from the baseline); `Ask` cites sources; Claude Desktop or Code lists due follow-ups through MCP | 12 to 15 |
| **4 Research agents + scoring + outreach** | 15 to 21 | Fetcher with policy and SSRF guard, verification, intel and similar-company fallback, scoring service, outreach drafts with lint and approval, LLM audit and budget guard, mock interviews | SSRF suite passes; quote verification rejects a fabricated quote in tests; verdict follows the rule; no send action exists; daily cap blocks a runaway job | 14 to 18 |
| **5 Discovery + scheduler** | 22 to 28 | Greenhouse, Lever and Ashby adapters, policy registry, daily digest, task screen, optional Gmail alert parser | Re-running discovery creates no duplicates; blocked domains are refused; failures visible and retryable | 8 to 10 |
| **6 Hardening and extras** | 29 onward | Backups and restore test, analytics and calibration view, offer calculator, referral CRM, STAR stories, optional Sheets sync, optional server-runner adapter after a security review, docs | Restore test green; documentation complete; deletion pass finished | as time allows |

**Technical spikes before committing (each about 1 to 2 hours, done at the start of the phase that needs it):**
- S1 Pyodide in a Web Worker with strict CSP and self-hosted assets.
- S2 PGlite with fixtures and result-set comparison.
- S3 procrastinate with async code and periodic tasks (else Celery plus Redis).
- S4 pgvector HNSW with FastEmbed 384-d; measure recall and latency on the guides.
- S5 MCP v2 server over stdio, connected to Claude Desktop and Claude Code; confirm the current SDK API (the docs I read show `MCPServer` and decorators).
- S6 Anthropic web search tool availability and pricing versus a self-hosted search provider.
- S7 Fetcher SSRF test harness.

Each spike ends with a short ADR: what we chose and what we measured.

---

## 15. LLM access and the API token question (answer for your local-only case)

Verified from Anthropic's pages in this session:
- **Subscription login (OAuth)** is "intended exclusively" for subscription holders and "designed to support ordinary use of Claude Code and other native Anthropic applications"; advertised limits "assume ordinary, individual usage of Claude Code and the Agent SDK".
- **Developers building products or services** that use Claude, including via the Agent SDK, should use **API key** authentication through the Claude Console. Third parties may not offer Claude.ai login or route requests through plan credentials for their users, and may not collect or store Claude.ai credentials or session tokens.
- A support article (updated October 2026) says that when you are signed in with your plan, **`claude -p` and the Agent SDK still draw from your subscription limits**; Max, Ultra and Team plans also include monthly **API credits** usable with an API key from a linked Console organisation. It does not say whether personal local use differs from building products, and it does not name Pro for the credits.

What this means for you:
1. **There is no "API token" you take from your subscription.** The supported ways are: an API key from the Console (separate billing; credits may offset it on some plans), or running Claude Code or `claude -p` signed in with your own plan.
2. **Recommended default: a Console API key**, because it is the documented route for software you build, it gives full control (structured output, tool use, caching, batching, token counts) and the cost at your volume is small (section 12). Put it in `.env`, never in the repository.
3. **Optional provider `ClaudeCliProvider`**: shells out to your locally installed `claude -p`, signed in with your own plan, for personal use only. It is a reasonable fit for the documented individual-use model, but the pages I read do not explicitly bless wrapping it in your own application, and it is technically weaker (process per call, less control, plan rate limits). Off by default; use it only if you accept that ambiguity, and ask Anthropic if you want certainty.
4. **Do not** extract OAuth tokens and call the API directly with them, and do not store Claude.ai credentials or session tokens in the app.
5. Embeddings need no token: FastEmbed runs locally.
6. I could not verify what plan you are on; check your plan's credit allowance in the Console.

---

## 16. Repository layout and conventions

```
careerpilot/
  plan.md  README.md  Makefile  docker-compose.yml  .env.example
  apps/
    api/                      # one Python package, three entrypoints
      pyproject.toml  alembic/
      src/careerpilot/
        core/                 # config, logging, security, db, errors, llm/, fetch/
        modules/              # tracker, companies, intel, scoring, outreach, prep,
        |                     # practice, knowledge, discovery  (each: models, schemas,
        |                     # repository, service, router, tasks?)
        main.py  worker.py  mcp_server.py
      tests/
    web/                      # Next.js app
      src/app/  src/features/<module>/  src/lib/api/ (generated)  src/runner/
  content/                    # the ONLY copy: guides/, curriculum.yaml, problems/, knowledge/
  prompts/                    # versioned prompt files
  scripts/                    # import_workbook, seed, backup, restore
  docs/adr/                   # decision records, one short file each
```

Conventions: modules import only `core` and other modules' public service functions (enforced); no business logic in routers or React components; database access only in repositories; one place for each concept; names follow the workbook vocabulary (Status, Mode 1/2/3, Priority) so your existing habits carry over; commits small with the reason in the message; ADR for every decision that has a real alternative.

### Reuse of what already exists (then delete the originals)
| Asset | Becomes |
|---|---|
| `interview-prep/*.md` (14 guides) | `content/guides/` and the RAG corpus |
| `tracker-build/curriculum.py` | `content/curriculum.yaml` (areas, 159 topics, 45 days) |
| `elphi-knowledge-base.md`, `resume-claims-audit.md` | `content/knowledge/` (RAG, and the truthfulness source for drafts) |
| `outreach_lint.py` and samples | `outreach/lint.py` plus its tests |
| `Job_Hunt_Tracker.xlsx` | Import format; the first data seed |
| Skills `ats-resume`, `job-outreach-writer`, `interview-prep-coach` | Stay as Claude skills; they will call the platform through MCP once it exists |

---

## 17. Skills and references to add

Skills for building (to be reviewed before enabling; downloaded files are untrusted until read):
- From the `anthropics/skills` repository: **mcp-builder**, **webapp-testing** (Playwright), **frontend-design** (listed by third-party aggregators; confirm in the repository itself, and read each skill's files before use). Install into the project's `.claude/skills/` only after review.
- Project skills we write: **careerpilot-dev** (conventions, ADR habit, the anti-over-engineering rules, how to run quality gates).

Primary references to read (and cite in ADRs): the MCP specification and Python SDK documentation; pgvector README; FastAPI, SQLAlchemy 2 and Alembic docs; OWASP ASVS and OWASP LLM Top 10; Anthropic's authentication and pricing pages (above); Postgres full-text search documentation.

---

## 18. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Building the platform eats prep time | High | High | Phase slicing; 2-hour cap; platform useful by day 3; prep first every day |
| Scope creep ("more features") | High | Medium | MoSCoW list; every addition needs a real case and a deletion elsewhere |
| A spike fails (Pyodide, PGlite, procrastinate, MCP v2 API) | Medium | Low to medium | Spikes first; named fallbacks (Celery plus Redis; Monaco plus JS-only; server runner later) |
| LLM output wrong or fabricated | High | High | Quote verification, rules for verdicts, human approval, evals, uncertainty shown |
| Review and portal terms change | Medium | Medium | Policy registry with review dates; manual paste path always works |
| API cost surprises | Low | Low | Daily cap, audit table, batch and caching |
| Security slip on localhost | Medium | Medium | Threat model controls tested; no outward-facing write tools |
| Over-engineering despite the rules | Medium | Medium | PR checklist; deletion pass per phase; ask "which real case needs this?" |
| Data loss | Low | High | Backups with a tested restore |

---

## 19. What I verified and what I did not

**Verified in this session from primary or fetched pages:** Anthropic's legal and authentication rules for subscription login versus API keys; the Agent SDK support article (plan-limit behaviour and monthly API credits); the API price table (models and per-million-token figures; no date visible on the page); the MCP Python SDK v2 quick-start shape (`MCPServer`, decorators, install command, transports listed).
**From secondary sources, treat as directional:** Judge0's 2024 sandbox-escape CVEs and the 1.13.1 fix; RAG best practices (hybrid search, fusion, reranking, evals); FastEmbed's 384-d default and multilingual options; the existence and contents of the `anthropics/skills` repository.
**Not verified (to be settled by spikes):** Pyodide and PGlite behaviour under strict CSP; procrastinate async and periodic support; pgvector HNSW settings and recall on your corpus; whether Anthropic's web search tool fits, and its price; MCP v2 behaviour with Claude Desktop and Claude Code; Anthropic's data-retention terms for your plan.
**Not possible to promise:** "100 percent perfection". The plan substitutes measurable gates: tests, evals, a threat model with tests, tested backups, and a deletion pass each phase.

---

## 20. Decisions needed from you

1. **Approve this plan** (or list changes), including the scope cuts in section 1.
2. **Project folder**: where should the repository live (for example `D:\Projects\careerpilot`)? I will create it with `git init` on a branch.
3. **LLM route**: Console API key (recommended) or also the optional local `claude -p` provider. Tell me your plan type if you know it.
4. **Name**: CareerPilot is a working name; change it now, it is cheap now and annoying later.
5. **Daily building time** (default 2 hours maximum) so I pace the phases.
6. **Hosting later?** Stay local, or plan an AWS deployment as a portfolio step after you join a company.
7. **Skills**: OK to fetch `mcp-builder`, `webapp-testing` and `frontend-design` from the Anthropic skills repository into an isolated folder for review?
