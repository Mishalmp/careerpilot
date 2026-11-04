# CareerPilot

Job application tracker, interview prep, an in-browser practice editor, and a place to learn how RAG and MCP are built. Local-first, single user. The full design is in [plan.md](plan.md); decisions are in [docs/adr](docs/adr).

Status: Phase 1. Sign in, track jobs (table and board, status history, contacts, CSV export), and follow the 45-day prep plan with topics, study sessions and guides. Practice editor, RAG and MCP come in later phases.

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

Optional: import jobs from your tracker workbook (safe to repeat; existing jobs are skipped and
columns without a home yet are listed):
```bash
uv run python -m careerpilot.cli import-tracker path/to/Job_Hunt_Tracker.xlsx
```

## Run
Two terminals:
```bash
cd apps/api && uv run uvicorn careerpilot.main:app_factory --factory --reload
```
```bash
cd apps/web && npm install && npm run dev
```
Open http://localhost:3100. The web app forwards `/api` to the backend on port 8000. Postgres is on host port 5433.

## Checks (what CI runs)
```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports && uv run pytest
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```
Tests use a separate `careerpilot_test` database that they create themselves.

## Content
- `content/curriculum.yaml`: the 45-day plan and its 159 topics. Edit it, then run `seed-prep` again (your progress is kept; topic `key`s are the stable ids).
- `content/guides/`: study guides shown in the Prep tab.
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
