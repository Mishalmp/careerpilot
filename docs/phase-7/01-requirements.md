# 01: Requirements and decisions

Everything the owner asked for, restated as numbered requirements (REQ-nn) that each map to tasks (`07-tasks.md`) and tests (`10-test-strategy.md`). If a requirement is wrong or missing, fix it here first.

## 1. The owner's words, condensed
"The UI sucks." Find similar products, choose UI, logo, icons, light mode in blue and a dark mode, simple elegant, a proper SaaS/PaaS look, seamless UX. Break everything into micro tasks, cross-validate end to end, redesign system design, logic and concepts where needed (MCP, RAG, Celery or Redis queuing), cover all edge cases, failure handling, DB issues. Educate me as an intermediate engineer. Add interview topics in the frontend, but nothing is predefined: when I apply to a new job, search the web for related interview questions, topics and practical questions like an AI agent, and let me practise them here; build question lists, multiple choice and checkpoint exams from what I learned (refer to existing platforms). Show the architecture, services, concepts, logic and workflows inside the frontend as interactive diagrams. Document everything first because context is almost over. Use AI the right way for a SaaS: define architecture, objects, expectations, inputs and outputs, edge cases, all test cases, AI-driven end-to-end testing, and ask me for inputs like real teams do. A new Claude session must continue exactly where this one stopped. It must scale in future.

## 2. Requirements
**Look and feel**
- REQ-01 Blue-based light theme and a matching dark theme; switch in the UI, remember the choice, follow the system by default, no flash on load.
- REQ-02 One design system (tokens, components, patterns) used by every screen; no ad-hoc colours or spacing.
- REQ-03 A logo, favicon and one consistent icon set.
- REQ-04 Seamless UX: instant feedback (skeletons, optimistic updates with rollback), keyboard shortcuts and a command palette, responsive from phone to desktop, WCAG 2.2 AA accessibility.
- REQ-05 Frontend security does not regress: CSP intact, no XSS paths for stored or researched text, no secrets in the browser.

**Learning platform**
- REQ-06 No predefined roadmap: topics, order and plans are editable; the seeded curriculum is only an import that can be changed or deleted.
- REQ-07 Adding a job can start an agentic research run (web search, fetch, extract, evaluate) under strict budgets; results land in an inbox; nothing enters the question bank without the owner's approval.
- REQ-08 Every researched item shows source link, date, a verified short quote and a reliability score; nothing is invented.
- REQ-09 Question types: multiple choice (single and multiple answer), short answer with rubric grading, practical coding and SQL, explain-in-your-words, and scenario/system-design.
- REQ-10 Practical questions run in the existing in-browser runner; owner-added or AI-drafted problems are validated (reference solution passes the tests) before saving.
- REQ-11 Spaced repetition (FSRS) schedules reviews per question from the owner's answers.
- REQ-12 Checkpoint exams are built from what has been studied: timed, scored, per-topic report, results feed the review queue.
- REQ-13 Mastery per topic and gaps against target jobs are visible; the roadmap can be generated from gaps and edited.

**Architecture explorer**
- REQ-14 Interactive diagrams of services, modules, data and workflows inside the app, with step-by-step playable flows.
- REQ-15 Concept pages (RAG, MCP, queues, SSRF, prompt injection, transactions, FSRS and more) with what, why, how it appears in this app, failure modes, a "try it" widget and the test that proves it.
- REQ-16 Live system status (services, queue, last runs, cost, backup age).
- REQ-17 Explorer content cannot silently drift from the code (tests fail on drift).

**System quality**
- REQ-18 A written senior review of the system with issues ranked, redesigns decided, and each failure mode's behaviour defined and tested.
- REQ-19 Long operations never block a request: they run as tasks with visible progress; failures are visible and retryable.
- REQ-20 Every AI call is budgeted (per call, per run, per day, in dollars) and audited.
- REQ-21 AI output is controlled: evals with thresholds, grounding checks, independent graders, human approval gates; no model decides a verdict, score or permission.
- REQ-22 Scalable path: per-user isolation everywhere, documented route from one user to many and from a laptop to the cloud.
- REQ-23 One command starts the whole stack in containers; native development keeps working.

**Process**
- REQ-24 Complete documentation, `STATUS.md` and memory notes so a fresh session continues without loss.
- REQ-25 Atomic tasks with dependencies and checks; each requirement traces to tests.
- REQ-26 AI-driven end-to-end testing in addition to conventional tests, with reports a human reviews.
- REQ-27 Education: every concept explained at an intermediate level in docs and in the app.

## 3. Traceability (requirement to tasks)
| Requirement | Tasks |
|---|---|
| REQ-01, 02, 03 | D01-D22, D12 |
| REQ-04 | D10, D11, D13, P01-P17, T04, T20 |
| REQ-05 | D05, H20, H22 |
| REQ-06, 13 | L02, L07, L20, LU02 |
| REQ-07, 08 | R01-R15, LU07, E03 |
| REQ-09, 10 | L10, L13-L15, LU04, LU05 |
| REQ-11 | L08, L09, L16, LU06 |
| REQ-12 | L18, L19, LU09 |
| REQ-14, 15, 16, 17 | V01-V18, W01-W04 |
| REQ-18 | `05-system-review.md`, H01-H26 |
| REQ-19 | B04, B05, H01-H05 |
| REQ-20, 21 | E01-E12, B07, H19 |
| REQ-22 | B03, B20, K01-K10, H11 |
| REQ-23 | K01-K10 |
| REQ-24 | X01, X06, W06 |
| REQ-25, 26 | T01-T20 |
| REQ-27 | W01-W05, `06-concepts-primer.md` |

## 4. Decisions (all **proposed**; owner approves or changes; record the answer in the "Answer" column)
| ID | Decision | Recommendation and why | Alternatives and cost of reversing | Answer |
|---|---|---|---|---|
| D1 | UI foundation | **shadcn/ui components copied into the repo, on Radix primitives and Tailwind v4, tokens as CSS variables (OKLCH).** You own the code, accessibility comes from Radix, it is the de-facto SaaS look, dark mode is just a second set of variable values. | Material UI or Chakra (heavier, own styling system), Mantine. Reversal: high (every component) | |
| D2 | Web search for the research agent | **Brave Search API behind a `SearchProvider` interface**; manual paste always works. Brave has its own index and a simple API; vendor-stated pricing roughly 3-9 USD per 1,000 queries (verify before use). | Anthropic web search tool (10 USD per 1,000 searches plus tokens, checked 2026-11-06; tied to the Claude API), Tavily (easy, credit based), SearXNG self-hosted (free, you run it). Reversal: low (interface) | |
| D3 | Long operations | **Run as background tasks returning 202 with a task id, progress events over SSE, polling fallback.** Keeps requests short and gives retry and visibility. | Keep synchronous with longer timeouts (simple, breaks on slow runs). Reversal: medium | |
| D4 | Containers | **Add Dockerfiles and a compose profile for the whole stack; keep native dev.** | Stay Postgres-only (current). Reversal: low | |
| D5 | Name and logo | **Keep CareerPilot; paper-plane mark in blue** (`assets/logo-mark.svg` is a concept to refine in D12). | Rename now (cheap now, costly later) | |
| D6 | Study content to Claude | **Allowed when a key is set** for notes, answers, job descriptions and fetched public pages; never the profile file, contact emails, backups or keys. See the table in the README. | Local-only model (not available), or ask each time | |
| D7 | Question-bank content rules | **Store links, short verified quotes and our own paraphrase; never copy long text or scrape review sites** (Glassdoor, LinkedIn, Indeed stay blocked). Respect robots.txt. | Store full text (copyright and terms risk) | |
| D8 | Spaced repetition algorithm | **FSRS via the Python `fsrs` package, pinned**, with SM-2-like fallback not needed. FSRS is the modern open algorithm; an official TypeScript package and ports exist. | SM-2 (older, simpler). Reversal: low (scheduler behind an interface) | |
| D9 | Diagram library | **React Flow (`@xyflow/react`)** for interactive node diagrams; plain SVG/CSS for small illustrations. | Mermaid (static), tldraw (heavy), D3 (more work). Reversal: medium | |
| D10 | Profile storage | **Move the scoring profile from a YAML file into the database** with an edit screen (needed for a Settings page); keep YAML import once. | Keep YAML (no UI edit). Reversal: low | |

## 4a. Owner answers and resolved decisions (recorded 2026-11-06)
**Intake answers (from the owner)**
| # | Answer | Consequence |
|---|---|---|
| 1 | The owner alone for the first month while it is built properly; then 5 to 10 invited users, then scale after their feedback | Stage 3 of the scalability path (`09` section 7) moves from "later" to "next after Release A+B": invite-only sign-up, per-user settings and keys/budgets, isolation tests (tasks B03, B20, B21) |
| 2 | Roles come from the CV: full stack, Python full stack, software developer/engineer, SDE and similar names. Everything must be dynamic from CV content, including interview roadmaps | New requirement REQ-28; tasks B03 (profile in DB), R16 (derive skills, role titles and research seeds from CV text) |
| 3 | 2 to 3 hours a day, 5 to 12 hours on weekends | Plan sizing in `07`; roadmap defaults in `03` |
| 4 | Ready = 80% on a checkpoint across high-priority topics, twice, a week apart | Default pass mark and "ready" rule in `03` section 8 |
| 5 | Linear, Vercel, Huntr are fine; use the best modern UI/UX; responsive almost everywhere | `02` unchanged; responsiveness is in every page checklist |
| 6 | Keep the name and logo; provide light and dark versions and different sizes (compact and full) for different places | Logo set in D12: mark, wordmark (light/dark), compact; UI density setting (comfortable/compact), task D23 |
| 7 | English only | |
| 8 | Prefers a small amount; asked what is possible with the current account | See "AI cost and access" below |
| 9 | Study content may be sent to Claude | D6 approved (profile file, contact emails, backups, keys still never sent) |
| 10 | Use whichever is free/open-source/cheap and best; must work perfectly | See "Search source" below |
| 11 | My call; avoid struggles when deploying or pulling on another OS; environment independent | See D4 |
| 12 | Laptop now; private GitHub repo; cloud later | X09 stays an owner task; stage 3 hosting is a later epic |
| 13 | Backups stay on the laptop; the owner zips and copies them to cloud storage; wants step-by-step notes for deploying and using on another OS or laptop | New task W09 (portability guide) |
| 14 | Chrome first; Edge/Firefox default | Playwright runs Chromium first |
| 15 | WCAG 2.2 AA | |
**Owner instruction on process**: if a skill or knowledge is missing, find it on the internet, cross-validate, test end to end; work automatically step by step without stopping.

**AI cost and access (verified 2026-11-06)**
- A Claude Pro subscription does not include an API key. API use is a separate Console account billed by prepaid credits; third-party guides say the minimum top-up is 5 USD (not confirmed by Anthropic's own page). Credits expire after one year and are non-refundable (Anthropic help article as summarised in a search result).
- Prices from Anthropic's pricing page (fetched 2026-11-06), per million tokens, input / output: Haiku 5.5 0.10 / 0.50 USD (prompts up to 100k tokens), Sonnet 5.5 2 / 10, Opus 5.5 4 / 20.
- Plan: use **Haiku 5.5** for extraction, MCQ generation and evaluation; **Sonnet 5.5** only for graders that need judgement and for the hardest steps, chosen by the eval scores (E10). A research run of 80k tokens costs roughly 0.01 to 0.05 USD on Haiku (arithmetic from the prices above; to be measured).
- Default caps for the owner: 1 USD/day and 10 USD/month, hard stop (settings; shown in the UI). Raise later.
- No free hosted API exists for this; a free local open-source model through a provider interface (for example Ollama) is possible later but quality for grading is unproven, so it is not part of the first build.
- The optional `claude -p` provider (plan section 15) stays off by default.

**Search source (verified 2026-11-06 from search results; confirm on the vendors' own pages before paying)**
- Brave Search API: reports say the old free tier was replaced in early 2026 by about 5 USD of monthly credit (roughly 1,000 queries), a card is required, and overage is billed.
- SearXNG (open source, self-hosted metasearch): free; JSON output must be enabled in `settings.yml`; its bot limiter can return 429 to API clients unless configured; reliability depends on upstream engines. **Tested 2026-11-06**: the `searxng/searxng` container with `docker/searxng/settings.yml` (JSON on, limiter off) returned 38 real results for a research query, and our adapter parsed them; DuckDuckGo answered with a CAPTCHA (engines vary), others answered.
- Anthropic web search tool: 10 USD per 1,000 searches plus tokens.
- Decision D2 (resolved): the `SearchProvider` interface ships with a Fake, a **SearXNG** adapter (default, free, runs in the compose `tools` profile) and a **Brave** adapter (optional, when the owner adds a key). Manual paste always works. Task R17 (the spike) is done and SearXNG works; Brave stays optional. Result quality of free engines varies by day, so keep manual paste available.

**Decisions resolved (owner said "your choice" or accepted defaults)**
| ID | Result |
|---|---|
| D1 | Approved: shadcn/ui + Radix + Tailwind v4 |
| D2 | Resolved as above (SearXNG default, Brave optional, manual paste) |
| D3 | Approved: long operations as tasks |
| D4 | Resolved: **native development stays the default** (fast, agents are quicker); a complete Docker Compose stack (db, api, worker, web, optional searxng) is the portable path for other machines and deployment; both use the same `.env` and one `scripts/dev.py`; no machine-specific paths in the repo |
| D5 | Approved: keep CareerPilot; logo set with light/dark and compact/full variants |
| D6 | Approved |
| D7 | Approved |
| D8 | Approved: FSRS (Python `fsrs`, pinned; confirm API at L08) |
| D9 | Approved: React Flow |
| D10 | Approved: profile in the database, derived from the CV (REQ-28) |
Any of these can be reopened; reversal costs are in the table above.

## 4b. Added requirements
- REQ-28 Dynamic from the CV: the profile (skills, years, role titles, seniority) is derived from the owner's CV text, editable, and drives scoring, research seeds, roadmap and gap analysis; no role list is hard-coded.
- REQ-29 Invite-only multi-user for 5 to 10 people after the first month: separate data, separate budgets, a shared server-side API key with per-user caps, admin-created invites.
- REQ-30 Portable setup: the same steps work on Windows, macOS and Linux; a written step-by-step guide covers new machine setup, deployment, backup zip and restore.
- REQ-31 Visual variants: light and dark themes, and comfortable and compact density; logo mark, wordmark and compact forms.

## 5. Non-goals (for now)
Native mobile apps. Real-time collaboration. Paying customers and billing. Email sending of any kind (the no-send rule stays). Bulk scraping of job sites that forbid it. A server-side code runner. Voice interviews.

## 6. Assumptions and open questions
- Assumption: still a single owner on one machine; multi-user is a design constraint, not a feature.
- Assumption: Chrome/Edge latest is the main browser.
- Open: does the owner want exam results to be shareable (PDF)? Default: no.
- Open: which target companies first (seeds the first research runs)? Ask at Q01.
- Unverified claims from research (re-check before relying): Brave and Tavily prices; the exact current Anthropic web-search tool version; the `open-interview` project's features; Radix colour hex values (task D01).
