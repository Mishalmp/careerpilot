# CareerPilot

Job application tracker, interview prep, an in-browser practice editor, and a place to learn how RAG and MCP are built. Local-first, single user. The full design is in [plan.md](plan.md); decisions are in [docs/adr](docs/adr).

Status: Phase 6. Track jobs, follow the 45-day prep plan, practise 28 problems in an in-browser editor (Python, JavaScript, TypeScript, SQL), ask questions of your own notes with cited answers, and let Claude Desktop or Claude Code use your tracker through an MCP server. Each job page also checks whether the company looks genuine (with quoted evidence), scores the fit against your profile, collects interview intel, and keeps outreach drafts that need your approval (nothing is ever sent for you). A mock interviewer asks and scores questions on a job or topic. Follow companies' public job boards (Greenhouse, Lever, Ashby): new listings wait in an inbox until you add them to the tracker, and a daily digest summarises the day. Insights show your funnel and prep progress, an offer calculator compares offers in rupees, a story bank holds interview stories, and encrypted nightly backups can be restored into a fresh database. Learn how the last two are built in [docs/learn](docs/learn).

**Phase 7 (in progress):** blue design system with light and dark modes, an account-setup wizard, a daily apply list built from job boards and feeds, an Activity page showing every background step and AI cost, Telegram control, and a security pass. What is done and what is not: [docs/phase-7/STATUS.md](docs/phase-7/STATUS.md).

## Run it anywhere
Whole product in containers (API, worker, web, Postgres), or native for development: step-by-step for Windows, macOS and Linux, backups you can carry to another machine, and a new-laptop checklist are in [docs/setup](docs/setup/README.md).

## Quick start on Windows (Command Prompt)
One-time installs: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (start it and wait until it says Running), [Python 3.12](https://www.python.org/downloads/) (tick **Add python.exe to PATH**), [Node 22](https://nodejs.org/), then `python -m pip install uv`.

Open **Command Prompt** (Start menu, type `cmd`) and run:
```bat
cd /d D:\careerpilot
start.bat
```
`start.bat` does everything: starts the database (and the search service), installs what is missing the first time (a few minutes), updates the database schema, opens the API and the web app in two console windows, waits until they answer, and opens http://localhost:3100.

First time only, create your login (it asks for a password of 12+ characters):
```bat
create-user.bat you@example.com
```
then run `start.bat` again (it opens the browser once a user exists).

| Command | What it does |
|---|---|
| `start.bat` | Start everything. Safe to run again: what already runs is left alone. |
| `stop.bat` | Stop the API, the web app and the containers. Your data is kept. |
| `status.bat` | Show what is running and the API's health checks. |
| `create-user.bat you@example.com` | Create your login (once). |
| `reset-password.bat you@example.com` | Set a new password and sign every session out. |

Keep the two console windows (API, Web) open while you use the app; closing one stops that part. Your settings and keys live in `.env` in this folder (never committed): `ANTHROPIC_API_KEY=` for Claude, `TELEGRAM_BOT_TOKEN=` and `CAREERPILOT_TELEGRAM_CHAT_ID=` for Telegram. Restart with `stop.bat` then `start.bat` after changing it.

| If you see | Do |
|---|---|
| "Docker Desktop is not running" | Open Docker Desktop, wait for "Running", run `start.bat` again. |
| "uv ... not recognized" or "The uv tool is missing" | `python -m pip install uv` |
| The web window says port 3100 is in use | Run `stop.bat`, then `start.bat`. |
| Page loads but everything errors | Run `status.bat`: "ready" must show for the API. If not, look at the API window. |
| First start is slow | Normal: the web app compiles pages the first time you open them. |

The same steps by hand, and macOS or Linux, are in the sections below and in [docs/setup](docs/setup/README.md).

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
- `create-user` asks for a password of at least 12 characters. Forgot it? `uv run python -m careerpilot.cli reset-password --email you@example.com` sets a new one and signs every session out (there is no email reset yet).
- After signing in, open **Profile**: account setup asks who you are, what role you want, and reads your CV (PDF, Word, text or paste). Scanned CVs need OCR: `uv sync --extra ocr` (about 100 MB; optional).

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
# Telegram: after creating a bot with @BotFather and setting TELEGRAM_BOT_TOKEN, message your bot, then:
cd apps/api && uv run python -m careerpilot.cli telegram-setup
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
