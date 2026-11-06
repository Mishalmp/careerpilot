"""The architecture explorer's content: hand-written diagrams, flows and concept pages from
`content/architecture/`, plus facts computed from the code (module dependencies), so the picture of
the backend cannot drift from the backend. `problems()` lists every inconsistency; a test requires
it to be empty.
"""

import ast
from pathlib import Path
from typing import Any

import yaml

from careerpilot.core.config import REPO_ROOT
from careerpilot.core.errors import ProblemError
from careerpilot.modules.architecture.schemas import (
    ConceptDetail,
    ConceptSummary,
    Diagram,
    DiagramEdge,
    DiagramNode,
    Flow,
)

MODULES_PREFIX = "careerpilot.modules."


def _architecture_dir(content_dir: Path) -> Path:
    return content_dir / "architecture"


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a mapping")
    return data  # pyright: ignore[reportUnknownVariableType]


# --- code facts --------------------------------------------------------------------------------


def module_names(src_root: Path | None = None) -> list[str]:
    """Feature modules that exist on disk (one folder each under careerpilot/modules)."""
    root = (src_root or REPO_ROOT / "apps" / "api" / "src") / "careerpilot" / "modules"
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "__init__.py").exists())


def module_dependencies(src_root: Path | None = None) -> set[tuple[str, str]]:
    """(importer, imported) pairs between feature modules, read from the real import statements."""
    root = (src_root or REPO_ROOT / "apps" / "api" / "src") / "careerpilot" / "modules"
    edges: set[tuple[str, str]] = set()
    for name in module_names(src_root):
        for file in (root / name).rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                targets: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    targets.append(node.module)
                elif isinstance(node, ast.Import):
                    targets.extend(alias.name for alias in node.names)
                for target in targets:
                    if target.startswith(MODULES_PREFIX):
                        other = target.removeprefix(MODULES_PREFIX).split(".")[0]
                        if other != name:
                            edges.add((name, other))
    return edges


# --- loading -----------------------------------------------------------------------------------


def load_diagrams(content_dir: Path, src_root: Path | None = None) -> list[Diagram]:
    raw = _read_yaml(_architecture_dir(content_dir) / "systems.yaml")
    diagrams: list[Diagram] = []
    for diagram_id, body in raw.items():
        nodes: list[DiagramNode] = []
        for item in body["nodes"]:
            kind = item.get("kind")
            if kind is None:
                kind = (
                    "core" if item["id"] == "core" or item["id"].startswith("core:") else "module"
                )
            nodes.append(DiagramNode.model_validate({**item, "kind": kind}))
        edges = [DiagramEdge.model_validate(e) for e in body.get("edges", [])]
        if diagram_id == "modules":
            present = {n.id for n in nodes}
            edges = [
                DiagramEdge(source=f"module:{a}", target=f"module:{b}")
                for a, b in sorted(module_dependencies(src_root))
                if f"module:{a}" in present and f"module:{b}" in present
            ]
        diagrams.append(
            Diagram(
                id=diagram_id,
                title=body["title"],
                summary=body["summary"],
                nodes=nodes,
                edges=edges,
            )
        )
    return diagrams


def load_flows(content_dir: Path) -> list[Flow]:
    raw = _read_yaml(_architecture_dir(content_dir) / "flows.yaml")
    return [Flow.model_validate(f) for f in raw["flows"]]


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValueError("a concept file must start with front matter")
    head, _, body = text[4:].partition("\n---\n")
    meta = yaml.safe_load(head)
    if not isinstance(meta, dict):
        raise ValueError("front matter must be a mapping")
    return meta, body.strip()  # pyright: ignore[reportUnknownVariableType]


def load_concepts(content_dir: Path) -> list[ConceptDetail]:
    folder = _architecture_dir(content_dir) / "concepts"
    concepts: list[ConceptDetail] = []
    for path in sorted(folder.glob("*.md")):
        meta, body = _split_front_matter(path.read_text(encoding="utf-8").replace("\r\n", "\n"))
        concepts.append(ConceptDetail.model_validate({**meta, "body": body}))
    return concepts


def concept_summaries(content_dir: Path) -> list[ConceptSummary]:
    return [
        ConceptSummary.model_validate(c.model_dump(exclude={"body"}))
        for c in load_concepts(content_dir)
    ]


def get_concept(content_dir: Path, concept_id: str) -> ConceptDetail:
    for concept in load_concepts(content_dir):
        if concept.id == concept_id:
            return concept
    raise ProblemError(404, "Not found", "Concept not found.")


# --- consistency -------------------------------------------------------------------------------


def problems(
    content_dir: Path, repo_root: Path | None = None, src_root: Path | None = None
) -> list[str]:
    """Everything inconsistent between the content and the code. Empty when all is well."""
    root = repo_root or REPO_ROOT
    found: list[str] = []
    diagrams = load_diagrams(content_dir, src_root)
    by_id = {d.id: d for d in diagrams}
    all_node_ids: set[str] = set()
    for diagram in diagrams:
        ids = [n.id for n in diagram.nodes]
        if len(ids) != len(set(ids)):
            found.append(f"diagram {diagram.id}: duplicate node ids")
        all_node_ids |= set(ids)
        for edge in diagram.edges:
            for end in (edge.source, edge.target):
                if end not in ids:
                    found.append(f"diagram {diagram.id}: edge uses unknown node {end}")
        for node in diagram.nodes:
            found.extend(
                f"node {node.id}: link {link} does not exist"
                for link in node.links
                if not (root / link).exists()
            )

    modules = by_id.get("modules")
    on_disk = {f"module:{m}" for m in module_names(src_root)}
    drawn: set[str] = {n.id for n in modules.nodes if n.kind == "module"} if modules else set()
    found.extend(
        f"module {m} exists in code but has no node in systems.yaml"
        for m in sorted(on_disk - drawn)
    )
    found.extend(
        f"node {m} is in systems.yaml but there is no such module" for m in sorted(drawn - on_disk)
    )

    overview_ids: set[str] = (
        {n.id for n in by_id["overview"].nodes} if "overview" in by_id else set()
    )
    flows = load_flows(content_dir)
    flow_ids = [f.id for f in flows]
    if len(flow_ids) != len(set(flow_ids)):
        found.append("flows: duplicate ids")
    for flow in flows:
        for step in flow.steps:
            for end in (step.source, step.target):
                if end not in overview_ids:
                    found.append(f"flow {flow.id}: step uses unknown node {end}")
        found.extend(
            f"flow {flow.id}: proof {p} does not exist"
            for p in flow.proof
            if not (root / p).exists()
        )
        if flow.status == "built" and not flow.proof:
            found.append(f"flow {flow.id}: a built flow needs a proof test")

    concepts = load_concepts(content_dir)
    concept_ids = {c.id for c in concepts}
    if len(concept_ids) != len(concepts):
        found.append("concepts: duplicate ids")
    for c in concepts:
        found.extend(
            f"concept {c.id}: related {r} does not exist" for r in c.related if r not in concept_ids
        )
        found.extend(
            f"concept {c.id}: appears_in {a} is not a node"
            for a in c.appears_in
            if a not in all_node_ids
        )
        found.extend(
            f"concept {c.id}: proof {p} does not exist" for p in c.proof if not (root / p).exists()
        )
    return found
