"""Brain node pipeline: make kg && make brain outputs validate against the schemas.

Runs the generators exactly as the make targets do (gen-template-kg.py ->
app/knowledge_graph.json, gen-brain.py -> app/brain.json), then asserts:

- both generators exit 0 and are deterministic (a second run is byte-identical),
- app/knowledge_graph.json carries the conflict-kg/v1 envelope,
- app/brain.json conforms to schemas/brain-envelope.schema.json, with every
  node/edge validated against brain-node / brain-edge,
- scripts/check-brain.py (the provenance/integrity/ordering gate) passes.

The generators are deterministic and their outputs are committed, so running
them in-place never dirties a clean working tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
APP = ROOT / "app"
SCHEMAS = ROOT / "schemas"


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


@pytest.fixture(scope="module")
def generated():
    """Run the kg + brain generators once (as `make kg && make brain` does).

    Snapshots app/ first and restores it after the module: the committed
    app/brain.json is the FEDERATED graph (make aggregate-brain), and the
    single-repo regeneration here must not leave it reverted on disk."""
    originals = {p: p.read_bytes() for p in (APP / "knowledge_graph.json", APP / "brain.json") if p.exists()}
    for script in ("gen-template-kg.py", "gen-brain.py"):
        proc = _run(script)
        assert proc.returncode == 0, f"{script} failed: {proc.stderr}"
    yield {
        "kg": (APP / "knowledge_graph.json").read_bytes(),
        "brain": (APP / "brain.json").read_bytes(),
    }
    for p, data in originals.items():
        p.write_bytes(data)


def test_generators_are_deterministic(generated):
    for script in ("gen-template-kg.py", "gen-brain.py"):
        assert _run(script).returncode == 0
    assert (APP / "knowledge_graph.json").read_bytes() == generated["kg"]
    assert (APP / "brain.json").read_bytes() == generated["brain"]


def test_knowledge_graph_envelope(generated):
    kg = json.loads(generated["kg"])
    assert kg["format"] == "conflict-kg/v1"
    assert isinstance(kg["nodes"], list) and kg["nodes"]
    assert isinstance(kg["edges"], list) and kg["edges"]
    ids = {n["id"] for n in kg["nodes"]}
    assert len(ids) == len(kg["nodes"]), "duplicate node ids"
    for e in kg["edges"]:
        assert e["source"] in ids and e["target"] in ids, f"dangling edge {e}"
    # One node per catalogue template, plus language/size/concept nodes.
    assert sum(1 for n in kg["nodes"] if n["id"].startswith("template:")) == 27


def test_brain_validates_against_schemas(generated):
    brain = json.loads(generated["brain"])
    envelope = json.loads((SCHEMAS / "brain-envelope.schema.json").read_text())
    node_schema = json.loads((SCHEMAS / "brain-node.schema.json").read_text())
    edge_schema = json.loads((SCHEMAS / "brain-edge.schema.json").read_text())

    # Validate the envelope shallowly (nodes/edges item $refs checked below,
    # avoiding cross-file $ref resolution), then every node and edge.
    shallow = dict(envelope)
    shallow["properties"] = dict(envelope["properties"])
    shallow["properties"]["nodes"] = {"type": "array"}
    shallow["properties"]["edges"] = {"type": "array"}
    jsonschema.validate(instance=brain, schema=shallow)
    for n in brain["nodes"]:
        jsonschema.validate(instance=n, schema=node_schema)
    for e in brain["edges"]:
        jsonschema.validate(instance=e, schema=edge_schema)

    assert brain["meta"]["counts"] == {
        "nodes": len(brain["nodes"]),
        "edges": len(brain["edges"]),
    }


def test_check_brain_gate_passes(generated):
    proc = _run("check-brain.py")
    assert proc.returncode == 0, f"check-brain failed: {proc.stdout}{proc.stderr}"


def test_aggregate_include_self(generated, tmp_path):
    """Master-brain mode: --include-self folds this repo's own brain in
    verbatim (bare ids, no anchor) alongside a namespaced sub-brain."""
    sub = tmp_path / "fake-template"
    (sub / "app").mkdir(parents=True)
    (sub / "app" / "brain.json").write_text(
        json.dumps(
            {
                "meta": {"version": "1", "generator": "gen-brain", "counts": {"nodes": 1, "edges": 0}},
                "nodes": [{"id": "concept:widget", "kind": "Concept", "title": "Widget", "derived": True}],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "federated.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "aggregate-brains.py"),
            str(sub),
            "--include-self",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    graph = json.loads(out.read_text(encoding="utf-8"))
    ids = {n["id"] for n in graph["nodes"]}
    own = json.loads(generated["brain"])
    for n in own["nodes"][:5]:
        assert n["id"] in ids, "own brain ids must stay bare"
    assert "fake-template/concept:widget" in ids
    assert "repo:fake-template" in ids
    assert not any(i.startswith("repo:") and i != "repo:fake-template" for i in ids)
