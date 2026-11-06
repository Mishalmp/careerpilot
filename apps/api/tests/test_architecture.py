"""The architecture explorer's content and its drift checks.
# covers: REQ-14, REQ-15, REQ-17 (explorer content cannot silently drift from the code)
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from careerpilot.core.config import REPO_ROOT
from careerpilot.modules.architecture import service

CONTENT = REPO_ROOT / "content"
BASE = "/api/v1/architecture"


# --- drift: content versus code ---------------------------------------------------------------------


def test_content_matches_the_code() -> None:
    """One check that fails with a precise message if anything has drifted."""
    assert service.problems(CONTENT) == []


def test_every_module_on_disk_is_drawn_and_nothing_extra_is() -> None:
    drawn = {
        n.id
        for d in service.load_diagrams(CONTENT)
        if d.id == "modules"
        for n in d.nodes
        if n.kind == "module"
    }
    assert drawn == {f"module:{m}" for m in service.module_names()}


def test_module_arrows_are_computed_from_real_imports() -> None:
    (modules,) = [d for d in service.load_diagrams(CONTENT) if d.id == "modules"]
    arrows = {(e.source, e.target) for e in modules.edges}
    real = {(f"module:{a}", f"module:{b}") for a, b in service.module_dependencies()}
    assert arrows == real
    # A known, deliberate dependency: Today builds its page from the tracker and prep services.
    assert ("module:today", "module:tracker") in arrows


def test_a_module_missing_from_the_diagram_is_reported(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    (architecture / "concepts").mkdir(parents=True)
    for name in ("systems.yaml", "flows.yaml"):
        (architecture / name).write_text(
            (CONTENT / "architecture" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    text = (architecture / "systems.yaml").read_text(encoding="utf-8")
    kept = "\n".join(line for line in text.splitlines() if "module:learn" not in line)
    (architecture / "systems.yaml").write_text(kept, encoding="utf-8")
    messages = service.problems(tmp_path)
    assert any("module:learn exists in code but has no node" in m for m in messages)


def test_a_bad_concept_reference_is_reported(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    (architecture / "concepts").mkdir(parents=True)
    for name in ("systems.yaml", "flows.yaml"):
        (architecture / name).write_text(
            (CONTENT / "architecture" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (architecture / "concepts" / "x.md").write_text(
        "---\nid: x\ntitle: X\nlevel: beginner\nrelated: [nope]\nappears_in: [module:ghost]\nproof: [no/such/file.py]\n---\n\nBody",
        encoding="utf-8",
    )
    messages = "\n".join(service.problems(tmp_path))
    assert "related nope does not exist" in messages
    assert "appears_in module:ghost is not a node" in messages
    assert "proof no/such/file.py does not exist" in messages


def test_a_built_flow_must_name_a_proof(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    (architecture / "concepts").mkdir(parents=True)
    (architecture / "systems.yaml").write_text(
        (CONTENT / "architecture" / "systems.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (architecture / "flows.yaml").write_text(
        "flows:\n  - id: f\n    title: F\n    summary: S\n    status: built\n    proof: []\n    steps:\n"
        "      - {from: browser, to: web, label: L, detail: D}\n",
        encoding="utf-8",
    )
    assert any("a built flow needs a proof test" in m for m in service.problems(tmp_path))


def test_every_flow_and_concept_has_content() -> None:
    flows = service.load_flows(CONTENT)
    assert len(flows) >= 5
    assert all(f.steps for f in flows)
    assert any(s.failure for f in flows for s in f.steps)  # failure branches exist
    concepts = service.load_concepts(CONTENT)
    assert len(concepts) >= 20
    for c in concepts:
        assert c.body.startswith("**Idea**") or c.id in {
            "testing",
            "talking-about-this-project",
            "reading-list",
        }


# --- the API -------------------------------------------------------------------------------------------


async def test_the_endpoints_serve_the_content(api: AsyncClient) -> None:
    diagrams = (await api.get(f"{BASE}/diagrams")).json()
    assert {d["id"] for d in diagrams} == {"overview", "modules"}
    overview = next(d for d in diagrams if d["id"] == "overview")
    assert {"browser", "api", "db", "worker"} <= {n["id"] for n in overview["nodes"]}
    assert all({"source", "target"} <= set(e) for e in overview["edges"])

    flows = (await api.get(f"{BASE}/flows")).json()
    assert "answer-question" in {f["id"] for f in flows}

    concepts = (await api.get(f"{BASE}/concepts")).json()
    assert all("body" not in c for c in concepts)
    queues = (await api.get(f"{BASE}/concepts/queues")).json()
    assert queues["title"].startswith("Queues")
    assert "SKIP LOCKED" in queues["body"]


async def test_unknown_concept_is_not_found(api: AsyncClient) -> None:
    assert (await api.get(f"{BASE}/concepts/not-a-concept")).status_code == 404
    assert (await api.get(f"{BASE}/concepts/..%2F..%2Fsecrets")).status_code == 404


async def test_the_explorer_requires_a_session(client: AsyncClient) -> None:
    for path in ("diagrams", "flows", "concepts", "concepts/queues"):
        assert (await client.get(f"{BASE}/{path}")).status_code == 401


@pytest.mark.parametrize("name", ["systems.yaml", "flows.yaml"])
def test_content_files_exist(name: str) -> None:
    assert (CONTENT / "architecture" / name).is_file()
