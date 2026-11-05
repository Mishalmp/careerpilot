import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from careerpilot.modules.intel.enums import ItemKind, SourceKind
from careerpilot.modules.tracker.schemas import Url

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
SourceText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=40, max_length=20000)
]

HONESTY_NOTE = (
    "Everything here comes from the sources listed, each with a quote that was checked against "
    "the source text. Facts from a text about another company are marked as inferred. Nothing "
    "is a prediction of what you will be asked."
)


class SourceCreate(BaseModel):
    """Either paste text you read yourself, or give a page for CareerPilot to fetch."""

    label: Label
    text: SourceText | None = None
    url: Url | None = None
    # Who the text is about. Leave out when it is about the job's own company.
    about_company: Name | None = None
    published_on: date | None = None

    @model_validator(mode="after")
    def _text_or_url(self) -> "SourceCreate":
        if not self.text and not self.url:
            raise ValueError("give the text you copied, or a page address to fetch")
        return self


class SourceOut(BaseModel):
    id: uuid.UUID
    kind: SourceKind
    label: str
    url: str | None
    about_company: str
    inferred: bool  # about another company
    published_on: date | None
    item_count: int
    characters: int


class ExtractOut(BaseModel):
    source: SourceOut
    kept: int
    dropped: int  # items whose quote was not in the source text


class ItemOut(BaseModel):
    id: uuid.UUID
    kind: ItemKind
    key: str
    text: str
    quote: str
    source_id: uuid.UUID
    source_label: str
    source_url: str | None
    published_on: date | None
    inferred: bool
    similar_to: str | None
    reliability: int


class IntelTopicOut(BaseModel):
    key: str
    sources: int
    reliability: int
    inferred_only: bool
    prep_topics: list[str]  # your prep topics that cover it


class BriefOut(BaseModel):
    rounds: list[ItemOut]
    topics: list[IntelTopicOut]
    likely_questions: list[ItemOut]
    tips: list[ItemOut]
    own_recent_sources: int
    needs_more_sources: bool


class IntelOut(BaseModel):
    job_id: uuid.UUID
    company_name: str
    sources: list[SourceOut]
    brief: BriefOut
    ai_available: bool
    note: str = HONESTY_NOTE


class PeerOut(BaseModel):
    name: str
    why: str


class PeersOut(BaseModel):
    peers: list[PeerOut]
    note: str = (
        "Suggestions of where to look, from the model's general knowledge. They are not facts "
        "about any interview. Find write-ups about them, then add those as sources."
    )


class QuestionsOut(BaseModel):
    questions: list[str]
    note: str = "Suggestions from the model, based only on the job description."


# What the model is asked to return (validated before anything is stored).


class RawItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["round", "topic", "question", "tip"]
    key: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=400)
    quote: str = Field(default="", max_length=600)


class RawItems(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[RawItem] = Field(default=[], max_length=40)


class RawPeers(BaseModel):
    model_config = ConfigDict(extra="ignore")

    peers: list[PeerOut] = Field(default=[], max_length=5)


class RawQuestions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]
    ] = Field(min_length=1, max_length=3)
