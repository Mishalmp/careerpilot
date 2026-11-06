# 09: Product specification (the foundation, A to Z)

This is the single description of what the product is, its objects, each feature's inputs, outputs, rules and edge cases, and its targets. Build and test against it. Existing behaviour is documented from the code as of commit `dbdf4e8`; new behaviour is marked **NEW**.

## 1. Product
**Purpose**: one place where a job seeker tracks applications, checks whether a company is genuine, prepares for the interviews that specific jobs need, practises, is examined, and sees how it is going, with AI used only where it helps and always checked.
**Primary user (now)**: one intermediate backend/full-stack engineer on a Windows laptop. **Future users**: friends or other job seekers (multi-user is a design constraint).
**Jobs to be done**: (1) keep every application and its history in order; (2) avoid scams and wasted effort; (3) know what to study for this job; (4) practise realistic questions and retain them; (5) prove readiness with exams; (6) understand the system well enough to explain it in an interview.
**Principles**: truthful (every AI claim traceable), human approves anything that leaves the machine or enters the knowledge base, deterministic rules decide verdicts, failures are visible and recoverable, simple before clever.

## 2. Domain objects
Existing (tables): `users`, `sessions`; `companies`, `jobs`, `applications`, `application_events`, `contacts`; `prep_topics`, `prep_days`, `prep_plan`, `study_sessions`; `submissions` (practice); `documents`, `chunks` (notes index); `llm_calls`, `audit_events`; `company_checks`; `job_scores`; `outreach_drafts`; `intel_sources`, `intel_items`; `mock_sessions`; `discovery_sources`, `discovered_jobs`; `tasks`; `digests`; `fx_rates`; `star_stories`.
**NEW** (spec in `03`): `tracks`, `topics` (replaces `prep_topics`), `topic_edges`, `questions`, `question_options`, `question_sources`, `attempts`, `review_cards`, `checkpoints`, `checkpoint_items`, `checkpoint_attempts`, `research_runs`, `research_findings`, `user_settings`/`profile`, `task_events`, `worker_heartbeats`.
Relationships in words: a **user** owns everything. A **company** has **jobs**; a job has one **application** with **events**. A **track** has **topics**; a topic has **questions**; a question has **options** (MCQ) and **sources**; an answer is an **attempt**; each question has one **review card** (schedule). A **checkpoint** snapshots questions into **items**. A **research run** produces **findings** that, once approved, become topics and questions. A **task** is any background work with progress **events**.
Key invariants: every row has `owner_id`; every query filters by it; unique natural keys per owner (company name, job fingerprint, task key); statuses are enums checked by the database; money has currency and a dated rate; AI output is stored with the prompt version that produced it.

## 3. Features: purpose, inputs, outputs, rules, edge cases
Format: **In** inputs, **Out** outputs, **Rules**, **Edge** edge cases. Acceptance = the test cases in `10` and the "done when" of tasks.

### 3.1 Sign-in and settings
In: email, password; settings changes. Out: session cookie (HttpOnly, SameSite=Lax) + CSRF token; settings page. Rules: password >= 12 characters; throttle failures; secrets (API key, backup key) are never shown after saving, only "set / not set". Edge: expired session during a form; two devices; password change revokes others; wrong clock.

### 3.2 Job tracker
In: job fields, pasted description/URL (**NEW** quick add), status changes with note and expected version, contacts. Out: jobs table and board, detail with timeline, CSV export. Rules: fingerprint dedupe; forward-only stages; note needed to skip a stage; terminal states reopen only with a reason; optimistic concurrency. Edge: duplicate with different tracking params; two tabs; huge description; deleting with undo (**NEW**).

### 3.3 Discovery and digest
In: board provider and name, title keywords. Out: inbox of listings, accepted into the tracker on demand, daily digest. Rules: only Greenhouse, Lever, Ashby public boards; fetcher guard; re-read adds nothing twice; decisions persist. Edge: board 404, invalid JSON, 8 MB limit, NUL characters, very long links, listing removed from the board.

### 3.4 Company check
In: job (company website, description). Out: 8 checks + 4 red flags, verdict by rule, evidence with verified quotes. Rules: model supplies evidence only; quote must be on the cited page and fit the check; manual findings win; flags cleared only by the owner. Edge: no website; site blocks fetch; domain registry silent; scam warnings in the description.

### 3.5 Fit score
In: job + profile (skills, years, regions, pay, levels). Out: score 0-100, coverage, chance label (rule of thumb), blockers, breakdown. Rules: weights versioned; unknown parts excluded and coverage shown; model reading limited to growth and warnings with verified quotes. Edge: no skills in the description; profile missing; profile changed (stale flag).

### 3.6 Outreach (no send)
In: job, contact (published source or referral), facts, constraint; or hand-written draft. Out: drafts with lint, states draft/approved/sent/rejected. Rules: nothing is ever sent by the app; approval guards (flags read, recipient source, company not suspicious, one per role, daily cap 10). Edge: second message per role; suspicious company; facts not in the description or page.

### 3.7 Interview intel
In: pasted text or fetched page, company. Out: rounds, topics, questions, tips with quotes and reliability; brief. Rules: quotes verified; other-company items marked inferred. **NEW**: becomes a source feeding the research inbox and question bank. Edge: review-site text (paste only), contradictions, old dates.

### 3.8 Learning platform (**NEW**, full spec `03`)
Topics, roadmap, questions of five types, quizzes, spaced repetition, checkpoint exams, research inbox, mastery. In: owner's study actions, research results (approved). Out: due reviews, exam reports, mastery. Rules: nothing predefined; every AI-made item grounded and approved; scheduling by FSRS. Edge: see `10` section 6.3-6.5.

### 3.9 Practice (in-browser runner)
In: code in Python/JS/TS/SQL. Out: per-test results, submissions history. Rules: learner code runs only in browser workers under CSP; limits on time and output; hidden tests are not secret. **NEW**: problems can be created from questions and are validated in the runner before saving. Edge: infinite loop, network attempt, giant output, SQL fixture reset.

### 3.10 Ask my notes (RAG)
In: question. Out: cited answer or the best passages, or "not in your notes". Rules: hybrid search + rank fusion; similarity gate; answer must cite valid passages; uncited answers withheld. Edge: empty corpus; private notes sent to the model only with a key and consent (D6); model changed.

### 3.11 Mock interviews
In: job or topic, question count, answers. Out: scored turns, summary with weak topics (by code). Rules: model scores are opinions; answer treated as data; one answer per turn. **NEW**: weak topics create review boosts; questions can be drawn from the question bank.

### 3.12 Insights, offers, stories
In: history, offers, stories. Out: funnel, pace, prep, calibration (waits for 50 outcomes); offer comparison in rupees with dated rates; STAR story bank with hints. Rules: no forecasts presented as facts; rates typed with dates; pre-tax only.

### 3.13 Architecture explorer (**NEW**, `04`)
In: none (read-only), plus try-it inputs. Out: diagrams, flows, concepts, live status, ERD, ADRs. Rules: content from `content/architecture/`; drift tests keep it equal to the code.

### 3.14 System, tasks, backups
In: task retry, backup now. Out: tasks screen, system status, encrypted backups, restore CLI. Rules: idempotent task keys; backoff; watchdog; restore into a new database only; key held by the owner. Edge: worker down, disk full, wrong key, tool version mismatch.

## 4. Navigation map (routes)
`/login` · `/` Today · `/jobs`, `/jobs/[id]` (tabs) · `/discover` · `/learn` (home, roadmap, topics/[id], quiz, review, checkpoints, inbox, bank) · `/practice`, `/practice/[slug]` · `/ask` · `/mock`, `/mock/[id]` · `/insights` · `/offers` · `/stories` · `/architecture` (+ concepts, flows, data, status, drills, decisions) · `/tasks` · `/settings` · `/dev/ui` (development only).
Sidebar groups: Workspace (Today, Jobs, Discover) · Prepare (Learn, Practice, Mock, Ask, Stories) · Analyse (Insights, Offers) · System (Architecture, Tasks, Settings).

## 5. API conventions
REST under `/api/v1`, OpenAPI is the contract and the TypeScript client is generated. Errors are `application/problem+json` with a stable `code`. Lists use keyset pagination with a hard maximum. Creates used by retries accept `Idempotency-Key` (NEW). Long operations return `202` with a task id; progress via SSE with polling fallback (NEW). Every write is audited (NEW). Every route requires a session and, if unsafe, a CSRF header.

## 6. Non-functional targets (confirm by measurement; thresholds are starting points)
| Area | Target |
|---|---|
| Latency (laptop, 50k jobs) | list/detail p95 < 200 ms; search p95 < 400 ms; no request > 2 s (longer work is a task) |
| Page load | first render < 1.5 s warm; interaction < 100 ms feedback |
| Availability | local app: recovers by itself after worker/API restart; no data loss on crash (transactions, backups) |
| Security | OWASP ASVS L1 for the parts that apply; no high findings in ZAP baseline; deps audited each run |
| Privacy | data leaves the machine only via the documented table (README), with consent; no telemetry |
| Accessibility | WCAG 2.2 AA; keyboard complete; reduced motion |
| Cost | AI cost visible in dollars; default 5 USD/day hard cap; per-run caps |
| Observability | structured logs with request/task id; `/system/status`; metrics endpoint |
| Maintainability | module boundaries enforced; rule modules 95% covered; docs updated with code |

## 7. Scalability path (what changes at each stage, and the trigger to move)
| Stage | Shape | Changes needed | Trigger |
|---|---|---|---|
| 1 Single user, laptop (now) | API+worker in one process, Postgres in Docker | none | |
| 2 Single user, containers | API, worker, web, Postgres as separate containers | Dockerfiles, compose, worker split (H01) | wanting one-command start |
| 3 Few users, one server | Same, behind HTTPS, real accounts | OIDC or password reset flow, per-user settings/keys (B03, B20), rate limits (B07), email-free invites, backups off-box | a second person wants to use it |
| 4 Many users, cloud | Several API instances, separate workers, managed Postgres, object storage | stateless API (sessions already in DB), queue priorities and limits (H02), read replicas if needed, pgvector tuning (H16), observability stack, tenant quotas | sustained load or reliability needs |
| 5 Heavy research load | Dedicated queue (Redis/Celery or a managed queue) | Replace `tasks/service.py` behind its interface; handlers unchanged | queue depth or latency beyond what Postgres `SKIP LOCKED` handles (rule of thumb: thousands of tasks/minute) |
Principles that make this possible and must not be broken: no global state in the API; every table owner-scoped; handlers idempotent; external services behind interfaces (LLM, search, embeddings, clock); config only from environment; schema only via migrations.

## 8. Out of scope here
See `01-requirements.md` section 5.
