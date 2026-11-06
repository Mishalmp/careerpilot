from typing import Any, Literal, cast

from pydantic import BaseModel, model_validator

Status = Literal["built", "planned"]
Kind = Literal["ui", "service", "store", "external", "module", "core"]


class DiagramNode(BaseModel):
    id: str
    kind: Kind
    status: Status = "built"
    title: str
    summary: str
    links: list[str] = []
    x: float
    y: float


def _rename_from_to(data: Any) -> Any:
    """The YAML says `from:`/`to:` because it reads better; the API says source/target."""
    if not isinstance(data, dict):
        return data
    mapping = cast("dict[str, Any]", data)
    if "from" in mapping and "to" in mapping:
        renamed = dict(mapping)
        renamed["source"] = renamed.pop("from")
        renamed["target"] = renamed.pop("to")
        return renamed
    return mapping


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str | None = None

    _rename = model_validator(mode="before")(_rename_from_to)


class Diagram(BaseModel):
    id: str
    title: str
    summary: str
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]


class FlowFailure(BaseModel):
    label: str
    detail: str


class FlowStep(BaseModel):
    source: str
    target: str
    label: str
    detail: str
    failure: FlowFailure | None = None

    _rename = model_validator(mode="before")(_rename_from_to)


class Flow(BaseModel):
    id: str
    title: str
    summary: str
    status: Status = "built"
    proof: list[str] = []
    steps: list[FlowStep]


class ConceptSummary(BaseModel):
    id: str
    title: str
    level: Literal["beginner", "intermediate", "advanced"]
    related: list[str]
    appears_in: list[str]
    proof: list[str]


class ConceptDetail(ConceptSummary):
    body: str
