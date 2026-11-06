# Setting up CareerPilot on any computer

Two ways to run it. **Containers** are the same on Windows, macOS and Linux and need no Python or Node. **Native** is faster while you are changing the code. Both use the same `.env` file and the same database.

## What was actually tested (read this first)
| Step | Tested | Where |
|---|---|---|
| Build both images, start API + worker + web + Postgres, migrations, health checks, proxy | yes | Windows 11, Docker Desktop 29.8 |
| Encrypted backup inside the container, restore into a new database, schema and tables present | yes | same |
| SearXNG container returns JSON search results; our adapter parses them | yes | same |
| Native run with `uv` and `npm` (daily use) | yes | Windows 11 |
| macOS, Linux, a cloud server, HTTPS in front of it | **no** (steps below follow the same commands but are untested) | |
Where a step below says "(untested)" it has not been run.

## 1. Containers (recommended for a new machine)
You need: Git, Docker Desktop (Windows/macOS) or Docker Engine with the compose plugin (Linux).
```bash
git clone <your private repository> careerpilot
cd careerpilot
cp .env.example .env            # Windows cmd: copy .env.example .env   (PowerShell: Copy-Item .env.example .env)
```
Edit `.env`: set `POSTGRES_PASSWORD` to a long random value. Optional now, add later: `ANTHROPIC_API_KEY`, search settings, `CAREERPILOT_BACKUP_KEY`.
```bash
docker compose --profile app up -d --build
docker compose --profile app ps                       # api and web should say "healthy"
docker compose exec api python -m careerpilot.cli create-user --email you@example.com
```
Open http://localhost:3100 and sign in. The first build takes several minutes (it downloads Python and Node packages and the in-browser Python/SQL runtimes).

What runs: `postgres` (database), `migrate` (updates the schema, then exits), `api`, `worker` (background tasks), `web`. Stop with `docker compose --profile app stop`; your data stays in the `pgdata` volume. `docker compose --profile app down` removes containers but keeps volumes; adding `-v` deletes your data, so never do that without a backup.

**Different ports** (for example 3100 is taken): put `WEB_PORT=3200`, `API_PORT=8210` and `RUNNER_ORIGINS=http://localhost:3200,http://127.0.0.1:3200` in `.env`, then rebuild: `docker compose --profile app up -d --build`. The web image bakes `RUNNER_ORIGINS` in, so it must be rebuilt when it changes.

**Free web search for the research agent** (optional): `docker compose --profile tools up -d searxng`, then in `.env` set `CAREERPILOT_SEARCH_PROVIDER=searxng` and recreate: `docker compose --profile app up -d`. The research agent also needs `ANTHROPIC_API_KEY`.

**AI key and cost**: a Claude Pro subscription does not include an API key. Make a key in the Anthropic Console, add a small prepaid amount, put it in `.env` as `ANTHROPIC_API_KEY=...`, and set a daily token cap (`CAREERPILOT_LLM_DAILY_TOKEN_CAP`). Check it with `docker compose exec api python -m careerpilot.cli llm-check`. Prices and limits are in `docs/phase-7/01-requirements.md` section 4a.

## 2. Native development
You need: Git, Docker (only for Postgres), Python 3.12, Node 22, and `uv`.
```bash
cp .env.example .env            # then edit POSTGRES_PASSWORD (and keep CAREERPILOT_DATABASE_URL in step with it)
docker compose up -d            # only Postgres (no profile)
cd apps/api
python -m uv sync               # on Windows use "python -m uv" if "uv" is not found
python -m uv run alembic upgrade head
python -m uv run python -m careerpilot.cli create-user --email you@example.com
python -m uv run uvicorn careerpilot.main:app_factory --factory --reload --port 8010
```
In a second terminal:
```bash
cd apps/web
npm install
npm run dev                     # http://localhost:3100
```
Checks you can run any time: `npm run e2e` (browser tests on a throwaway database), `python -m uv run pytest`, `npm test`. See `README.md` for the full list.

## 3. Backups you can carry to another machine
Backups are encrypted files (`.cpbk`). The key is the only way to read them: keep it in a password manager, **never** in the repository or next to the backups.
```bash
docker compose exec api python -m careerpilot.cli backup-key        # prints a key; save it
# put CAREERPILOT_BACKUP_KEY=<the key> in .env, then:
docker compose --profile app up -d                                  # applies the new setting
docker compose exec api python -m careerpilot.cli backup            # writes /app/backups/careerpilot-<time>.cpbk
```
The worker also makes one every night and keeps 14. To copy them out and zip them for your cloud folder (untested command):
```bash
docker compose cp api:/app/backups ./backups-export
# zip the backups-export folder and upload it yourself
```
**Restore on another machine**: bring the stack up as in section 1 (same `CAREERPILOT_BACKUP_KEY` in `.env`), put the file in the container, restore into a **new** database, and switch to it:
```bash
docker compose cp ./backups-export/careerpilot-XXXX.cpbk api:/app/backups/   # untested
docker compose exec api python -m careerpilot.cli restore /app/backups/careerpilot-XXXX.cpbk --into careerpilot_restored
# put CAREERPILOT_DB_NAME=careerpilot_restored in .env, then:
docker compose --profile app up -d
```
Restore never writes into the live database, so a wrong file or key cannot damage your data. The container backup and restore commands (without the copy steps) were tested on 2026-11-06.

## 4. Moving to a new laptop or another OS: checklist
1. Put the code on the new machine (private GitHub repository, then `git clone`).
2. Create `.env` there (never copy it through Git). Use the same `CAREERPILOT_BACKUP_KEY` and your `ANTHROPIC_API_KEY`.
3. Start the stack (section 1) and confirm it is healthy.
4. Restore your latest backup (section 3).
5. Personal files that are not in Git: `content/private/` (your profile and private guides) and `resume-kit/` if you use it. Copy them yourself.
6. Check the Tasks page and `/architecture` > System for the live state.

## 5. Putting it on a server (untested outline)
- Use the same compose file on a Linux server. Do not publish Postgres or the API to the internet; only the web port, and only behind HTTPS (for example Caddy or nginx in front of port 3100).
- Set in `.env`: `CAREERPILOT_COOKIE_SECURE=true`. In `docker-compose.yml` set `CAREERPILOT_ALLOWED_HOSTS` and `CAREERPILOT_ALLOWED_ORIGINS` to your real domain, and `RUNNER_ORIGINS` to `https://your-domain`, then rebuild the web image.
- Add users only through the command line for now; invites and per-user budgets are planned (tasks B21, K09, K10).
- Back up off the server and test a restore before relying on it (section 3).

## 6. Troubleshooting
| Symptom | Fix |
|---|---|
| `uv` is not recognised (Windows) | Use `python -m uv ...` instead |
| Port already in use | Change `WEB_PORT` / `API_PORT` (section 1) |
| Docker cannot pull images ("no such host") | Usually a temporary Docker Desktop DNS problem: retry, or restart Docker Desktop |
| Web shows "The API is not reachable" | `docker compose --profile app ps`; read `docker compose logs api` |
| Sign-in works but actions fail with 403 | The address you opened is not in `CAREERPILOT_ALLOWED_ORIGINS` |
| Backup says the tool version differs | Containers bring pg_dump 16 matching the database; for native runs set `CAREERPILOT_PG_CONTAINER=careerpilot-postgres-1` |
| Practice runner does not load | `RUNNER_ORIGINS` must list the address you use (rebuild web after changing it) |
