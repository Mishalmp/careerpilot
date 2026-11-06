---
id: token-budgets
title: Token budgets, cost and caching
level: beginner
related: [agents-workflows]
appears_in: [core:llm]
proof: [apps/api/tests/test_llm.py]
---


**Idea**: you pay per input/output token; costs differ per model. Control with: smaller inputs (extract main content), cheaper models for easy steps, caps per call/run/day in money not just tokens, and **prompt caching** (reuse a long unchanged prefix at a discount; measure before adopting). Long outputs should stream to avoid timeouts.

**In this app**: daily token cap today; USD caps planned (E08, E09); caching decision E10; research budgets (`03`).

**Fails**: caps that count tokens only; retry storms multiplying cost; no visibility.
