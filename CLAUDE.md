# CareerPilot: working rules

Read [plan.md](plan.md) first; decisions live in `docs/adr/`. Commands are in [README.md](README.md).

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
- Anything that leaves the machine (email, applications) needs explicit user approval; there is no send action.

## Safety
- Never commit `.env`, keys or `resume-kit/` (personal documents; ignored).
- Tests must only touch `careerpilot_test`.
- Do not bulk-automate LinkedIn, Indeed or Glassdoor; see plan sections 6.2 and 9.
- Web: this Next.js version differs from older ones; read `apps/web/node_modules/next/dist/docs/` before changing Next config or routing.
