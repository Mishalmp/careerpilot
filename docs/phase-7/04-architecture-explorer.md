# 04: Architecture explorer (the app explains itself)

Covers REQ-14 to REQ-17 and REQ-27. Tasks: group V (and W) in `07-tasks.md`. Test cases: `10` section for EXP.

## 1. Purpose
A section of the web app, `/architecture`, where you can see and click through how CareerPilot works: services, modules, data, flows, concepts, decisions, live health. It is both a teaching tool (you are an intermediate engineer preparing for interviews) and the living documentation a new contributor or a new Claude session can use. It is **read-only** and needs no model.

## 2. Principles
1. **Content is data, not code.** Diagrams, flows and concept pages live in `content/architecture/` as YAML and Markdown (rule 2: content only under `content/`).
2. **No drift.** Wherever a fact can be derived from the code (modules, routes, tables, tasks, prompts, tools), it is generated or checked by a test; hand-written parts reference ids that the test verifies exist.
3. **Show, then tell.** Each page leads with a picture or an interaction, then the words.
4. **Honest.** Each concept page says how it appears in this app, its failure modes, and the test that proves it. Where something is a planned design, it is labelled "planned".
5. **Accessible.** Every diagram has a text alternative and a keyboard path (a list view of the same nodes).

## 3. Information architecture
```
/architecture
 ├─ overview        system map (C4 level 1-2): people, web, API, worker, Postgres, external services
 ├─ modules         module graph (levels 3): 20 modules, allowed imports (from import-linter contracts)
 ├─ flows           playable sequences (see section 5)
 ├─ data            ERD: tables, columns, relations, owner scoping, indexes
 ├─ concepts        concept library (section 6)
 ├─ decisions       ADR viewer (docs/adr) + Phase 7 decisions D1-D10 with status
 ├─ status          live: services up, queue depth, last runs, spend, backup age, migration head
 ├─ drills          failure drills: "what happens if X fails", with the real test
 └─ glossary        terms with links
```

## 4. Diagrams
**Library**: React Flow (`@xyflow/react`, D9) for node-and-edge views; plain SVG for small illustrations (RAG pipeline, queue lifecycle). Layout is precomputed in the content file (x, y) so there is no runtime layout engine; a layout helper is a dev script only.
**Overview (C4 levels)**: level 1 context (you, Postgres, Claude API, search provider, job boards, company sites); level 2 containers (web, API, worker, Postgres, MCP server, browser workers for code); level 3 per container on click (modules). Zoom = drilling down; breadcrumb to go up.
**Module graph**: nodes = modules, edges = allowed imports (service/schemas/dependencies only), generated from the import-linter config; a forbidden edge is shown only in a "rules" overlay.
**Node data**: `id`, `kind` (service, module, store, external, ui), `title`, `summary` (one sentence), `owns` (tables/prompts/tasks), `links` (code path, ADR, concept), `status_probe` (optional key used by live status).
**Interactions**: hover = summary; click = side panel (what it does, inputs/outputs, failure behaviour, tests, code link); search box filters nodes; filter chips by kind; keyboard: arrows move between nodes, Enter opens panel, Esc closes; "list view" toggle for screen readers.
**Layers/overlays**: Data flow (default), Security (trust boundaries, auth, CSRF, SSRF guard), AI (where models are called, budgets), Failure (what breaks and what happens), Ownership (owner_id scoping).

## 5. Flow player
A flow is an ordered list of steps over nodes: `{from, to, label, payload_example, notes, failure?}`. The player highlights the active edge, shows the payload, and has Previous / Next / Play. A step can have a **failure branch** (button "What if this fails?") which swaps in the alternative steps and the expected behaviour.
Initial flows (each ends with the test id that covers it):
1. Sign-in and session (cookie, CSRF).
2. Add a job (quick add, dedupe fingerprint, optimistic UI).
3. Company check (task, fetch, quotes verified, verdict by rule).
4. Research for a job (plan, search, fetch, extract, verify, inbox, approve).
5. Study loop (answer, grade, FSRS update, due queue).
6. Checkpoint exam (build, snapshot, run, submit, report, boosts).
7. Ask my notes (embed, hybrid search, fuse, gate, cite).
8. MCP tool call with preview and confirm.
9. Background task lifecycle (enqueue, claim, heartbeat, retry, dead).
10. Backup and restore into a new database.
11. Discovery run and daily digest.
12. Practice runner (code stays in the browser worker under CSP).

## 6. Concept library
Each concept is one Markdown file with front matter and fixed sections, so the UI renders them uniformly.
```
---
id: rag
title: Retrieval-augmented generation
level: intermediate
related: [embeddings, hybrid-search, prompt-injection, evals]
appears_in: [module:notes, flow:ask-notes]
proof: [tests/test_rag_eval.py, tests/test_notes_*.py]
---
## In one minute
## Why it exists
## How it works (diagram id: rag-pipeline)
## How it appears in CareerPilot
## How it fails (table: failure, symptom, our behaviour)
## Try it (widget id)
## Interview questions (links to question bank topics)
## Further reading (checked links)
```
**Initial concepts** (full text drafted in `06-concepts-primer.md`, then moved to content): sessions and CSRF; password hashing; SSRF; prompt injection; transactions and isolation; optimistic concurrency; idempotency; queues and leases (SKIP LOCKED); outbox pattern; retries, backoff, jitter; embeddings; chunking; hybrid search and rank fusion; RAG and evals; MCP; agents vs workflows; token budgets and cost; grounding and quote verification; spaced repetition (FSRS); content security policy; migrations (expand/contract); observability; multi-tenancy; backups and restore testing.
**Try-it widgets** (small client components, deterministic, no network): chunking sliders (see chunks and overlap); rank fusion calculator (two ranked lists to a fused list); FSRS simulator (answer pattern to schedule); retry/backoff timeline; SSRF checker (type a URL, see which rule blocks it, using a pure JS port of the rules with a parity test); idempotency demo (send twice, see one row, with a mock); token/cost estimator; CSP explainer.
Widgets that mirror backend rules must have a **parity test**: same table of cases run against both implementations.

## 7. ERD page
Generated from SQLAlchemy metadata at build time into `content/architecture/generated/schema.json` (tables, columns, types, nullability, foreign keys, indexes, comments). Hand-written descriptions live in `content/architecture/tables.yaml` keyed by table name. Drift test: every table has a description, every described table exists. UI: tables grouped by module, relationship lines on focus (not all at once), click a table for columns, constraints, owner scoping, and which services read/write it.

## 8. Live status page
Reads `GET /api/v1/system/status` (exists in part) extended with: API/worker/database up, migration head vs expected, queue counts by status and kind, oldest queued age, last run per scheduled job, failed tasks (with link), LLM spend today vs cap, search spend, last backup and last verified restore, disk space, embedding stale count. Colour + text + icon for each (never colour alone). Polling every 15 s while the tab is visible; stale data marked.

## 9. Failure drills page
A table of drills: "Kill the worker", "Provider returns 429", "Database slow", "Page contains an injection", "Backup key wrong". Each shows: what you would see, what the system does, which test proves it (id and file), and a copyable command to reproduce locally. It never runs destructive actions from the browser.

## 10. Decisions page
Renders `docs/adr/*.md` (copied at build time into `content/architecture/generated/adr/` or read through an API route) plus Phase 7 decisions D1-D10 with their status (proposed, accepted, changed). Each decision links to affected modules.

## 11. Data contracts and files
```
content/architecture/
  systems.yaml        nodes and edges per diagram level (layout included)
  flows/<id>.yaml     steps with failures
  concepts/<id>.md    concept pages (front matter above)
  tables.yaml         table descriptions
  drills.yaml         failure drills
  glossary.yaml
  generated/          (git-tracked, produced by `careerpilot export-architecture`)
    modules.json  routes.json  schema.json  tasks.json  prompts.json  mcp-tools.json
```
`careerpilot export-architecture` is a new CLI command (added to task V02, which also serves the same data through the API) that writes the generated files from code: import-linter contracts, FastAPI routes, SQLAlchemy metadata, task kinds, prompt files, MCP tool list. The web reads them through a typed loader (zod or generated types) at build time.

## 12. Drift tests (REQ-17)
1. Generated files equal a fresh export (CI fails on diff).
2. Every module in the code appears in `systems.yaml`; every node referencing a module id points at a real one.
3. Every flow step references existing node ids; every `proof` path in a concept exists; every `appears_in` id exists.
4. Every concept link and ADR link resolves; external links checked by a scheduled job only (not on every CI run).
5. Every table has a description; every route group appears in some flow or the route list.
6. Widget parity tests (section 6).

## 13. Performance and size
Diagrams render client-side from JSON of a few hundred nodes at most; React Flow is loaded only on `/architecture` routes (dynamic import) to keep other pages light. Target: explorer first interaction < 2 s warm. Pages are static where possible.

## 14. Accessibility
List view equal to the diagram; focus order logical; visible focus; reduced motion disables flow auto-play animation; colour never the only signal; minimum node text 14 px at default zoom.

## 15. Acceptance (summary; detailed cases in `10`)
You can start at the overview, drill into the worker, open the "Background task lifecycle" flow, step through a failure branch, open the linked concept "queues and leases", use the backoff widget, and find the test that proves it, using only the keyboard if you want. Drift tests pass; a deliberately renamed module makes a test fail with a clear message.
