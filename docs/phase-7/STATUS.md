# STATUS: read this first when resuming (keep it short and current)

Updated: 2026-11-06 by the session that wrote the Phase 7 plan.

## Where we are
- Phases 0 to 6 are built and committed on branch `phase-6-hardening` (`main` is behind it). Gates were green locally; GitHub CI has never run.
- **Phase 7 build has started (2026-11-06).** Documentation set: `docs/phase-7/` (README index, 01 to 10, tasks in 07, owner answers in `01` section 4a).
- **Owner answers recorded** (01 section 4a): decisions D1 to D10 resolved (D2: SearXNG default + Brave optional + manual paste; D4: native dev default, full Docker Compose for portability). Owner works 2-3 h/day, more at weekends; first month alone, then 5-10 invited users.
- **Done in code** (see `07-tasks.md`, [x] and [~] marks): design tokens (Radix blue/slate, light + dark, contrast script in vitest), theme + density (cookies, no flash), self-hosted fonts, primitives in `apps/web/src/components/ui/*`, new AppShell (grouped sidebar, drawer, theme menu), logo + favicon, PageHeader, Jobs page + Add job dialog redesigned, every existing page mapped to tokens.
- **E2E**: `cd apps/web && npm run e2e` starts its own API (port 8011, DB `careerpilot_e2e`, recreated each run) and a production web build (port 3101) using the installed Chrome. 41 tests: theme, shell, mobile, axe on every page in both themes, jobs flows. Screenshots land in `apps/web/e2e/.shots/` (git-ignored): look at them after UI work.
- **Not done yet**: pages other than Jobs still have their old internal layout (themed, not redesigned): Today, Job detail, Discover, Prep, Practice, Ask, Mock, Insights, Offers, Stories, Tasks (tasks P01, P02, P05, P07, P09-P17). Backend platform B-tasks, learning platform L/LU/R tasks, architecture explorer V tasks, hardening H tasks, containers K tasks: all not started.
- **Gotchas learned**: `npm run e2e` rebuilds the web app each run (about 40 s). Dev server on port 3100 may be a stale process from earlier; Next allows one dev server per directory, so reuse it or stop it from your own terminal. Pages send no CSP yet (task H20). `tabular-nums` on Inter looked odd in table cells, so it is not used there.
- **Security note for the owner**: an earlier commit briefly included a README line with a real-looking password; it was removed and that commit amended before any push. If that password is real, change it, and note the old commit object may still exist in `git reflog` until it expires.

## What the next session should do
1. Read `docs/phase-7/README.md`, then `08-ai-development-playbook.md` (how to work with this owner).
2. Ask the owner the **15 intake questions** in `08` section 4 that are still unanswered; record answers in `01-requirements.md` section 4. Ask them to approve or change decisions D1 to D10 (task Q02) and, optionally, send reference screenshots (Q03).
3. Work `07-tasks.md` from the top: first unchecked or [~] task whose dependencies are done. Suggested order now: finish P-pages (Today P02, Job detail P05, then the rest), backend B01-B05 (status, task progress), then learning backend L02-L10. In parallel when a key exists: E01, E02 (first live AI check).
4. After UI work run `npm run e2e` and read the screenshots; after backend work run the API tests (`cd apps/api && python -m uv run pytest`).
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
