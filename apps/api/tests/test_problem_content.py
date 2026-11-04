"""Checks every file in content/problems: format, references to the curriculum, and that the tests
themselves are right (a reference solution passes all of them; the empty starter passes none)."""

import importlib.util
import json
import re
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.modules.practice.enums import Kind, Language
from careerpilot.modules.practice.problems import Problem, load_problems, starters
from careerpilot.modules.prep.curriculum import load_curriculum
from tests.conftest import TEST_URL
from tests.problem_solutions import PYTHON, SQL

CONTENT = REPO_ROOT / "content"
HARNESS_PATH = REPO_ROOT / "apps" / "web" / "public" / "runner" / "harness.py"
PROBLEMS = load_problems(CONTENT).problems
FUNCTION_PROBLEMS = [p for p in PROBLEMS.values() if p.kind == Kind.FUNCTION]
SQL_PROBLEMS = [p for p in PROBLEMS.values() if p.kind == Kind.SQL]


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("runner_harness", HARNESS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load_harness()


def run(problem: Problem, source: str) -> list[dict[str, Any]]:
    assert problem.signature is not None
    return [
        json.loads(
            harness.run_test(
                source,
                problem.signature.name,
                json.dumps(test.args),
                json.dumps(test.expected),
                test.compare.value,
            )
        )
        for test in problem.tests
    ]


def test_every_problem_file_is_valid_and_there_are_enough() -> None:
    loaded = load_problems(CONTENT)
    assert loaded.errors == []
    assert len(loaded.problems) >= 25
    assert len(FUNCTION_PROBLEMS) >= 18 and len(SQL_PROBLEMS) >= 6


def test_every_problem_has_a_reference_solution_and_no_stray_ones() -> None:
    assert {p.slug for p in FUNCTION_PROBLEMS} == set(PYTHON)
    assert {p.slug for p in SQL_PROBLEMS} == set(SQL)


def test_topic_keys_exist_in_the_curriculum() -> None:
    curriculum = load_curriculum(CONTENT)
    known = {t.key for area in curriculum.areas for t in area.topics}
    for problem in PROBLEMS.values():
        assert set(problem.topic_keys) <= known, problem.slug


def test_difficulty_and_tags_are_filled_in() -> None:
    for problem in PROBLEMS.values():
        assert problem.tags, problem.slug
        assert len(problem.statement) > 80, problem.slug


@pytest.mark.parametrize("problem", FUNCTION_PROBLEMS, ids=lambda p: p.slug)
def test_reference_solution_passes_every_test(problem: Problem) -> None:
    results = run(problem, PYTHON[problem.slug])
    failures = [
        (t.name, r) for t, r in zip(problem.tests, results, strict=True) if r["status"] != "pass"
    ]
    assert failures == []


@pytest.mark.parametrize("problem", FUNCTION_PROBLEMS, ids=lambda p: p.slug)
def test_the_empty_starter_passes_no_test(problem: Problem) -> None:
    python_starter = next(s for s in starters(problem) if s.language == Language.PYTHON)
    results = run(problem, python_starter.code)
    assert all(r["status"] != "pass" for r in results), (
        "a test that an empty answer passes proves nothing"
    )


@pytest.mark.parametrize("problem", FUNCTION_PROBLEMS, ids=lambda p: p.slug)
def test_a_wrong_answer_is_caught(problem: Problem) -> None:
    """Returning the first argument unchanged must not satisfy the whole suite."""
    assert problem.signature is not None
    source = f"def {problem.signature.name}(*args):\n    return args[0]\n"
    assert any(r["status"] != "pass" for r in run(problem, source))


def test_tests_are_json_and_names_are_short() -> None:
    for problem in FUNCTION_PROBLEMS:
        json.dumps([t.model_dump(mode="json") for t in problem.tests])
        assert all(len(t.name) <= 60 for t in problem.tests), problem.slug


# ---- SQL: run each reference query on real Postgres -----------------------------------------


def _cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _canonical(rows: list[list[Any]], ordered: bool) -> list[str]:
    keys = [json.dumps([round(c, 6) if isinstance(c, float) else c for c in row]) for row in rows]
    return keys if ordered else sorted(keys)


@pytest.mark.parametrize("problem", SQL_PROBLEMS, ids=lambda p: p.slug)
async def test_sql_reference_matches_expected_on_every_dataset(problem: Problem) -> None:
    assert problem.sql is not None
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            pg: Any = raw.driver_connection  # asyncpg connection
            for test in problem.sql.tests:
                schema = f"check_{uuid.uuid4().hex[:8]}"
                await pg.execute(f"CREATE SCHEMA {schema}")
                try:
                    await pg.execute(f"SET search_path TO {schema}")
                    await pg.execute(problem.sql.ddl + "\n" + test.data)
                    statement = await pg.prepare(SQL[problem.slug])
                    columns = [a.name.lower() for a in statement.get_attributes()]
                    rows = [
                        [_cell(v) for v in record.values()] for record in await statement.fetch()
                    ]
                finally:
                    await pg.execute("RESET search_path")
                    await pg.execute(f"DROP SCHEMA {schema} CASCADE")
                expected = test.expected
                assert columns == [c.lower() for c in expected.columns], test.name
                assert _canonical(rows, expected.ordered) == _canonical(
                    expected.rows, expected.ordered
                ), test.name
    finally:
        await engine.dispose()


@pytest.mark.parametrize("problem", SQL_PROBLEMS, ids=lambda p: p.slug)
def test_sql_starter_is_not_already_the_answer(problem: Problem) -> None:
    assert problem.sql is not None
    assert problem.sql.starter.strip() != SQL[problem.slug].strip()


def test_every_practice_link_in_the_guides_points_at_a_real_problem() -> None:
    links = {
        (guide.name, match)
        for guide in (CONTENT / "guides").glob("*.md")
        for match in re.findall(r"\]\(practice:([^)\s]+)\)", guide.read_text(encoding="utf-8"))
    }
    assert links, "the guides should link to problems"
    assert [link for link in links if link[1] not in PROBLEMS] == []


def test_every_problem_is_linked_from_some_guide() -> None:
    linked = {
        match
        for guide in (CONTENT / "guides").glob("*.md")
        for match in re.findall(r"\]\(practice:([^)\s]+)\)", guide.read_text(encoding="utf-8"))
    }
    assert set(PROBLEMS) - linked == set()


def test_statements_do_not_contain_html() -> None:
    for problem in PROBLEMS.values():
        assert not re.search(r"<\s*script", problem.statement, re.I), problem.slug


def test_default_content_dir_is_the_repo_content_folder(settings: Settings) -> None:
    assert Path(settings.content_dir) == CONTENT
