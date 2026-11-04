# 0004: LLM access behind a provider interface

Status: accepted (2026-11-03), implemented in Phase 4

## Context
Anthropic's pages say subscription login is for ordinary individual use of Claude Code and its native apps, and that software you build should use a Console API key. Whether wrapping `claude -p` in a personal local app counts as personal use is not stated.

## Decision
- One small provider interface (`complete`, `structured`, `stream`) with three implementations: Anthropic API key (default), local `claude -p` (optional, off by default), and a fake for tests.
- Never extract or store subscription OAuth tokens.
- Embeddings run locally (FastEmbed), so no embedding provider key is needed.
- A daily cost cap and an audit table (`llm_calls`) are part of the same layer.

## Consequences
The auth route can change without touching services or prompts.
