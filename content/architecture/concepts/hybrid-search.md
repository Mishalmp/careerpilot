---
id: hybrid-search
title: Hybrid search and reciprocal rank fusion (RRF)
level: intermediate
related: [embeddings, rag-evals]
appears_in: [module:knowledge]
proof: [apps/api/tests/test_knowledge_api.py]
---


**Idea**: keyword search (exact terms, names, error codes) and vector search (meaning) fail differently. Run both, then merge ranked lists. RRF scores each item by `sum(1 / (k + rank))` across lists (k about 60), which needs no score normalisation.

**In this app**: full-text + vector merged by RRF, then a similarity gate refuses weak matches.

**Try it (explorer widget)**: edit two ranked lists and see the fused order.

**Fails**: stop-word and language issues in keyword search; gate threshold set by feel instead of by the eval set.
