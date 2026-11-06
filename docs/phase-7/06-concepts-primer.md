# 06: Concepts primer

The teaching notes now live in the app's content so there is one source of truth (rule 2). Each concept is a file under `content/architecture/concepts/` with the sections Idea, In this app, How it fails, Interview angle, and a front matter block naming the code it appears in and the tests that prove it. The architecture explorer (`/architecture/concepts`) renders them; edit the files, not this page.

| Concept | File |
|---|---|
| Agents vs workflows | `content/architecture/concepts/agents-workflows.md` |
| Backups and restore testing | `content/architecture/concepts/backups.md` |
| Content Security Policy (CSP) | `content/architecture/concepts/csp.md` |
| Embeddings, chunking and vector search | `content/architecture/concepts/embeddings.md` |
| Spaced repetition and FSRS | `content/architecture/concepts/fsrs.md` |
| Grounding, quote verification and hallucination control | `content/architecture/concepts/grounding.md` |
| Hybrid search and reciprocal rank fusion (RRF) | `content/architecture/concepts/hybrid-search.md` |
| Idempotency | `content/architecture/concepts/idempotency.md` |
| MCP (Model Context Protocol) | `content/architecture/concepts/mcp.md` |
| Database migrations (expand/contract) | `content/architecture/concepts/migrations.md` |
| Multi-tenancy | `content/architecture/concepts/multi-tenancy.md` |
| Observability | `content/architecture/concepts/observability.md` |
| Password hashing | `content/architecture/concepts/password-hashing.md` |
| Prompt injection | `content/architecture/concepts/prompt-injection.md` |
| Queues, leases and retries | `content/architecture/concepts/queues.md` |
| RAG and how to evaluate it | `content/architecture/concepts/rag-evals.md` |
| Reading list (checked sources, verify before relying) | `content/architecture/concepts/reading-list.md` |
| Sessions, cookies and CSRF | `content/architecture/concepts/sessions-csrf.md` |
| Server-sent events and progress | `content/architecture/concepts/sse.md` |
| SSRF (server-side request forgery) | `content/architecture/concepts/ssrf.md` |
| How to talk about this project honestly | `content/architecture/concepts/talking-about-this-project.md` |
| Testing strategy ideas | `content/architecture/concepts/testing.md` |
| Token budgets, cost and caching | `content/architecture/concepts/token-budgets.md` |
| Transactions, isolation and locking | `content/architecture/concepts/transactions.md` |

To add a concept: create a file with the same front matter (`id`, `title`, `level`, `related`, `appears_in`, `proof`). A drift test fails if `related`, `appears_in` or `proof` point at something that does not exist.
