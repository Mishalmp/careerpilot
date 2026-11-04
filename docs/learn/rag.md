# How "Ask my notes" works (RAG, built from scratch)

RAG means **retrieval-augmented generation**: before a language model answers, you look up the passages that matter and give it only those. The model then explains them instead of remembering (or inventing) facts. Here the "library" is your study guides and private notes.

```
 notes (Markdown files)                                   a question
        │                                                      │
  1. chunk ──► passages with heading paths                     │
        │                                                      ▼
  2. embed ──► 384 numbers per passage (local model)    embed the question
        │                                                      │
  3. store ──► Postgres: vector index + full-text index        │
        │                                                      ▼
        └───────────────────────────────►  4. search: nearest by meaning  +  matching words
                                                       │
                                            5. fuse the two rankings (RRF)
                                                       │
                                  6. confident?  no ──► "your notes don't cover this"
                                                       │ yes
                                  7. ask Claude, passages only, must cite [1] [2]
                                                       │
                                  8. check the citations are real ──► answer + sources
```

Each step is a small file you can read in one sitting.

| Step | Code | The idea |
|---|---|---|
| 1 Chunk | `modules/knowledge/chunking.py` | Split by heading so a passage stays on one topic. Keep code blocks and tables whole. A numbered question starts a new passage. |
| 2 Embed | `modules/knowledge/embeddings.py` | A model turns text into a list of numbers so that similar meanings are close together. We use `bge-small-en-v1.5` (384 numbers) on your CPU through FastEmbed. Nothing is sent anywhere. |
| 3 Store | `models.py`, migration `0004` | Postgres with pgvector: an HNSW index for "nearest vectors" and a GIN index for full-text. One database does both. |
| 4 Search | `repository.py`, `service.py: search` | Two searches: by meaning (cosine distance) and by words (`ts_rank_cd`). |
| 5 Fuse | `ranking.py` | Reciprocal rank fusion: each list gives a passage `weight / (60 + rank)`. Only ranks are compared, so the two scoring scales never need converting. |
| 6 Gate | `service.py: search` | If even the best passage is not close in meaning (cosine similarity below 0.6), say so instead of answering. |
| 7 Ask | `prompts.py`, `core/llm.py` | The model sees at most six passages, is told they are quoted data, and must cite them. |
| 8 Check | `service.py: interpret` | An answer with no valid `[n]` citation is withheld. `NOT_IN_NOTES` is honoured. |

## What was measured (not assumed)
`careerpilot eval-rag` runs 45 fixed questions (37 your notes can answer, 8 they cannot) and reports numbers. On 2026-11-05:

| Variant | Right passage in top 5 | Mean reciprocal rank |
|---|---|---|
| Full-text only | 76% | 0.58 |
| Vectors only | 97% | 0.94 |
| Both, equal weight | 97% | 0.84 |
| Both, text weight 0.2 (used) | **100%** | 0.89 |

What this teaches:
- Meaning-based search carries most of the quality on natural questions. Words alone are weak.
- Adding the word search at **full** weight made the ranking *worse*; common words add noise. A small weight rescued the one question the vectors ranked below the cut, at a small cost to ordering. The weight is a setting (`text_weight`) so you can re-measure.
- "Is it in my notes?" is a separate problem from "which passage is best?". Right passages scored 0.62 to 0.88 similarity; unrelated questions scored up to 0.57, so the cut-off is 0.6. One topically close question (Kubernetes ingress, which brushes the system-design notes) still passes retrieval; the model's `NOT_IN_NOTES` rule is the second guard.
- 45 questions is a small sample. Treat the numbers as a regression alarm, not a benchmark.

## Try it
```bash
cd apps/api
uv run python -m careerpilot.cli ingest                       # index the notes (first run downloads the model)
uv run python -m careerpilot.cli search "why does my lambda see the last value"
uv run python -m careerpilot.cli eval-rag --details          # the numbers above
uv run python -m careerpilot.cli eval-rag --mode vector      # compare variants
```
Set `ANTHROPIC_API_KEY` in `.env` to turn on written answers. Without it you still get the passages, which is already useful.

## Things to try next (each is a good exercise)
1. Change `MAX_CHARS` in `chunking.py` and re-run the eval. Does smaller or larger help?
2. Add a re-ranker: fetch 20 candidates, re-score them with a cross-encoder, keep the top 6. Keep it only if the numbers improve.
3. Add your own questions to `content/eval/questions.yaml`, especially ones that failed.
4. Add job descriptions as a second source of documents (`discover()` in `service.py`).

## Limits and risks
- Passages go to Claude when written answers are on. Private notes are included. Turn the key off to keep everything local.
- Retrieval can miss; the answer is only as good as the passages found. The sources shown beside every answer are how you check.
- Changing the embedding model re-indexes everything (the model name is part of each file's hash). A model with a different number of dimensions also needs a migration, because the column size is fixed at 384.
