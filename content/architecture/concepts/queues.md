---
id: queues
title: Queues, leases and retries
level: intermediate
related: [idempotency, sse]
appears_in: [module:tasks]
proof: [apps/api/tests/test_tasks_worker.py]
---


**Idea**: a queue decouples "ask for work" from "do work". A worker claims a task with a lease (a time-limited claim) and must finish or renew it; if it dies, the lease expires and another worker takes over, so handlers must be idempotent. Retries use exponential backoff with jitter (random spread) to avoid thundering herds. Tasks that always fail go to a dead-letter state for a human.

**In this app**: the `tasks` table with `FOR UPDATE SKIP LOCKED` (each worker locks different rows without waiting), unique keys, backoff, watchdog; `worker.py` handlers raise `TaskFailure` with a user-readable message.

**Postgres queue vs Celery/Redis**: see `05` section 2. The key point is the **dual-write problem**: with an external broker you commit a database row and publish a message in two steps; a crash between them loses or duplicates work (the fix is an outbox table, which is a Postgres queue anyway). With the queue in the same database, enqueue is part of the same transaction.

**Fails**: non-idempotent handlers; leases shorter than the work; one slow kind starving others (per-kind limits, H02); clock-based leases using worker time (use DB time).

**Interview**: "at-least-once vs exactly-once delivery", "how do you handle poison messages".
