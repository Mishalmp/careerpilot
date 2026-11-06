---
id: migrations
title: Database migrations (expand/contract)
level: intermediate
related: [transactions]
appears_in: [db]
proof: [apps/api/tests/test_migrations.py]
---


**Idea**: change schema in safe steps so old and new code both work: add nullable column → deploy code that writes both → backfill → switch reads → drop old. Never rename or drop in one step on a live system. Create big indexes concurrently. Test up and down.

**In this app**: Alembic, a drift test comparing models to migrations; migration 0012 once broke `/readyz` by running a function at import time (lesson recorded; H09 prevents repeats).
