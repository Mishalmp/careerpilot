import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Focus = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]

NOTE = (
    "Scores come from the model, judged against what a good answer contains. Treat them as a "
    "second opinion, not a measurement. Your answers are sent to Anthropic when a key is set."
)


class StartMockRequest(BaseModel):
    # Either a job (the interview follows its description and any intel you collected) or a topic.
    job_id: uuid.UUID | None = None
    focus: Focus | None = None
    questions: Annotated[int, Field(ge=3, le=8)] = 5

    @model_validator(mode="after")
    def _something_to_ask_about(self) -> "StartMockRequest":
        if self.job_id is None and self.focus is None:
            raise ValueError("choose a job or give a topic")
        return self


class AnswerMockRequest(BaseModel):
    # The question number you are answering, so a double click cannot answer two questions.
    turn: Annotated[int, Field(ge=0)]
    answer: Answer


class MockTurnOut(BaseModel):
    question: str
    topic: str
    answer: str | None
    score: int | None
    feedback: str | None


class MockTopicResultOut(BaseModel):
    topic: str
    average: float
    questions: int


class MockSummaryOut(BaseModel):
    average: float | None
    answered: int
    weak: list[MockTopicResultOut]
    strong: list[MockTopicResultOut]


class MockSessionOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    focus: str
    total_questions: int
    turns: list[MockTurnOut]
    current_turn: int | None  # the question waiting for your answer
    finished: bool
    summary: MockSummaryOut | None
    created_at: datetime
    note: str = NOTE


class MockSessionItem(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    answered: int
    total_questions: int
    average: float | None
    finished: bool


class RawQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)
    ]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RawEvaluation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: Annotated[int, Field(ge=0, le=5)]
    feedback: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]
    next_question: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    next_topic: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = (
        None
    )
