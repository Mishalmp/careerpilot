"""Measure retrieval quality on a fixed list of questions, so a change can be judged by numbers.

Every change to chunking, embeddings or ranking should be followed by `careerpilot eval-rag`.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.modules.knowledge import repository, service
from careerpilot.modules.knowledge.embeddings import Embedder


class Expect(BaseModel):
    doc: str
    contains: str


class Question(BaseModel):
    id: str
    question: str
    expect: Expect | Literal["none"]


def load_questions(content_dir: Path) -> list[Question]:
    raw = yaml.safe_load((content_dir / "eval" / "questions.yaml").read_text(encoding="utf-8"))
    questions = [Question.model_validate(item) for item in raw]
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("question ids must be unique")
    return questions


@dataclass(frozen=True)
class Result:
    id: str
    answerable: bool
    rank: int | None  # 1-based position of the first correct passage, or None if it was not found
    confident: bool
    best_similarity: float | None


@dataclass(frozen=True)
class Report:
    answerable: int
    unanswerable: int
    skipped: int
    recall_at_k: float
    mrr: float
    answerable_confident: float  # of answerable questions, how many the search accepted as covered
    unanswerable_abstained: float  # of unanswerable questions, how many it correctly refused
    k: int
    missed: list[str]
    wrongly_confident: list[str]


async def run(
    db: AsyncSession,
    owner_id: uuid.UUID,
    embedder: Embedder,
    settings: Settings,
    questions: list[Question],
    *,
    k: int = 5,
    mode: Literal["hybrid", "vector", "text"] = "hybrid",
) -> tuple[list[Result], int]:
    """Search every question. Returns the results and the count skipped (document not indexed)."""
    indexed = {doc.name for doc in (await repository.documents_by_path(db, owner_id)).values()}
    results: list[Result] = []
    skipped = 0
    for question in questions:
        expect = question.expect
        if isinstance(expect, Expect) and expect.doc not in indexed:
            skipped += 1
            continue
        found = await service.search(
            db, owner_id, embedder, settings, question.question, limit=max(k, 8), mode=mode
        )
        rank = None
        if isinstance(expect, Expect):
            needle = expect.contains.casefold()
            for position, hit in enumerate(found.hits, start=1):
                if (
                    hit.document_name == expect.doc
                    and needle in f"{hit.heading_path}\n{hit.text}".casefold()
                ):
                    rank = position
                    break
        results.append(
            Result(
                question.id,
                isinstance(expect, Expect),
                rank,
                found.confident,
                found.best_similarity,
            )
        )
    return results, skipped


def summarize(results: list[Result], skipped: int, k: int = 5) -> Report:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    found = [r for r in answerable if r.rank is not None and r.rank <= k]
    return Report(
        answerable=len(answerable),
        unanswerable=len(unanswerable),
        skipped=skipped,
        recall_at_k=round(len(found) / len(answerable), 4) if answerable else 0.0,
        mrr=round(sum(1 / r.rank for r in answerable if r.rank) / len(answerable), 4)
        if answerable
        else 0.0,
        answerable_confident=round(sum(r.confident for r in answerable) / len(answerable), 4)
        if answerable
        else 0.0,
        unanswerable_abstained=round(
            sum(not r.confident for r in unanswerable) / len(unanswerable), 4
        )
        if unanswerable
        else 0.0,
        k=k,
        missed=[r.id for r in answerable if r.rank is None or r.rank > k],
        wrongly_confident=[r.id for r in unanswerable if r.confident],
    )
