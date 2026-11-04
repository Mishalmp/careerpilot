import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from careerpilot.modules.practice.enums import (
    Compare,
    Difficulty,
    Kind,
    Language,
    ProgressStatus,
)


class ProblemSummary(BaseModel):
    slug: str
    title: str
    kind: Kind
    difficulty: Difficulty
    tags: list[str]
    topic_keys: list[str]
    languages: list[Language]
    status: ProgressStatus


class LanguageSpec(BaseModel):
    language: Language
    starter: str
    entry: str | None


class FunctionTestOut(BaseModel):
    """The runner needs every case. `hidden` only hides a case in the UI."""

    name: str
    hidden: bool
    args: list[Any]
    expected: Any
    compare: Compare


class SqlExpectedOut(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    ordered: bool


class SqlTestOut(BaseModel):
    name: str
    hidden: bool
    data: str
    expected: SqlExpectedOut


class ProblemDetail(ProblemSummary):
    statement: str
    specs: list[LanguageSpec]
    function_tests: list[FunctionTestOut]
    sql_ddl: str | None
    sql_tests: list[SqlTestOut]


class CaseResult(BaseModel):
    name: Annotated[str, StringConstraints(max_length=200)]
    status: Literal["pass", "fail", "error", "timeout", "skipped"]


class SubmissionCreate(BaseModel):
    language: Language
    code: Annotated[str, StringConstraints(max_length=50_000)]
    passed: Annotated[int, Field(ge=0, le=1000)]
    total: Annotated[int, Field(ge=1, le=1000)]
    runtime_ms: Annotated[int, Field(ge=0, le=3_600_000)]
    results: Annotated[list[CaseResult], Field(max_length=1000)]


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    language: Language
    code: str
    passed: int
    total: int
    runtime_ms: int
    results: list[CaseResult]
    created_at: datetime
