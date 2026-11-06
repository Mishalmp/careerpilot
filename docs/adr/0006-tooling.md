# 0006: Tooling choices and deviations from the plan

Status: accepted (2026-11-03)

- **Python tooling:** `uv` (installed with `pip install uv`), `ruff`, `pyright` strict, `pytest`, `import-linter`.
- **Web tooling:** `npm`, not `pnpm`. pnpm is not installed on this machine and the gain is small for one app. Revisit if a second JavaScript package appears.
- **Task runner:** none. `make` is not available on Windows by default, so the README lists the commands. A task runner is added only if the list becomes painful.
- **Ports:** web 3100 (3000 was already in use), API 8010 (8000 is taken by another Docker project on this machine), Postgres 5433.
- **Job queue:** not added in Phase 0. The first background work arrives in Phase 4; spike S3 compares procrastinate with Celery plus Redis then.
- **Worker and MCP entrypoints:** added with their first feature, not before.
- **API types:** `apps/api/openapi.json` is exported from the app and `apps/web/src/lib/api/schema.d.ts` is generated from it. CI regenerates both and fails on any difference.
- **CI:** GitHub Actions on a personal repository. It has not been run yet; the same commands pass locally.
