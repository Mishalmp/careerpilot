# FastAPI, Async Backend, API Design and Security

Days 8, 9, 12, 34. Your stack at Poumki: FastAPI, Pydantic 2, async SQLAlchemy 2 with asyncpg, Alembic, Redis, Celery, JWT, RBAC, Stripe webhooks.

## FastAPI and async

**1. ASGI vs WSGI.** WSGI is synchronous request-response. ASGI supports async, WebSockets and long-lived connections. FastAPI is built on Starlette (ASGI) and runs under uvicorn.

**2. `def` vs `async def` endpoints.** `async def` runs on the event loop; blocking code inside it stalls all requests. Plain `def` endpoints run in a thread pool, so blocking libraries are safe there. Use `async def` only with async-capable calls (async DB driver, httpx).

**3. Pydantic v2.** Typed models validate and coerce request bodies, query parameters and responses, generate OpenAPI schemas, and serialise with `response_model`. Know `Field` constraints, validators, `model_dump`, and `from_attributes` for ORM objects.

**4. Dependency injection.** `Depends()` composes reusable pieces: DB session, current user, permission checks, settings. Dependencies with `yield` give setup and teardown (a session per request, closed afterwards). Overrides make testing easy (`app.dependency_overrides`).

**5. Async SQLAlchemy.** One `AsyncSession` per request, never shared across tasks; use `async with` and commit or roll back deliberately; eager-load relationships because lazy loading does not work in async contexts (`selectinload`, `joinedload`). A connection pool bounds concurrency; size it against database limits and number of workers.

**6. Background work: which tool?** FastAPI `BackgroundTasks`: small, same-process, lost if the process dies. Celery (or another queue): durable, retried, scaled separately, for long or critical work. Orchestrator (Kestra or Airflow): scheduled multi-step workflows with visibility. Pattern at Elphi: accept with HTTP 202, process asynchronously, deliver a completion callback.

**7. Middleware, request IDs, logging.** A request-ID middleware ties logs across services; structured JSON logs; exception handlers return a consistent error body; health endpoints (liveness and readiness) for the load balancer.

**8. Lifespan and settings.** Create shared resources (engines, HTTP clients, Redis) on startup and dispose on shutdown; read configuration from the environment with `pydantic-settings`.

**9. Testing.** `TestClient` or `httpx.AsyncClient`, dependency overrides for DB and auth, factory fixtures, async tests with `pytest-asyncio` or `anyio`; separate unit tests from a few integration tests against a real database container.

**10. Performance and pitfalls.** Many workers vs one async worker (CPU-bound code needs processes), connection pool exhaustion, N+1 in async code, large response serialisation, blocking calls hidden in libraries, missing timeouts on outbound HTTP calls.

## API design

**11. REST basics.** Resources as nouns, HTTP verbs for actions, correct status codes (200, 201, 202, 204, 400, 401, 403, 404, 409, 422, 429, 5xx), consistent error format, versioning (`/v1`) and backward compatibility.

**12. Idempotency.** GET, PUT and DELETE are idempotent by definition; make POST safe to retry with an idempotency key stored with the result. Essential for payments, webhooks and any client that retries.

**13. Pagination, filtering, sorting.** Cursor (keyset) pagination for large changing data; explicit allowed sort fields; bound page sizes.

**14. Async APIs.** Long tasks return 202 plus a status URL or a callback; polling and callbacks need retries and a defined terminal state.

**15. Contracts between services.** Document request and response shapes, auth, error codes and retry rules in one place. Version them. Treat it as the only agreement between teams.

## Security

**16. AuthN vs AuthZ.** Authentication proves identity; authorisation decides access. Check authorisation on **every** request and object, not only at the UI.

**17. Sessions vs JWT.** Sessions: server-side state, easy revocation. JWT: stateless, signed claims, hard to revoke before expiry, so use short access tokens with refresh tokens, rotation and a revocation list when needed. Store tokens carefully (HTTP-only cookies resist XSS theft). Verify signature, expiry, audience and algorithm; never trust an unsigned token.

**18. OAuth2 and OIDC.** OAuth2 delegates authorisation (authorisation code flow with PKCE for apps); OIDC adds identity on top. Know what the access token, ID token and refresh token are for.

**19. OWASP Top 10, with fixes.** Broken access control (check ownership and roles server-side); cryptographic failures (TLS, strong hashing such as bcrypt or argon2, KMS); injection (parameterised queries); insecure design; misconfiguration; vulnerable dependencies (pin and scan); auth failures (rate limit, MFA); integrity failures (verify webhooks, signed artefacts); logging failures; SSRF (allow-list outbound targets).

**20. Webhooks.** Verify the provider signature on the raw body, check timestamps to stop replay, respond fast, make handlers idempotent by event id, store before processing (Stripe style).

**21. Secrets and encryption.** Never commit secrets; use environment variables or a secrets manager; rotate; encrypt sensitive fields; envelope encryption with KMS (your tenant database credentials). Principle of least privilege for IAM roles.

**22. Multi-tenant leakage.** Tenant resolved from the authenticated identity, never from a client-supplied field; every query scoped by tenant or physically isolated by database; tests that try to read another tenant's data; per-tenant rate limits.

**23. Rate limiting and abuse protection.** Token bucket or sliding window per user, IP and tenant, enforced at the edge and in the app; return 429 with `Retry-After`.

## Practice
1. Build a small FastAPI service: JWT login, a protected resource, async SQLAlchemy, tests with overridden dependencies.
2. Add an idempotency-key mechanism to a POST endpoint.
3. Implement and test webhook signature verification.
4. Write an OWASP checklist for one of your services and find three issues.

## Common mistakes
Blocking calls in `async def`; sharing one DB session across requests; storing JWTs in localStorage without discussing the XSS risk; claiming "we use JWT so it is secure"; no timeouts on outbound calls.
