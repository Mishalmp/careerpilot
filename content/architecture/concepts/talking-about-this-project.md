---
id: talking-about-this-project
title: How to talk about this project honestly
level: beginner
related: []
appears_in: []
proof: [docs/phase-7/09-product-spec.md]
---

Claim only what the repository proves: for example "a Postgres-backed queue with SKIP LOCKED, idempotent keys and a watchdog, tested with crash drills" (after T11), not "scales to millions". Say what you chose not to do (no Celery/Redis, why) and what you would change at larger scale (stage table in `09`). W05 turns this into a reviewed list.
