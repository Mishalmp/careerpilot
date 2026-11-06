# STATUS: read this first when resuming (keep it short and current)

Updated: 2026-11-06 by the session that wrote the Phase 7 plan.

## Where we are
- Phases 0 to 6 are built and committed on branch `phase-6-hardening` (`main` is one commit behind it). 809 backend tests, 42 web tests, all gates green locally. GitHub CI has never run.
- **Phase 7 is documentation only so far. No Phase 7 code has been written.** The complete document set is in `docs/phase-7/`: README (index), 01 requirements and decisions, 02 design system, 03 learning platform, 04 architecture explorer, 05 system review, 06 concepts primer, 07 tasks (about 250 atomic tasks), 08 AI development playbook, 09 product spec, 10 test strategy, `assets/` (logo concept SVGs).
- Task `X01` (write the plan) is done. Everything else in `07-tasks.md` is unchecked.
- Task ids in docs 02 to 05 were cross-checked against `07-tasks.md` on 2026-11-06. If you add or renumber tasks, grep the other docs for the old id.
- The owner reported that the UI "sucks" and asked for: blue SaaS design (light + dark), a learning platform with agentic web research for interview topics, an interactive architecture explorer, a senior system review, micro tasks, and AI-driven development and testing done the way real teams do it.

## What the next session should do
1. Read `docs/phase-7/README.md`, then `08-ai-development-playbook.md` (how to work with this owner).
2. Ask the owner the **15 intake questions** in `08` section 4 that are still unanswered; record answers in `01-requirements.md` section 4. Ask them to approve or change decisions D1 to D10 (task Q02) and, optionally, send reference screenshots (Q03).
3. Work `07-tasks.md` from the top: first unchecked task whose dependencies are done. Suggested order for the owner's top complaint: Q01-Q02, D01-D22 (design system, gate D21 owner review), then P-pages. In parallel when a key exists: E01, E02 (first live AI check).
4. Do **not** start UI or feature code until Q02 is answered, because D1 (UI foundation) and D2 (search provider) change what gets built.
5. Before ending: tick finished tasks with commit ids, update this file.

## Decisions status (details: 01-requirements.md section 4)
All proposed, **none approved yet**: D1 shadcn/ui + Radix + Tailwind, D2 Brave Search behind `SearchProvider`, D3 long operations as background tasks, D4 full Docker, D5 keep the name and a paper-plane logo, D6 sending study content to Claude, D7 question-bank content rules, D8 FSRS, D9 React Flow, D10 profile in the database.

## Known blockers and open items
- No Anthropic API key has ever been used: every model feature is tested only with fakes. Task E01 runs the first live check (`llm-check`); it needs the owner to put a key in `.env` (Q04).
- GitHub CI has never run (no remote): owner task X09.
- Unverified claims to re-check before relying on them: Radix colour values (D01), search-provider prices (R01), MCP spec revision details (H17), `fsrs` package API (L08).
- I could not view the reference products' live UIs; the design research is from published text. Screenshots from the owner (Q03) would improve it.
- Owner housekeeping from before: run `create-user` on the dev DB; restart old dev servers on ports 8000/3100 (API now 8010).

## Last verified facts (re-check if older than a week)
- Ports: web 3100, API 8010, Postgres 5433 (container `careerpilot-postgres-1`). `python -m uv` instead of `uv` on this Windows machine.
- Dev database migrated to revision 0013; no user created yet in the dev DB.
- Tests use the `careerpilot_test` database and truncate users.
