# 0001: Modular monolith

Status: accepted (2026-11-03)

## Context
One developer, one machine, a fixed time window. The plan lists many features (tracker, prep, practice, RAG, MCP, research agents) that share data.

## Decision
One Python package (`careerpilot`) with feature modules under `modules/`, each laid out as `models`, `schemas`, `repository`, `service`, `router`. A worker and an MCP entrypoint reuse the same services later. `core/` holds shared infrastructure and never imports from `modules/`.

The layer order inside a module (router, dependencies, service, repository) and the `core` rule are enforced by import-linter in CI. Rules between modules are added when a second module exists.

## Consequences
- One deployable, one database, no network contracts between parts.
- Splitting a module out later is possible because it only talks to others through service functions.
- Discipline is enforced by tooling, not goodwill.
