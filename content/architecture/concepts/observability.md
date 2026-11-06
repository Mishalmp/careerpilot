---
id: observability
title: Observability
level: intermediate
related: []
appears_in: [api]
proof: [apps/api/tests/test_ops.py]
---


**Idea**: logs (what happened), metrics (how much, how fast), traces (where time went), tied together by a request id. Alert on symptoms users feel.

**In this app**: request and task ids in logs (B16), `/system/status` (B01), metrics endpoint (B17).
