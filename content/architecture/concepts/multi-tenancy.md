---
id: multi-tenancy
title: Multi-tenancy
level: intermediate
related: [sessions-csrf]
appears_in: [module:auth]
proof: [apps/api/tests/test_security.py]
---


**Idea**: many users share one deployment; isolation is enforced in every query (`owner_id`), tested for every resource, and extended to caches, files, background tasks, rate limits and costs. Row-level security in Postgres is a stronger option for later.

**In this app**: rule "every query scoped by owner_id" plus a cross-owner test per resource.

**Fails**: a join that forgets the filter; a cache keyed without the owner; an admin tool that bypasses scoping.
