import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.llm import LlmClient, call_llm
from careerpilot.core.prompts import load_prompt
from careerpilot.modules.knowledge import prompts, repository
from careerpilot.modules.knowledge.chunking import chunk_markdown
from careerpilot.modules.knowledge.embeddings import Embedder
from careerpilot.modules.knowledge.models import DocumentKind
from careerpilot.modules.knowledge.ranking import or_query, reciprocal_rank_fusion
from careerpilot.modules.knowledge.schemas import (
    AskOut,
    CitationOut,
    HitOut,
    IngestOut,
    SearchOut,
    StatusOut,
)

CANDIDATES = 20  # how many results each search contributes before they are fused
ANSWER_PASSAGES = 6  # how many passages the model sees
EMBED_BATCH = 32

_CITATION = re.compile(r"\[(\d+)\]")


# ---- ingest ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    source_path: str
    name: str
    kind: DocumentKind
    text: str


def discover(content_dir: Path) -> list[SourceFile]:
    """Markdown files that make up your notes: committed guides, then git-ignored private notes."""
    found: list[SourceFile] = []
    for folder, kind in (("guides", DocumentKind.GUIDE), ("private", DocumentKind.PRIVATE)):
        directory = content_dir / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            found.append(
                SourceFile(
                    f"{folder}/{path.name}", path.stem, kind, path.read_text(encoding="utf-8")
                )
            )
    return found


def _title(source: SourceFile) -> str:
    for line in source.text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return source.name


def _hash(text: str, embedder: Embedder) -> str:
    # The model name is part of the hash: switching models re-indexes every file.
    return hashlib.sha256(f"{embedder.name}\n{text}".encode()).hexdigest()


async def _embed(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors += await to_thread.run_sync(
            embedder.embed_passages, texts[start : start + EMBED_BATCH]
        )
    return vectors


async def ingest(
    db: AsyncSession, owner_id: uuid.UUID, content_dir: Path, embedder: Embedder
) -> IngestOut:
    """Bring the index in line with the files. Only changed files are re-embedded; repeatable."""
    existing = await repository.documents_by_path(db, owner_id)
    sources = discover(content_dir)
    counts = {"added": 0, "updated": 0, "unchanged": 0}

    for source in sources:
        digest = _hash(source.text, embedder)
        current = existing.get(source.source_path)
        if current is not None and current.content_hash == digest:
            counts["unchanged"] += 1
            continue
        raw = chunk_markdown(source.text)
        # The heading path is embedded too, so "Python > Core questions" helps retrieval.
        vectors = await _embed(embedder, [f"{c.heading_path}\n{c.text}".strip() for c in raw])
        await repository.replace_document(
            db,
            owner_id,
            current,
            {
                "source_path": source.source_path,
                "name": source.name,
                "title": _title(source),
                "kind": source.kind,
                "content_hash": digest,
                "embedding_model": embedder.name,
            },
            [
                {"ordinal": i, "heading_path": c.heading_path, "text": c.text, "embedding": v}
                for i, (c, v) in enumerate(zip(raw, vectors, strict=True))
            ],
        )
        counts["updated" if current else "added"] += 1

    present = {s.source_path for s in sources}
    stale = [path for path in existing if path not in present]
    await repository.delete_documents(db, owner_id, stale)
    await db.commit()
    _, chunk_total, _ = await repository.index_status(db, owner_id)
    return IngestOut(**counts, removed=len(stale), chunks=chunk_total)


async def status(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, ai_enabled: bool
) -> StatusOut:
    documents, chunks, indexed_at = await repository.index_status(db, owner_id)
    return StatusOut(
        documents=documents,
        chunks=chunks,
        indexed_at=indexed_at,
        embedding_model=settings.embedding_model
        if settings.embedder == "fastembed"
        else "hash-384",
        ai_enabled=ai_enabled,
    )


# ---- search ---------------------------------------------------------------------------------


async def search(
    db: AsyncSession,
    owner_id: uuid.UUID,
    embedder: Embedder,
    settings: Settings,
    query: str,
    limit: int = 8,
    *,
    mode: Literal["hybrid", "vector", "text"] = "hybrid",
) -> SearchOut:
    """Hybrid search: meaning (vectors) and exact words (full-text), merged by rank.

    `mode` exists so the evaluation can compare each half with the combination.
    """
    by_meaning: list[tuple[uuid.UUID, float]] = []
    by_words: list[tuple[uuid.UUID, float]] = []
    if mode != "text":
        query_vector = await to_thread.run_sync(embedder.embed_query, query)
        await repository.set_search_quality(db)
        by_meaning = await repository.vector_search(db, owner_id, query_vector, CANDIDATES)
    if mode != "vector":
        by_words = await repository.text_search(db, owner_id, or_query(query), CANDIDATES)

    similarity = {chunk_id: 1.0 - distance for chunk_id, distance in by_meaning}
    fused = reciprocal_rank_fusion(
        [[c for c, _ in by_meaning], [c for c, _ in by_words]], weights=(1.0, settings.text_weight)
    )[:limit]
    rows = await repository.chunks_with_documents(db, owner_id, [c for c, _ in fused])

    hits: list[HitOut] = []
    for chunk_id, score in fused:
        chunk, document = rows[chunk_id]
        hits.append(
            HitOut(
                chunk_id=chunk.id,
                document_name=document.name,
                document_title=document.title,
                kind=document.kind,
                heading_path=chunk.heading_path,
                text=chunk.text,
                score=round(score, 5),
                similarity=round(similarity[chunk_id], 4) if chunk_id in similarity else None,
            )
        )
    best = max(similarity.values(), default=None)
    # Words alone can match by accident ("index"), so only meaning decides if the notes cover it.
    return SearchOut(
        hits=hits,
        confident=best is not None and best >= settings.min_similarity,
        best_similarity=best,
    )


# ---- ask ------------------------------------------------------------------------------------


def _label(hit: HitOut) -> str:
    return hit.heading_path or hit.document_title


async def ask(
    db: AsyncSession,
    owner_id: uuid.UUID,
    embedder: Embedder,
    llm: LlmClient | None,
    settings: Settings,
    question: str,
) -> AskOut:
    """Answer from the notes only, citing passages. Never answers when the notes do not cover it."""
    found = await search(db, owner_id, embedder, settings, question)
    if not found.confident:
        return AskOut(mode="not_in_notes", answer=None, citations=[], hits=found.hits)
    if llm is None:
        return AskOut(mode="retrieval_only", answer=None, citations=[], hits=found.hits)

    passages = found.hits[:ANSWER_PASSAGES]
    prompt = load_prompt(settings.prompts_dir, "ask-notes")
    reply = await call_llm(
        db,
        owner_id,
        llm,
        settings,
        purpose=prompt.label,
        system=prompt.system,
        user=prompts.user_message(question, [(_label(h), h.text) for h in passages]),
        max_tokens=prompt.max_tokens,
    )
    return interpret(reply.text, reply.refused, passages, found.hits)


def interpret(text: str, refused: bool, passages: list[HitOut], hits: list[HitOut]) -> AskOut:
    """Turn the model's reply into a result, trusting only answers that cite real passages."""
    answer = text.strip()
    if refused:
        return AskOut(mode="refused", answer=None, citations=[], hits=hits)
    if not answer or prompts.NOT_IN_NOTES in answer:
        return AskOut(mode="not_in_notes", answer=None, citations=[], hits=hits)
    cited = sorted({int(n) for n in _CITATION.findall(answer) if 1 <= int(n) <= len(passages)})
    if not cited:
        # An answer that cites nothing cannot be checked against the notes, so it is not shown.
        return AskOut(mode="ungrounded", answer=None, citations=[], hits=hits)
    citations = [CitationOut(number=n, hit=passages[n - 1]) for n in cited]
    return AskOut(mode="answered", answer=answer, citations=citations, hits=hits)
