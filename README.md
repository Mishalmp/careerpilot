# CareerPilot

Job application tracker, interview prep, an in-browser practice editor, and a place to learn how RAG and MCP are built. Local-first, single user. The full design is in [plan.md](plan.md); decisions are in [docs/adr](docs/adr).

Status: Phase 6. Track jobs, follow the 45-day prep plan, practise 28 problems in an in-browser editor (Python, JavaScript, TypeScript, SQL), ask questions of your own notes with cited answers, and let Claude Desktop or Claude Code use your tracker through an MCP server. Each job page also checks whether the company looks genuine (with quoted evidence), scores the fit against your profile, collects interview intel, and keeps outreach drafts that need your approval (nothing is ever sent for you). A mock interviewer asks and scores questions on a job or topic. Follow companies' public job boards (Greenhouse, Lever, Ashby): new listings wait in an inbox until you add them to the tracker, and a daily digest summarises the day. Insights show your funnel and prep progress, an offer calculator compares offers in rupees, a story bank holds interview stories, and encrypted nightly backups can be restored into a fresh database. Learn how the last two are built in [docs/learn](docs/learn).

**Next (Phase 7, planned, not built):** new blue design system with light and dark modes, a learning platform that researches interview topics for each job, an interactive architecture explorer, and a hardening pass. Everything is specified in [docs/phase-7](docs/phase-7/README.md); resume from [docs/phase-7/STATUS.md](docs/phase-7/STATUS.md).

## Run it anywhere
Whole product in containers (API, worker, web, Postgres), or native for development: step-by-step for Windows, macOS and Linux, backups you can carry to another machine, and a new-laptop checklist are in [docs/setup](docs/setup/README.md).

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

**On Windows (cmd or PowerShell):**
- `cp` does not exist there: use `copy .env.example .env`, and only if `.env` is not there yet (it holds your settings).
- If `pip install uv` leaves `uv` "not recognized", the program is installed but its folder is not on your PATH. Put `python -m` in front instead, and use that everywhere below: `python -m uv sync`, `python -m uv run alembic upgrade head`, and so on.
- `create-user` asks for a password of at least 12 characters.

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
cd apps/api && uv run uvicorn careerpilot.main:app_factory --factory --reload --port 8010
```
```bash
cd apps/web && npm install && npm run dev
```
Open http://localhost:3100. The web app forwards `/api` to the backend on port 8010 (set `API_ORIGIN` to use another; 8000 is avoided because other Docker projects often use it). Postgres is on host port 5433.

While the API is up it also runs the background worker (daily job-board reads and digest; see the Tasks screen). To run the worker alone: `uv run python -m careerpilot.cli worker`. Set `CAREERPILOT_WORKER_ENABLED=false` to turn it off.

## Checks (what CI runs)
```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports && uv run pytest
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```
Tests use a separate `careerpilot_test` database that they create themselves.

## Backups
Your data is in one Postgres database. Back it up with a key only you hold:
```bash
cd apps/api
uv run python -m careerpilot.cli backup-key        # prints a key: keep it in a password manager
```
Put it in `.env` as `CAREERPILOT_BACKUP_KEY=...`. If Postgres runs in Docker, also set `CAREERPILOT_PG_CONTAINER=careerpilot-postgres-1` so the right `pg_dump` version is used. Then:
```bash
uv run python -m careerpilot.cli backup                                  # writes backups/careerpilot-<time>.cpbk
uv run python -m careerpilot.cli restore backups/FILE.cpbk --into careerpilot_restored
```
While the app runs, a backup is made every night (14 are kept). Restore always creates a **new** database and never touches the live one; point `CAREERPILOT_DATABASE_URL` at it to use it. Backups are encrypted, but copy `backups/` to another disk or cloud folder yourself: a backup on the same disk does not survive that disk.

## Checking the connection to Claude
Features that use the model need `ANTHROPIC_API_KEY` in `.env`. Without a key everything still works except the model steps. Once you have one, run a small real request to prove the key, model name and JSON handling work:
```bash
cd apps/api && uv run python -m careerpilot.cli llm-check
```
Every model call is capped per day (`CAREERPILOT_LLM_DAILY_TOKEN_CAP`, default 200,000 tokens) and logged in the `llm_calls` table without the prompts. The model calls in this project have only been tested against a scripted stand-in, so treat the first live use as a test.

**What is sent to Claude (only when a key is set, and only when you use that feature):**

| Feature | Sent |
|---|---|
| Ask my notes | your question and up to six matching passages from your notes, **including private notes** |
| Read their pages (company check) | text of the company's own public web pages |
| Score + read the description | the job description (first 12,000 characters) |
| Interview intel | the source text you pasted or fetched, and, for suggestions, the company name and job description |
| Outreach drafts | the job description, the facts you gave, your first name and constraint line, and up to two matching passages from your notes |
| Mock interview | the topic or job description, collected intel facts, your answers, and matching passages from your notes |

Never sent: passwords, the session cookie, your profile file, exchange rates, backups, or the backup key. Check the data-retention terms of your Anthropic plan before using private notes with it; I did not verify them.

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
content    curriculum, guides, problems, skills list (the only copy)
prompts    versioned prompt files, one folder per prompt
backups    encrypted database backups (git-ignored)
docs/adr   one short file per decision
plan.md    the project plan
```
