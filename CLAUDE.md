# CareerPilot: working rules

**Resuming work? Read [docs/phase-7/STATUS.md](docs/phase-7/STATUS.md) first**, then the task list in `docs/phase-7/07-tasks.md`. Update STATUS.md before ending any session.

Read [plan.md](plan.md) first; decisions live in `docs/adr/`. Commands are in [README.md](README.md). The owner is an intermediate engineer who wants concepts explained: say what concept a change uses and how it can fail (teaching notes: `docs/phase-7/06-concepts-primer.md`).

## Rules (from plan section 1)
1. No abstraction until three real uses, except the interfaces the ADRs name.
2. One source of truth: schema in Alembic, API types generated from OpenAPI, content only under `content/`, prompts only under `prompts/`.
3. No copies of files or code. Delete before adding; each phase ends with a deletion pass.
4. Every new dependency needs a one-line reason and a removal path.
5. Do the real thing where a real case exists (security, idempotency, cost caps) and say why in the PR.

## Layout conventions
- A feature is `apps/api/src/careerpilot/modules/<name>/` with `models`, `schemas`, `repository`, `service`, `router` (plus `dependencies` if it exposes any). Routers hold no business logic; SQL lives only in repositories; services own the transaction (`commit`).
- Protected routes must depend on `Authenticated` (it also enforces CSRF). Never add a route that reads a session cookie by hand.
- New table: add the model, import it in `careerpilot/models.py`, write a migration, run the drift test.
- New module: add it to the `containers` list in the import-linter contract in `apps/api/pyproject.toml`, and add the "keeps its internals private" contract for it. Other modules may import its `service`, `schemas` and `dependencies` only.
- Every query is scoped by `owner_id`; add a cross-owner test for each new resource (see `other_api` in `tests/conftest.py`).
- Links shown in the UI must be validated as http(s) in the schema (`Url` in `modules/tracker/schemas.py`).
- Practice problems: tests are language-neutral JSON in `content/problems/<slug>.yaml`; add a reference solution to `tests/problem_solutions.py` and link the problem from a guide with `practice:<slug>`. Learner code only ever runs in the browser workers under their own CSP (ADR 0007); never run it on the server.
- Changing chunking, embeddings, ranking or prompts for notes search: run `careerpilot eval-rag` before and after and keep the numbers in the PR; `CAREERPILOT_RUN_MODEL_TESTS=1 pytest tests/test_rag_eval.py` is the gate.
- MCP tools call services, never repositories. Writes preview until `confirm=true` and are audited. Never add a tool that sends, deletes or changes settings. User-facing tool errors use `ToolError`; other exceptions are hidden from the model.
- All model calls go through `core/llm.call_llm` or `call_llm_json` (daily token cap, audit table). Prompts are files in `prompts/<name>/vN.md`; add a new version instead of editing one that was used. Wrap untrusted text with `core/prompts.data_block`.
- Research code fetches pages only through `core/fetcher.Fetcher` (SSRF guard, blocked sites). Anything a model quotes must pass `core/evidence.quote_appears` against the fetched text before it is stored.
- Verdicts, scores and states are computed by code (`rules.py`, `workflow.py`), never by the model. Outreach has no send action and must not get one; approval guards are in `modules/outreach/service.py`.
- Background work is a `tasks` row with an idempotent key, claimed with SKIP LOCKED, handled in `worker.py`. Handlers raise `TaskFailure` with a message written for the user. A new job source is an adapter in `modules/discovery/adapters.py` (pure parser plus a board address on the provider's own host) and goes through the safe fetcher; never add a source whose terms forbid automation.
- The daily apply list (`modules/apply`) is assisted: pay and interview information are found by rules in levels, each with its source and a quote; it has no model, no submit action and must not get one. The policy is the owner's file `content/private/apply-policy.yaml` (no auto-submit key). Sites that forbid automation are shown as links only.
- Backups are encrypted with a key that lives only in the environment; restore creates a new database and never writes into the live one (`core/backup.py`). Never store the key in the repo or beside the backups. Money: no exchange rate is fetched; rates are typed in with a date.
- Your profile for scoring is `content/private/profile.yaml` (see `content/profile.example.yaml`); skills live once in `content/skills.yaml`.
- Anything that leaves the machine (email, applications) needs explicit user approval; there is no send action.

## Safety
- Never commit `.env`, keys or `resume-kit/` (personal documents; ignored).
- Tests must only touch `careerpilot_test`.
- Do not bulk-automate LinkedIn, Indeed or Glassdoor; see plan sections 6.2 and 9.
- Web: this Next.js version differs from older ones; read `apps/web/node_modules/next/dist/docs/` before changing Next config or routing.
