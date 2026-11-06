---
id: idempotency
title: Idempotency
level: intermediate
related: [queues, transactions]
appears_in: [module:learn, module:tasks]
proof: [apps/api/tests/test_learn_api.py, apps/api/tests/test_tasks_worker.py]
---


**Idea**: doing an operation twice has the same effect as once. Needed because networks retry. Techniques: natural unique keys, an `Idempotency-Key` header stored with the first response, upserts, and "check state then act" inside a transaction.

**In this app**: task keys, discovery unique constraints, `Idempotency-Key` on creates (B13), quiz answer tokens (L17), checkpoint submit-once (L19).

**Fails**: dedupe only in application code (race between two requests), keys that are not scoped by owner, reusing a key with a different body (should be rejected).

**Interview**: "design an idempotent payment API".
