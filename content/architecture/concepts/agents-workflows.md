---
id: agents-workflows
title: Agents vs workflows
level: intermediate
related: [prompt-injection, token-budgets]
appears_in: [module:mock, module:discovery]
proof: [apps/api/tests/test_mock_api.py]
---


**Idea** (Anthropic's guidance): a **workflow** is code-controlled steps with model calls inside (chaining, routing, parallel, orchestrator-workers, evaluator-optimizer); an **agent** lets the model choose steps and tools in a loop. Use the simplest thing that works; agents cost more, are harder to test and can wander.

**In this app**: the research run is a workflow (fixed stages, budgets); mock interviews are a turn loop with code deciding when to stop; QA agents (T13, T14) are real agents, kept outside production and reviewed by a human.

**Fails**: unbounded loops, no budget, no stop condition, trusting agent output without verification.
