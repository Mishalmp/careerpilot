# 0002: PostgreSQL with pgvector; UUID keys

Status: accepted (2026-11-03)

## Context
The platform needs relational data, full-text search and vector search. Postgres is already known to the owner.

## Decision
- PostgreSQL 16 with the pgvector extension (Docker image `pgvector/pgvector:pg16`), enabled in the baseline migration.
- The container publishes on host port **5433**, bound to 127.0.0.1, so it does not clash with another local Postgres.
- Primary keys are random UUIDs (`uuid4`). Time-ordered keys were considered; the locality gain does not matter at this scale.
- Timestamps are `timestamptz`, stored in UTC.
- Constraint and index names follow one naming convention (`core/db.py`), so migrations are deterministic.
- A drift test fails when the models and the migrations disagree.

## Consequences
- One store to back up and reason about.
- A separate vector database is only worth adding if measurements show a need.
