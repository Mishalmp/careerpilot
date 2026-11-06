# Phase 7+: product redesign, learning platform, architecture explorer

Status: **plan written, nothing built yet** (written 2026-11-06). Read this file first in any new session.

## Why this exists
After Phases 0 to 6 the app works but looks like a developer prototype. The owner asked for:
1. A professional SaaS look: **light mode in blue, plus a dark mode**, simple and elegant, with a logo, icons and a real design system.
2. A **learning platform** inside the app: interview topics, questions, multiple choice, practical exercises, checkpoint exams. Nothing predefined: when a new job is added the system searches the web for the interview topics and questions that job needs (an agentic workflow), the owner approves them, studies them, practises them, and is examined on what was learned.
3. An **architecture explorer** in the frontend: every service, concept, logic and workflow shown as interactive diagrams, not just text, so an intermediate engineer can learn how the whole app works.
4. A **senior-level review** of the system design (queues, database, RAG, MCP, failure handling, anomalies) with redesigns where needed, and everything broken into **micro tasks** with end-to-end checks.

## The files (read in this order)
| File | What it holds |
|---|---|
| [01-requirements.md](01-requirements.md) | The request, restated as numbered requirements, with how each will be proven. Decisions that need the owner's approval. |
| [02-design-system.md](02-design-system.md) | Reference products, the chosen look, colour tokens (light and dark), type, icons, logo, layout, every screen's redesign, accessibility, frontend security. |
| [03-learning-platform.md](03-learning-platform.md) | The agentic research flow, question types, grounding and anti-hallucination rules, spaced repetition, checkpoints and exams, data model, failure handling. |
| [04-architecture-explorer.md](04-architecture-explorer.md) | The interactive "how this app works" section: pages, diagrams, live status, content model, anti-drift tests. |
| [05-system-review.md](05-system-review.md) | Issues found in the current system, ranked, with the redesign or decision for each (queue, DB, RAG, MCP, LLM, security, frontend, process). Failure-mode tables. |
| [06-concepts-primer.md](06-concepts-primer.md) | Teaching notes for an intermediate engineer: the concepts behind this app (sessions, CSRF, SSRF, transactions, queues, RAG, MCP, spaced repetition...). Source material for the explorer's concept pages. |
| [07-tasks.md](07-tasks.md) | **The work list.** Atomic tasks with IDs, dependencies, size, and "done when" checks. Tick boxes as work completes. |
| [08-ai-development-playbook.md](08-ai-development-playbook.md) | How AI is used to build this product: lifecycle, roles, the 15 intake questions, guardrails, session handoff, definitions of ready and done. |
| [09-product-spec.md](09-product-spec.md) | The foundation A to Z: purpose, domain objects, each feature's inputs, outputs, rules, edge cases, routes, API conventions, targets, scalability path. |
| [10-test-strategy.md](10-test-strategy.md) | Test layers, data, LLM evals, AI QA agents, CI gates, the test-case catalogue, failure drills. |
| [11-ai-usage-search-and-apply.md](11-ai-usage-search-and-apply.md) | AI access without a key, costs, model/context rules, MCP and RAG rules, security checklist, free and cheap search APIs with verified rates, and the assisted daily-apply design. |
| [STATUS.md](STATUS.md) | Where work stopped and what is next. Update before ending any session. |
| [assets/](assets) | Logo concept files (mark, wordmark light and dark). |

## How to continue in a new session (context is limited)
1. Read this file, then `07-tasks.md`. Find the first unchecked task whose dependencies are checked.
2. Read only the section of the other files that task names. Do not reload everything.
3. Do the task. Run its "done when" check. Tick the box in `07-tasks.md` and add the commit id.
4. Keep rules in `CLAUDE.md` (no copies, one source of truth, tests per change, owner scoping, no send actions).
5. If a task turns out wrong, change the plan file first, then the code, and note why at the bottom of `07-tasks.md` under "Changes to the plan".

## Facts any session must know (so they are not rediscovered)
- Windows machine. `uv` is not on PATH: use `python -m uv ...`. Shell is Git Bash or PowerShell; `cp` does not exist in cmd.
- Ports: web 3100, **API 8010** (8000 belongs to the user's Elphi Docker container), Postgres 5433 (Docker, container `careerpilot-postgres-1`).
- Tests use the `careerpilot_test` database and **truncate users**; any dev servers pointed at it lose their user after a test run.
- No git remote. Branches `phase-0..6` form one line; `main` exists at the latest commit. CI has never run.
- No Anthropic API key has ever been used. All model features are tested only with fakes. First live step is `llm-check` (task E01).
- The tool layer turns typed escape sequences (`\n`, `\x00`, `’`) into real characters when files are written through shell heredocs or Python strings. Write files with the file-writing tool, and check for stray control characters.
- Next.js 16 here differs from older versions: read `apps/web/node_modules/next/dist/docs/` before changing routing or config. `next build` fetches Google fonts and fails offline (task D06 removes that by self-hosting fonts).
- Existing modules: auth, tracker, prep, practice, knowledge, today, verification, scoring, outreach, intel, mock, discovery, tasks, digest, analytics, offers, stories (17). 81 API operations, 13 migrations, 809 backend tests, 42 web tests.

## Decisions the owner must make before building (details in 01-requirements.md section 4)
D1 design system: shadcn/ui + Radix + Tailwind (recommended). D2 web search source for the research agent (recommended: Brave Search API, behind an interface; Anthropic web search as an option). D3 long operations become background tasks with progress (recommended). D4 Docker for the whole stack. D5 name and logo direction. D6 whether study content may be sent to Claude. D7 question-bank content rules (links and short quotes, not copied text). D8 FSRS for spaced repetition. D9 React Flow for diagrams. D10 move the scoring profile from YAML into the database. None is approved yet (task Q02).
