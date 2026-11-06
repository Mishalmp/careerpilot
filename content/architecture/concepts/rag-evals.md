---
id: rag-evals
title: RAG and how to evaluate it
level: intermediate
related: [hybrid-search, grounding]
appears_in: [module:knowledge]
proof: [apps/api/tests/test_rag_eval.py]
---


**Idea**: retrieval-augmented generation: retrieve passages, put them in the prompt, ask the model to answer only from them and cite. Quality has two parts: **retrieval** (did the right passage come back? recall@k, MRR) and **generation** (is the answer faithful to the passages, does it refuse when the answer is not there?). Evaluate them separately with a labelled question set including unanswerable questions.

**In this app**: `careerpilot eval-rag`, a gate test, and the rule to record numbers before and after any change to chunking, embeddings, ranking or prompts. Answers with invalid citations are withheld.

**Fails**: tiny eval sets (noise), tuning to the test set, citation that points to a passage that does not support the claim (faithfulness check, H14).

**Interview**: "how would you know your RAG got better".
