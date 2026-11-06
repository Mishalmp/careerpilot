---
id: grounding
title: Grounding, quote verification and hallucination control
level: intermediate
related: [prompt-injection, rag-evals]
appears_in: [core:evidence]
proof: [apps/api/tests/test_verification_rules.py]
---


**Idea**: models can state false things fluently. Make claims checkable: require the supporting quote, then check in code that the quote occurs in the source text (after normalising whitespace/quotes) and that it fits the claim. A second, independent call that does not see the answer key can test MCQ keys ("blind answer"). Label what could not be verified.

**In this app**: `core/evidence.quote_appears`; question statuses `verified` / `unverified` (`03`).

**Fails**: quote exists but does not support the claim (needs the fit check and human approval); source itself is wrong (reliability score, owner review).
