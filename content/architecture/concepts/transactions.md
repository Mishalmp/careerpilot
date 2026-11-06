---
id: transactions
title: Transactions, isolation and locking
level: intermediate
related: [idempotency, migrations]
appears_in: [module:tracker, module:learn]
proof: [apps/api/tests/test_tracker_api.py]
---


**Idea**: a transaction groups writes so they all happen or none do. Default isolation in Postgres (read committed) means each statement sees committed data as of its start. Lost updates are prevented by optimistic concurrency (a version column checked in the `UPDATE ... WHERE version = x`) or by `SELECT ... FOR UPDATE`. Deadlocks come from taking locks in different orders; keep transactions short.

**In this app**: services own `commit`; repositories hold SQL; applications have a `version`; the LLM usage row must not be lost when a call fails (H07 audits this). Long work happens outside open transactions.

**Fails**: a transaction held open during a network call; two tabs overwrite each other (we return a conflict); `idle in transaction` sessions block migrations (H08 sets timeouts).

**Interview**: "explain read committed vs repeatable read", "how do you prevent double booking".
