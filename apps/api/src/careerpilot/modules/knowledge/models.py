import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.knowledge.embeddings import DIMENSIONS


class DocumentKind(StrEnum):
    GUIDE = "guide"  # content/guides, committed
    PRIVATE = "private"  # content/private, git-ignored


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_path", name="uq_documents_owner_id_source_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_path: Mapped[str] = mapped_column(Text)  # e.g. "guides/01-python.md"
    name: Mapped[str] = mapped_column(Text)  # file stem, used in links: /prep/guides/<name>
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[DocumentKind] = mapped_column(str_enum(DocumentKind, "document_kind"))
    # Hash of the text plus the embedding model: a change to either means "re-index this file".
    content_hash: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(Text)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_id_ordinal"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    heading_path: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS))
    # Full-text index over heading and text, kept in sync by the database itself.
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', heading_path || ' ' || text)", persisted=True)
    )
