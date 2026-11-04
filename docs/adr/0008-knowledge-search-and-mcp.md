# 0008: Notes search, AI answers and the MCP server

Status: accepted (2026-11-05). Teaching versions: [RAG](../learn/rag.md), [MCP](../learn/mcp.md).

## Search
- **Local embeddings.** `BAAI/bge-small-en-v1.5` via FastEmbed (ONNX, CPU), 384 dimensions, cached in `.cache/fastembed` (git-ignored). FastEmbed's default build of this model is a quantised ONNX file published by Qdrant on Hugging Face; the first use downloads it (about 130 MB). No note text is sent to an embedding service.
- **One database.** pgvector HNSW (cosine) plus Postgres full-text in the same table. Vectors are filtered by owner after the index lookup; fine for one user, and the reason to set `hnsw.iterative_scan` if this ever becomes multi-user with large data.
- **Fusion with a lower weight for words.** Measured, not assumed: equal-weight fusion ranked worse than vectors alone on 45 questions; weight 0.2 gave the best recall (see the learning note for the table). The weight and the "is it covered?" threshold (0.6) are settings, chosen from `careerpilot eval-rag`.
- **A quality gate.** `content/eval/questions.yaml` + `baseline.json`; `tests/test_rag_eval.py` fails when quality drops below the floors. It runs only with `CAREERPILOT_RUN_MODEL_TESTS=1` because it needs the real model; the questions themselves are validated on every run.
- **Test stand-in.** A hashing embedder lets the other tests run offline. It is not a quality embedder, and the tests use a lower similarity threshold for it.

## AI answers
- The official `anthropic` SDK, default model `claude-sonnet-5-5` (setting `llm_model`), effort `low`. No key means retrieval-only answers; the feature still works.
- Everything goes through `core/llm.py`: a **daily token cap** (default 200,000, setting `llm_daily_token_cap`) and an `llm_calls` table (tokens, latency, status; never prompts or answers).
- **Answers must cite.** The model gets at most six passages, told they are quoted data. An answer with no valid `[n]` is withheld; `NOT_IN_NOTES` is honoured; a refusal is reported as such. The question never reaches the model when the best passage is below the similarity threshold.
- Passages (including private notes) are sent to Anthropic when a key is set. Check the data-retention terms of your plan before relying on it for anything sensitive; I did not verify them.
- Not built: the optional `claude -p` provider from ADR 0004, and refusal fallbacks. Add them when there is a need.

## MCP server
- Official SDK v2 (`mcp` 2.x), stdio transport, tools call the existing services. Writes preview until `confirm=true` and are audited in `audit_events`.
- **No send, delete or settings tools**, ever; this is the safety property that does not depend on the model behaving.
- Verified three ways: in-memory client tests of every tool, the real server launched over stdio, and the tool list asserted to contain no dangerous verbs. Not yet exercised against a live Claude Desktop; the config is in the learning note.
- HTTP transport is deferred until it can be done safely (token, Origin check, TLS).
