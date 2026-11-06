---
id: embeddings
title: Embeddings, chunking and vector search
level: intermediate
related: [hybrid-search, rag-evals]
appears_in: [module:knowledge]
proof: [apps/api/tests/test_chunking.py, apps/api/tests/test_knowledge_api.py]
---


**Idea**: an embedding model turns text into a vector; similar meaning gives nearby vectors. To search long notes you split them into chunks (size and overlap are trade-offs: small chunks are precise but lose context, big ones blur). Nearest-neighbour search finds the closest chunks; an index (HNSW in pgvector) makes it fast with approximate results.

**In this app**: notes are chunked and embedded locally; chunks live in Postgres with pgvector; `embedding_version` (H12) prevents mixing models.

**Fails**: changing the model without re-embedding; chunks that cut a sentence in half; filter-after-search returning too few rows for one owner (H16 checks pgvector's iterative scan).
