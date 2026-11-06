---
id: testing
title: Testing strategy ideas
level: beginner
related: [rag-evals]
appears_in: []
proof: [docs/phase-7/10-test-strategy.md]
---


**Pyramid**: many fast unit tests, fewer integration tests against a real database, a few end-to-end browser tests. **Property tests** state rules ("a checkpoint never repeats a question") and let a tool find counter-examples. **Mutation tests** change the code to see whether tests notice. **Evals** are tests for model behaviour: a labelled set, a metric, a threshold. **AI QA agents** explore the UI like a person and report; they are non-deterministic, so their output is a lead for a human, not a gate. Details in `10-test-strategy.md`.
