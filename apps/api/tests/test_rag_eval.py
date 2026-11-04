"""Retrieval quality. The questions are checked without a model; the quality gate needs the real one."""

import json
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.modules.auth import service as auth_service
from careerpilot.modules.knowledge import evaluation, service
from careerpilot.modules.knowledge.chunking import chunk_markdown
from careerpilot.modules.knowledge.embeddings import FastEmbedder
from tests.conftest import TEST_URL

CONTENT = REPO_ROOT / "content"
QUESTIONS = evaluation.load_questions(CONTENT)
BASELINE = json.loads((CONTENT / "eval" / "baseline.json").read_text(encoding="utf-8"))


def test_there_are_enough_questions_of_both_kinds() -> None:
    answerable = [q for q in QUESTIONS if isinstance(q.expect, evaluation.Expect)]
    assert len(answerable) >= 30 and len(QUESTIONS) - len(answerable) >= 6


def test_every_expected_text_really_is_in_its_document() -> None:
    """A wrong question would make the quality numbers meaningless."""
    sources = {s.name: s for s in service.discover(CONTENT)}
    checked = 0
    for question in QUESTIONS:
        expect = question.expect
        if not isinstance(expect, evaluation.Expect) or expect.doc not in sources:
            continue  # private notes are not present everywhere
        needle = expect.contains.casefold()
        chunks = chunk_markdown(sources[expect.doc].text)
        assert any(needle in f"{c.heading_path}\n{c.text}".casefold() for c in chunks), question.id
        checked += 1
    assert checked >= 30


@pytest.mark.skipif(
    not os.environ.get("CAREERPILOT_RUN_MODEL_TESTS"),
    reason="downloads and runs the real embedding model; set CAREERPILOT_RUN_MODEL_TESTS=1",
)
class TestWithTheRealModel:
    @pytest_asyncio.fixture
    async def db(self, user: None) -> AsyncIterator[AsyncSession]:
        engine = create_async_engine(TEST_URL, poolclass=NullPool)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
        await engine.dispose()

    async def test_retrieval_quality_has_not_dropped(
        self, db: AsyncSession, settings: Settings
    ) -> None:
        owner: uuid.UUID = (await auth_service.sole_user(db)).id
        real = settings.model_copy(update={"embedder": "fastembed"})
        embedder = FastEmbedder(real.embedding_model, real.model_cache_dir)
        await service.ingest(db, owner, CONTENT, embedder)

        results, skipped = await evaluation.run(db, owner, embedder, real, QUESTIONS, k=5)
        report = evaluation.summarize(results, skipped, 5)
        print(report)  # shown with -s; the numbers are the point of this test
        assert report.recall_at_k >= BASELINE["recall_at_k"], report.missed
        assert report.mrr >= BASELINE["mrr"]
        assert report.answerable_confident >= BASELINE["answerable_confident"]
        assert report.unanswerable_abstained >= BASELINE["unanswerable_abstained"], (
            report.wrongly_confident
        )
