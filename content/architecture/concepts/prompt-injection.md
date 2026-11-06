---
id: prompt-injection
title: Prompt injection
level: intermediate
related: [grounding, agents-workflows, ssrf]
appears_in: [core:llm, core:evidence]
proof: [apps/api/tests/test_verification_rules.py, apps/api/tests/test_llm.py]
---


**Idea**: a model cannot reliably tell instructions from data in the same text. Fetched pages, job descriptions, notes and your own answers may contain "ignore previous instructions...". Defences stack: (1) wrap untrusted text as data with clear delimiters and say so in the system prompt; (2) give the model no dangerous tools in the same call; (3) validate output shape; (4) verify claims in code (quotes must appear in the source); (5) human approval before anything enters the knowledge base or leaves the machine; (6) least privilege.

**In this app**: `core/prompts.data_block`, `core/evidence.quote_appears`, outreach has no send action, the research inbox needs approval, MCP writes preview first.

**Fails**: a model "obeys" hidden text and produces a plausible but wrong summary; defence (4) catches fabricated quotes but not a true-but-misleading quote, which is why the owner approves.

**Interview**: "indirect vs direct injection", "why filtering keywords is not a defence".
