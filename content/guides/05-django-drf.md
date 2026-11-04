# Django and Django REST Framework

Days 10 and 11. Your Django experience: Oreqo ERP backend (DRF, PostgreSQL, JWT), Brototype projects (INSIGHIT with Channels and Celery, JUSTWATCHES). Be ready to say exactly what you built.

## Core questions and short model answers

**1. Request lifecycle.** Web server (WSGI or ASGI) to middleware chain, URL resolver, view, response through middleware back out. Middleware runs for every request (security, sessions, auth, CORS). Order matters.

**2. Querysets are lazy.** Building or filtering a queryset does not hit the database; evaluation (iteration, `list()`, `len()`, slicing with step, `bool`) does. Results are cached on the queryset object after evaluation.

**3. The N+1 problem.** Looping over objects and touching a related field issues one query per row. Fix: `select_related` (SQL JOIN, for foreign keys and one-to-one) and `prefetch_related` (a second query joined in Python, for many-to-many and reverse relations). Detect with `django-debug-toolbar`, `connection.queries`, or `assertNumQueries` in tests.

**4. ORM power tools.** `F()` for column-to-column updates done in the database (avoids race conditions), `Q()` for OR and NOT filters, `annotate` and `aggregate`, `Subquery` and `Exists`, `bulk_create` and `bulk_update`, `update()` for set-based writes, `values()` and `values_list()` for lighter rows, `only()` and `defer()`.

**5. Transactions.** `ATOMIC_REQUESTS`, `transaction.atomic()` blocks, `select_for_update()` for row locks, `transaction.on_commit` to run side effects (send email, enqueue Celery task) only after the transaction commits, avoiding tasks that run before data exists.

**6. Migrations.** Generated from model changes; keep them small and reversible; for large tables use the safe sequence (nullable column, backfill in batches, then constraint). Data migrations separate from schema migrations. Never edit applied migrations.

**7. DRF serializers.** Convert between model instances and JSON, and validate input. `ModelSerializer` generates fields; override `validate_<field>` and `validate` for rules; nested writes need explicit `create`/`update`. `SerializerMethodField` is read-only and can hide N+1 queries.

**8. Views.** `APIView` (explicit), generic views (mixins), `ViewSet` plus routers (CRUD with less code). Choose by how custom the behaviour is.

**9. Authentication and permissions.** Authentication identifies the caller (session, token, JWT via SimpleJWT); permissions decide what they may do (`IsAuthenticated`, custom `BasePermission`, object-level `has_object_permission`). Throttling limits request rates per user or IP. Know access and refresh token lifetimes and rotation.

**10. Pagination and filtering.** Page number, limit-offset, and cursor pagination (stable under changes, preferred for feeds). `django-filter` for query parameters. Always bound page sizes.

**11. Signals.** Hooks for model events. They hide control flow and are hard to test; prefer explicit service functions, use signals sparingly (audit, cache invalidation).

**12. Caching.** Per-view, per-fragment or low-level cache with Redis; cache keys including tenant and user where relevant; invalidate on write; beware stale data and stampedes.

**13. Celery with Django.** Tasks for slow or retryable work; pass ids not objects; make tasks **idempotent**; `acks_late` and retries with backoff; avoid long transactions around enqueueing; use `on_commit`. Know the difference between task retry and re-delivery after a worker crash.

**14. Security defaults.** CSRF protection for session auth, `SECURE_*` settings, password hashing, escaping in templates, ORM parameterisation prevents SQL injection (raw SQL needs parameters), `ALLOWED_HOSTS`, CORS configured narrowly, secrets from the environment.

**15. Testing.** `pytest-django` or `TestCase`; factory-style fixtures; test permissions and edge cases; `APIClient` for endpoint tests; `assertNumQueries` for performance regressions.

**16. Django vs FastAPI.** Django: batteries included (ORM, admin, auth, migrations), best for CRUD-heavy apps and teams that want conventions. FastAPI: async-first, typed validation with Pydantic, OpenAPI docs generated, flexible; you assemble the ORM, auth and migrations (SQLAlchemy and Alembic in your project). Pick by team, I/O profile and need for the admin and ecosystem; they can coexist.

## Practice
1. Create an N+1 on purpose, measure queries, fix with `select_related` and `prefetch_related`.
2. A DRF endpoint with a nested serializer, custom permission and cursor pagination.
3. A Celery task that is safe to run twice, with retries.
4. Write a zero-downtime migration plan for adding a non-null column to a 50-million-row table.

## Where it connects
Oreqo ERP APIs (consignments, payroll), JWT auth, PostgreSQL; contrast with the async FastAPI and SQLAlchemy stack at Poumki.

## Common mistakes
Passing ORM objects to Celery; running queries in serializer methods; treating signals as business logic; saying Django is "slow" without measuring.
