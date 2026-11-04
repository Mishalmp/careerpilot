import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.knowledge.models import Chunk, Document


async def documents_by_path(db: AsyncSession, owner_id: uuid.UUID) -> dict[str, Document]:
    rows = await db.scalars(select(Document).where(Document.owner_id == owner_id))
    return {doc.source_path: doc for doc in rows}


async def replace_document(
    db: AsyncSession,
    owner_id: uuid.UUID,
    existing: Document | None,
    fields: dict[str, Any],
    chunks: Sequence[dict[str, Any]],
) -> Document:
    """Write a document and all its chunks. Old chunks go first, in the same transaction."""
    if existing is None:
        document = Document(owner_id=owner_id, **fields)
        db.add(document)
        await db.flush()
    else:
        document = existing
        for name, value in fields.items():
            setattr(document, name, value)
        document.indexed_at = datetime.now(UTC)
        await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    db.add_all(Chunk(owner_id=owner_id, document_id=document.id, **chunk) for chunk in chunks)
    await db.flush()
    return document


async def delete_documents(db: AsyncSession, owner_id: uuid.UUID, paths: Sequence[str]) -> None:
    if paths:
        await db.execute(
            delete(Document).where(Document.owner_id == owner_id, Document.source_path.in_(paths))
        )


async def vector_search(
    db: AsyncSession, owner_id: uuid.UUID, query_vector: list[float], limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Nearest chunks by cosine distance (0 = identical). Uses the HNSW index."""
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = await db.execute(
        select(Chunk.id, distance.label("distance"))
        .where(Chunk.owner_id == owner_id)
        .order_by(distance)
        .limit(limit)
    )
    return [(chunk_id, float(d)) for chunk_id, d in rows.all()]


async def text_search(
    db: AsyncSession, owner_id: uuid.UUID, tsquery: str, limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Chunks containing any query word, best first. `tsquery` is built from plain words only."""
    if not tsquery:
        return []
    query = func.to_tsquery("english", tsquery)
    rank = func.ts_rank_cd(Chunk.tsv, query)
    rows = await db.execute(
        select(Chunk.id, rank.label("rank"))
        .where(Chunk.owner_id == owner_id, Chunk.tsv.op("@@")(query))
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )
    return [(chunk_id, float(r)) for chunk_id, r in rows.all()]


async def chunks_with_documents(
    db: AsyncSession, owner_id: uuid.UUID, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[Chunk, Document]]:
    if not ids:
        return {}
    rows = await db.execute(
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.owner_id == owner_id, Chunk.id.in_(ids))
    )
    return {chunk.id: (chunk, document) for chunk, document in rows.all()}


async def index_status(db: AsyncSession, owner_id: uuid.UUID) -> tuple[int, int, datetime | None]:
    documents = await db.scalar(
        select(func.count()).select_from(Document).where(Document.owner_id == owner_id)
    )
    chunks = await db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.owner_id == owner_id)
    )
    latest = await db.scalar(
        select(func.max(Document.indexed_at)).where(Document.owner_id == owner_id)
    )
    return int(documents or 0), int(chunks or 0), latest


async def set_search_quality(db: AsyncSession) -> None:
    """Make the HNSW index look at more candidates: slower, more accurate (default is 40)."""
    await db.execute(text("SET LOCAL hnsw.ef_search = 100"))
