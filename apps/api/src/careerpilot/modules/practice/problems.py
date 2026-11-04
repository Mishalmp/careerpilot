"""Practice problems: the file format, loading, and starter code generation.

A problem is one YAML file in content/problems/. Function problems describe a signature once and
get starter code in Python, JavaScript and TypeScript generated from it; SQL problems give a schema,
a starter query and datasets. Tests are language-neutral JSON, so the same tests run in every
language.
"""

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Self

import structlog
import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from careerpilot.modules.practice.enums import Compare, Difficulty, Kind, Language

log = structlog.get_logger()

_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_TYPE = re.compile(r"^(int|float|str|bool|any)(\[\])*$")


class Param(BaseModel):
    name: Annotated[str, Field(pattern=_IDENT.pattern)]
    type: str

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if not _TYPE.match(value):
            raise ValueError(
                f"unknown type '{value}' (use int, float, str, bool, any and [] suffixes)"
            )
        return value


class Signature(BaseModel):
    name: Annotated[str, Field(pattern=_IDENT.pattern)]  # the Python name; JS/TS use camelCase
    params: list[Param]
    returns: str

    @field_validator("returns")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if not _TYPE.match(value):
            raise ValueError(f"unknown type '{value}'")
        return value


class FunctionTest(BaseModel):
    name: str
    args: list[Any]
    expected: Any
    hidden: bool = False
    compare: Compare = Compare.EXACT


class SqlExpected(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    ordered: bool = False


class SqlTest(BaseModel):
    name: str
    data: str = ""  # INSERT statements for this dataset
    expected: SqlExpected
    hidden: bool = False


class SqlSpec(BaseModel):
    ddl: str  # CREATE TABLE statements shared by every test
    starter: str
    tests: list[SqlTest]


class Problem(BaseModel):
    slug: Annotated[str, Field(pattern=_SLUG.pattern)]
    title: str
    kind: Kind
    difficulty: Difficulty
    tags: list[str] = []
    # Curriculum topic keys this problem practises (checked against curriculum.yaml in tests).
    topic_keys: list[str] = []
    statement: str
    signature: Signature | None = None
    tests: list[FunctionTest] = []
    sql: SqlSpec | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.kind == Kind.FUNCTION:
            if self.signature is None or self.sql is not None:
                raise ValueError("a function problem needs `signature` and no `sql`")
            tests: list[Any] = list(self.tests)
        else:
            if self.sql is None or self.signature is not None or self.tests:
                raise ValueError("a SQL problem needs `sql` and no `signature` or `tests`")
            tests = list(self.sql.tests)
        if len(tests) < 3:
            raise ValueError("write at least 3 tests")
        if all(test.hidden for test in tests):
            raise ValueError("at least one test must be visible")
        names = [test.name for test in tests]
        if len(names) != len(set(names)):
            raise ValueError("test names must be unique")
        return self

    @property
    def test_count(self) -> int:
        return len(self.sql.tests) if self.sql else len(self.tests)

    @property
    def languages(self) -> list[Language]:
        if self.kind == Kind.SQL:
            return [Language.SQL]
        return [Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT]


# ---- starter code -------------------------------------------------------------------------

_PY_TYPES = {"int": "int", "float": "float", "str": "str", "bool": "bool", "any": "Any"}
_TS_TYPES = {
    "int": "number",
    "float": "number",
    "str": "string",
    "bool": "boolean",
    "any": "unknown",
}


def _split(type_name: str) -> tuple[str, int]:
    depth = type_name.count("[]")
    return type_name.removesuffix("[]" * depth), depth


def _python_type(type_name: str) -> str:
    base, depth = _split(type_name)
    return "list[" * depth + _PY_TYPES[base] + "]" * depth


def _ts_type(type_name: str) -> str:
    base, depth = _split(type_name)
    return _TS_TYPES[base] + "[]" * depth


def camel_case(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(word.capitalize() for word in rest)


@dataclass(frozen=True)
class Starter:
    language: Language
    code: str
    entry: str | None


def starters(problem: Problem) -> list[Starter]:
    if problem.sql:
        return [Starter(Language.SQL, problem.sql.starter, None)]
    sig = problem.signature
    if sig is None:  # the model validator makes this impossible
        raise RuntimeError("function problem without a signature")
    py_params = ", ".join(f"{p.name}: {_python_type(p.type)}" for p in sig.params)
    uses_any = "any" in " ".join([p.type for p in sig.params] + [sig.returns])
    py_import = "from typing import Any\n\n\n" if uses_any else ""
    js_name = camel_case(sig.name)
    js_params = ", ".join(camel_case(p.name) for p in sig.params)
    ts_params = ", ".join(f"{camel_case(p.name)}: {_ts_type(p.type)}" for p in sig.params)
    return [
        Starter(
            Language.PYTHON,
            f"{py_import}def {sig.name}({py_params}) -> {_python_type(sig.returns)}:\n"
            "    # Write your solution here.\n    pass\n",
            sig.name,
        ),
        Starter(
            Language.JAVASCRIPT,
            f"function {js_name}({js_params}) {{\n  // Write your solution here.\n}}\n",
            js_name,
        ),
        Starter(
            Language.TYPESCRIPT,
            f"function {js_name}({ts_params}): {_ts_type(sig.returns)} {{\n"
            "  // Write your solution here.\n}\n",
            js_name,
        ),
    ]


# ---- loading ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Loaded:
    problems: dict[str, Problem]
    errors: list[str]


_cache: dict[Path, tuple[tuple[tuple[str, int], ...], Loaded]] = {}
_lock = threading.Lock()


def _read(path: Path) -> Problem:
    problem = Problem.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if problem.slug != path.stem:
        raise ValueError(f"slug '{problem.slug}' must match the file name '{path.stem}'")
    return problem


def load_problems(content_dir: Path) -> Loaded:
    """Read content/problems/*.yaml. A broken file is reported and skipped, not fatal.

    Results are cached until a file is added, removed or edited.
    """
    directory = content_dir / "problems"
    files = sorted(directory.glob("*.yaml")) if directory.is_dir() else []
    signature = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    with _lock:
        cached = _cache.get(directory)
        if cached and cached[0] == signature:
            return cached[1]
        problems: dict[str, Problem] = {}
        errors: list[str] = []
        for path in files:
            try:
                problem = _read(path)
            except (ValidationError, ValueError, yaml.YAMLError) as exc:
                errors.append(f"{path.name}: {exc}")
                log.error("problem_file_invalid", file=path.name, error=str(exc))
                continue
            problems[problem.slug] = problem
        loaded = Loaded(problems, errors)
        _cache[directory] = (signature, loaded)
        return loaded
