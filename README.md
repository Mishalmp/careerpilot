# CareerPilot

Job application tracker, interview prep, an in-browser practice editor, and a place to learn how RAG and MCP are built. Local-first, single user. The full design is in [plan.md](plan.md); decisions are in [docs/adr](docs/adr).

Status: Phase 5. Track jobs, follow the 45-day prep plan, practise 28 problems in an in-browser editor (Python, JavaScript, TypeScript, SQL), ask questions of your own notes with cited answers, and let Claude Desktop or Claude Code use your tracker through an MCP server. Each job page also checks whether the company looks genuine (with quoted evidence), scores the fit against your profile, collects interview intel, and keeps outreach drafts that need your approval (nothing is ever sent for you). A mock interviewer asks and scores questions on a job or topic. Follow companies' public job boards (Greenhouse, Lever, Ashby): new listings wait in an inbox until you add them to the tracker, and a daily digest summarises the day. Learn how the last two are built in [docs/learn](docs/learn).

## Requirements
Docker Desktop, Python 3.12, Node 22, and `uv` (`pip install uv`).

## First run
```bash
cp .env.example .env
docker compose up -d
cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m careerpilot.cli create-user --email you@example.com
uv run python -m careerpilot.cli seed-prep        # optional: the Prep page also has a Load button
```

Optional: index your notes for search (the first run downloads a ~130 MB model; see [docs/learn/rag.md](docs/learn/rag.md)).
Written answers need an Anthropic API key in `.env` (`ANTHROPIC_API_KEY=...`); without one you still get the matching passages.
```bash
uv run python -m careerpilot.cli ingest
uv run python -m careerpilot.cli eval-rag      # retrieval quality on 45 fixed questions
```

Optional: import jobs from your tracker workbook (safe to repeat; existing jobs are skipped and
columns without a home yet are listed):
```bash
uv run python -m careerpilot.cli import-tracker path/to/Job_Hunt_Tracker.xlsx
```

## Run
The first `npm install` also copies the Python and SQL runtimes into `apps/web/public` (about 30 MB, git-ignored). Run `npm run prepare:runner` to redo that.

Two terminals:
```bash
cd apps/api && uv run uvicorn careerpilot.main:app_factory --factory --reload
```
```bash
cd apps/web && npm install && npm run dev
```
Open http://localhost:3100. The web app forwards `/api` to the backend on port 8000 (set `API_ORIGIN` to use another). Postgres is on host port 5433.

While the API is up it also runs the background worker (daily job-board reads and digest; see the Tasks screen). To run the worker alone: `uv run python -m careerpilot.cli worker`. Set `CAREERPILOT_WORKER_ENABLED=false` to turn it off.

## Checks (what CI runs)
```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports && uv run pytest
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```
Tests use a separate `careerpilot_test` database that they create themselves.

## Claude Desktop / Claude Code (MCP)
`uv run python -m careerpilot.mcp_server` starts the MCP server. Setup and what it can and cannot do: [docs/learn/mcp.md](docs/learn/mcp.md).

## Content
- `content/curriculum.yaml`: the 45-day plan and its 159 topics. Edit it, then run `seed-prep` again (your progress is kept; topic `key`s are the stable ids).
- `content/guides/`: study guides shown in the Prep tab. A link written `[text](practice:two-sum)` opens that problem in the editor.
- `content/eval/`: the golden questions and the quality floors for notes search.
- `content/problems/`: one YAML file per practice problem (see [ADR 0007](docs/adr/0007-practice-runner.md)). Add a file, add a reference solution in `apps/api/tests/problem_solutions.py`, and the content tests check it.
- `content/private/` (git-ignored): guides that describe an employer's systems. They appear in the Prep tab but never enter git.

## After changing the API
```bash
cd apps/api && uv run python -m careerpilot.export_openapi openapi.json
cd ../web && npm run gen:api
```
Commit both generated files; CI fails if they are stale.

## Layout
```
apps/api   FastAPI backend (src/careerpilot: core/, modules/<feature>/, alembic/)
apps/web   Next.js app (src/features/<module>, src/lib/api is the generated client)
content    curriculum and guides (the only copy)
docs/adr   one short file per decision
plan.md    the project plan
```
