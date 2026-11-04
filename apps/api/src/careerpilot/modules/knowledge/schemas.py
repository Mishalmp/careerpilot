import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from careerpilot.modules.knowledge.models import DocumentKind

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class HitOut(BaseModel):
    chunk_id: uuid.UUID
    document_name: str
    document_title: str
    kind: DocumentKind
    heading_path: str
    text: str
    score: float
    # Cosine similarity to the question when the vector search found it (1 = identical).
    similarity: float | None


class SearchOut(BaseModel):
    hits: list[HitOut]
    confident: bool
    best_similarity: float | None


class AskRequest(BaseModel):
    question: Question


class CitationOut(BaseModel):
    number: int
    hit: HitOut


class AskOut(BaseModel):
    """`mode` says what happened:
    answered: a written answer with citations; retrieval_only: no AI key, passages only;
    not_in_notes: nothing relevant enough; ungrounded: the AI cited nothing, so it was withheld;
    refused: the AI declined.
    """

    mode: Literal["answered", "retrieval_only", "not_in_notes", "ungrounded", "refused"]
    answer: str | None
    citations: list[CitationOut]
    hits: list[HitOut]


class IngestOut(BaseModel):
    added: int
    updated: int
    unchanged: int
    removed: int
    chunks: int


class StatusOut(BaseModel):
    documents: int
    chunks: int
    indexed_at: datetime | None
    embedding_model: str
    ai_enabled: bool
