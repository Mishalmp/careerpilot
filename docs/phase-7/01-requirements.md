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

## 5. Non-goals (for now)
Native mobile apps. Real-time collaboration. Paying customers and billing. Email sending of any kind (the no-send rule stays). Bulk scraping of job sites that forbid it. A server-side code runner. Voice interviews.

## 6. Assumptions and open questions
- Assumption: still a single owner on one machine; multi-user is a design constraint, not a feature.
- Assumption: Chrome/Edge latest is the main browser.
- Open: does the owner want exam results to be shareable (PDF)? Default: no.
- Open: which target companies first (seeds the first research runs)? Ask at Q01.
- Unverified claims from research (re-check before relying): Brave and Tavily prices; the exact current Anthropic web-search tool version; the `open-interview` project's features; Radix colour hex values (task D01).
