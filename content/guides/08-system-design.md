# System Design

Days 22 to 28 (and 3, 5, 25, 26 for your own project). Practice on paper with a 45-minute timer and speak throughout.

## The framework (use it every time)

1. **Clarify requirements** (2 to 5 minutes). Functional: what must it do? Non-functional: scale, latency, availability, consistency, cost, compliance. Out of scope: say what you are skipping.
2. **Estimate** (3 minutes). Users, requests per second (peak is roughly 2 to 5 times average), data size per item, storage per year, read to write ratio, bandwidth. Round numbers, show your arithmetic.
3. **API and data model** (5 minutes). Main endpoints, entities, keys, access patterns that drive the storage choice.
4. **High-level design** (10 minutes). Clients, edge (CDN, load balancer), services, datastores, caches, queues. Draw the main flows.
5. **Deep dives** (15 minutes). The two or three hardest parts: bottleneck, consistency, failure handling.
6. **Trade-offs and failure modes** (5 minutes). What breaks, how you detect it, how you recover; what you would change at 10x.

Say "I assume X; tell me if wrong" instead of waiting for permission.

## Building blocks to know cold

| Block | Know |
|---|---|
| Load balancer | L4 vs L7, health checks, algorithms (round robin, least connections), sticky sessions and why to avoid them |
| Cache | Cache-aside, write-through, write-behind; TTL, eviction (LRU); invalidation is the hard part; stampede and hot-key protection; local vs distributed (Redis) |
| CDN | Static and cacheable content at the edge, cache keys, purge |
| Database | Relational vs document vs key-value vs columnar; indexes; replication (leader-follower, lag, failover); sharding (key choice, hot shards, resharding); CAP and PACELC in plain words |
| Queues and streams | Decouple and smooth spikes; at-least-once delivery means consumers must be idempotent; ordering per key; dead-letter queues; backpressure |
| Object storage | Large blobs, presigned URLs, lifecycle, eventual patterns |
| Search | Inverted index; when to use a search engine vs database `LIKE` |
| Observability | Logs, metrics, traces, SLOs, alerting on symptoms not causes |
| Reliability | Timeouts everywhere, retries with exponential backoff and jitter, circuit breakers, bulkheads, graceful degradation, idempotency keys |

## Worked designs (practise each, then do your own variants)

**A. URL shortener.** Requirements: create short link, redirect, optional expiry, analytics. Estimate: 100 million links per year, 10:1 read to write. Key generation: counter plus base62 (needs coordination), random with collision check, or pre-generated ranges per node. Store key to URL in a key-value or relational table (indexed on key); cache hot keys in Redis; redirect with 301 vs 302 (302 lets you count clicks). Deep dive: unique key at scale, analytics via a queue and a columnar store, abuse protection.

**B. Rate limiter.** Algorithms: fixed window (burst at edges), sliding window log (accurate, memory heavy), sliding window counter (compromise), token bucket (allows bursts, common). Implement in Redis with atomic Lua or `INCR` plus expiry; limits per user, IP and tenant; return 429 with `Retry-After`; decide fail-open or fail-closed if Redis is down; distributed clocks and race conditions.

**C. Notification or job scheduler with retries.** Producers enqueue; workers pull; scheduled jobs in a time-ordered store; at-least-once with idempotent handlers; retries with exponential backoff, jitter and a cap; dead-letter queue and replay tooling; visibility timeouts; priority queues; per-tenant fairness; monitoring queue depth and age. Link to your Celery and callback design and its limits.

**D. Multi-tenant SaaS (your Elphi).** Tenancy models: shared schema with tenant id (cheapest, risk of leakage), schema per tenant, **database per tenant** (strong isolation, per-tenant backup and restore, noisy-neighbour protection; cost: many databases and migrations to run across all, connection management). Control plane (accounts, plans, billing, tenant registry) separate from tenant plane. Provisioning automation, encrypted credentials, tenant routing by identity, per-tenant migrations with a runner and failure handling, per-tenant storage prefixes, quotas and limits, onboarding and offboarding (export and delete). Deep dive: migrations across 1,000 tenants, connection pooling per tenant database, cross-tenant analytics.

**E. Data ingestion and analytics pipeline.** Sources (APIs, file uploads), ingestion service with rate-limit handling and retries, raw immutable storage, transformation jobs, curated tables, serving layer (API and dashboards), orchestration, data quality, lineage, backfills, cost control. Cover late data, schema drift, idempotency, per-tenant isolation.

**F. File upload and processing service.** Presigned upload to object storage, event to a queue, validation worker, status tracking with progress, large-file multipart, virus scan, retries and idempotency, user-visible status (polling or server-sent events).

**G. Chat or feed.** Fan-out on write vs on read vs hybrid (celebrity problem), WebSockets or SSE, message ordering and storage, presence, push notifications, read receipts. Know trade-offs, not every detail.

**H. Payments or billing flow.** Idempotency keys, webhooks with signature checks, a ledger model, reconciliation jobs, eventual consistency between the payment provider and your records.

## Distributed systems concepts to explain in one minute each
CAP and consistency models (strong, eventual, read-your-writes); two-phase commit vs **saga** (compensating actions) vs **outbox pattern** (write the event in the same transaction, publish afterwards); idempotent consumers; exactly-once is "at-least-once plus idempotency" in practice; leader election; consistent hashing; quorum reads and writes; clock issues.

## Common mistakes
Jumping to boxes without requirements; no numbers; naming technologies without reasons; ignoring failure modes; claiming a database "scales infinitely"; silence while thinking; over-engineering for a first version (start simple, show the path to scale).

## Self-check after each practice
Did I state requirements? Did I estimate? Did I name the bottleneck? Did I explain one trade-off per component? Did I describe a failure and recovery? Did I keep to time?

## Practise in the editor

Solve these in the browser editor; your code runs in a sandbox and is checked against hidden tests.

- [Sliding-window rate limiter](practice:rate-limit-decisions)
- [Exponential backoff schedule](practice:backoff-schedule)
- [Latest record per key](practice:latest-per-key)
