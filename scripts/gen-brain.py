#!/usr/bin/env python3
"""Federate the template's structured JSON sources into one brain graph.

The portal already emits a dozen structured artifacts (decisions, open
questions, action items, RAID, roadmap, deliverables, user stories,
stakeholders, glossary, sessions, dependencies, the spec manifest, and the
knowledge graph). Each holds one slice of the engagement. This script is the
federated compiler: it reads those sources and projects them into one uniform
property graph at app/brain.json so a single index can be searched and walked.

No new data — it only RELOCATES and RELATES what already exists, stamping every
node with the source file it came from (provenance). The brain is a compiled
artifact: never hand-edit app/brain.json, regenerate it from the sources.

Architecture — a registry of thin adapters, one per source:

    @adapter
    def decisions(root): -> (nodes, edges)

Adapters are REGISTERED, not hardcoded: adding a new source = writing one
adapter and decorating it. Each adapter opens its source file under ROOT,
tolerates a missing or empty file (returns an empty graph rather than
crashing), and emits nodes + edges in the uniform envelope.

Schema contract (schemas/brain-node.schema.json + brain-edge.schema.json):
    node: { id, kind(required), title?, text?, source?, durability?, derived?,
            status?, owner?, labels?[], data?{} }
    edge: { source(required), target(required), rel?, class?, data?{} }
Each source maps to a FIRST-CLASS `kind` from the taxonomy (Memory, Decision,
OpenQuestion, ActionItem, Session, Spec, Risk, Deliverable, Roadmap, Story,
Stakeholder, Dependency, Term, Concept) — the kind itself is the discriminator,
so no `data.subkind` is needed. Concept is reserved for derived KG nodes
(`derived=True`), which are projected from sessions rather than authored as a
source artifact. Every node carries a `durability` (durable-logic for the facts
that persist — decisions, specs, memory, terms; point-in-time for the dated
records — sessions, action items, questions, risks, roadmap, deliverables,
stories, stakeholders, dependencies); the richer per-node fields go inside
`data`, which the schema permits as a free-form object. The output is the
{meta, nodes, edges} envelope (schemas/brain-envelope.schema.json): nodes and
edges conform to brain-node/brain-edge (app/brain.json#/nodes, #/edges), and a
`meta` block self-describes the format — `meta.version` (BRAIN_VERSION) is the
authoritative schema version a stale brain is migrated against (#25, via
scripts/migrate-brain.py + `make migrate-brain`).

Determinism: meta is a fixed, derived object (version + generator + recomputed
counts — no timestamps or env), nodes are sorted by id, edges by (source,
target, rel), and the file is written with indent=1 — a stable, diff-friendly,
round-trippable shape.

Run from anywhere:  python3 scripts/gen-brain.py
"""

from __future__ import annotations

import json
import os

from config import settings  # noqa: F401  (Phase-0 frozen config singleton)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "brain.json")

# Authoritative brain-envelope schema version (#25). Stamped into meta.version so
# brain.json self-describes its format; scripts/migrate-brain.py upgrades any
# brain whose meta.version is older than this. Bump it (and register a migration)
# whenever the envelope/node/edge format changes incompatibly.
BRAIN_VERSION = "1"
GENERATOR = "gen-brain"


# ----------------------------------------------------------------------------
# Adapter registry
# ----------------------------------------------------------------------------
#
# ADAPTERS is the source of truth for what gets federated. Each adapter is a
# `(root) -> (nodes, edges)` callable registered by the @adapter decorator, so
# adding a source is a one-function change with no edits to main().

ADAPTERS = []


def adapter(fn):
    """Register a source adapter. Decorated fns run in registration order."""
    ADAPTERS.append(fn)
    return fn


def _load(root: str, *parts: str):
    """Read a JSON source under ROOT. Missing/invalid -> None (never raises)."""
    path = os.path.join(root, *parts)
    try:
        # utf-8-sig tolerates (and strips) an optional leading BOM — a common
        # Windows/export artifact. A bare utf-8 read raises on a BOM, which the
        # except below would swallow, silently dropping the whole file's content.
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _rows(data, key: str) -> list:
    """Pull a list under `key` from a loaded source. Tolerant of None / shape."""
    if not isinstance(data, dict):
        return []
    rows = data.get(key)
    return rows if isinstance(rows, list) else []


def _slug(text: str) -> str:
    """Stable id fragment from free text."""
    out = []
    for ch in str(text).strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "item"


def _node(
    nid,
    kind,
    *,
    title=None,
    text=None,
    source=None,
    durability=None,
    derived=None,
    status=None,
    owner=None,
    labels=None,
    data=None,
):
    """Build a schema-conforming node (only non-empty optional keys are set).

    Provenance/durability fields ride at the top level: `derived` marks a node
    projected FROM other nodes rather than a first-class source row; `durability`
    classifies how long the fact holds (durable-logic / point-in-time); `status`
    and `owner` are surfaced from the source row when present. `derived` is only
    set when True (a False would be noise — absence already means "not derived")."""
    n = {"id": nid, "kind": kind}
    if title:
        n["title"] = title
    if text:
        n["text"] = text
    if source:
        n["source"] = source
    if durability:
        n["durability"] = durability
    if derived:
        n["derived"] = True
    if status:
        n["status"] = status
    if owner:
        n["owner"] = owner
    if labels:
        n["labels"] = [str(x) for x in labels]
    if data:
        n["data"] = data
    return n


# Durability per kind — how long a fact of this kind holds. The durable-logic
# kinds encode standing truth (a decision, a spec, a memory, a glossary term);
# the point-in-time kinds are dated records of a moment (a session, an action,
# an open question, a risk, the roadmap-as-of-now). Concept (derived KG) is
# left durability-less — its lifetime tracks the sessions it was distilled from.
_DURABILITY = {
    "Decision": "durable-logic",
    "Spec": "durable-logic",
    "Memory": "durable-logic",
    "Term": "durable-logic",
    "Session": "point-in-time",
    "ActionItem": "point-in-time",
    "OpenQuestion": "point-in-time",
    "Risk": "point-in-time",
    "Roadmap": "point-in-time",
    "Deliverable": "point-in-time",
    "Story": "point-in-time",
    "Stakeholder": "point-in-time",
    "Dependency": "point-in-time",
    # Source-inventory kinds (#13). A data source's shape — its tables/columns —
    # is standing structural truth, so Source/Entity/Field are durable-logic.
    "Source": "durable-logic",
    "Entity": "durable-logic",
    "Field": "durable-logic",
    # Artifact-pattern kinds (#14). A tracked artifact (and the catalog that
    # indexes it) is a standing deliverable, so Artifact/Catalog are
    # durable-logic.
    "Artifact": "durable-logic",
    "Catalog": "durable-logic",
}


# ----------------------------------------------------------------------------
# Adapters — one per source. Memory (memory/*.md) is a FUTURE slot (issue #3
# B2): the markdown-crawl adapter is deferred and intentionally not built here.
# ----------------------------------------------------------------------------


@adapter
def decisions(root):
    src = "app/decisions.json"
    nodes, edges = [], []
    for d in _rows(_load(root, "app", "decisions.json"), "decisions"):
        if not isinstance(d, dict) or not d.get("title"):
            continue
        nid = "decision:" + _slug(d["title"])
        nodes.append(
            _node(
                nid,
                "Decision",
                title=d.get("title"),
                text=d.get("decision"),
                source=src,
                durability=_DURABILITY.get("Decision"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("date", "session") if d.get(k)},
            )
        )
        if d.get("session"):
            edges.append({"source": nid, "target": "session:" + str(d["session"]), "rel": "decided_in"})
    return nodes, edges


@adapter
def open_questions(root):
    src = "app/open-questions.json"
    nodes, edges = [], []
    for d in _rows(_load(root, "app", "open-questions.json"), "questions"):
        if not isinstance(d, dict) or not d.get("question"):
            continue
        nid = "question:" + _slug(d["question"])
        nodes.append(
            _node(
                nid,
                "OpenQuestion",
                title=d.get("question"),
                text=d.get("context"),
                source=src,
                durability=_DURABILITY.get("OpenQuestion"),
                status=d.get("status"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("date", "session") if d.get(k)},
            )
        )
        if d.get("session"):
            edges.append({"source": nid, "target": "session:" + str(d["session"]), "rel": "raised_in"})
    return nodes, edges


@adapter
def action_items(root):
    src = "app/action-items.json"
    nodes, edges = [], []
    for i, d in enumerate(_rows(_load(root, "app", "action-items.json"), "items")):
        if not isinstance(d, dict) or not d.get("text"):
            continue
        nid = f"action:{i}:{_slug(d['text'])[:40]}"
        nodes.append(
            _node(
                nid,
                "ActionItem",
                text=d.get("text"),
                source=src,
                durability=_DURABILITY.get("ActionItem"),
                owner=d.get("owner"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("date", "session", "session_title") if d.get(k)},
            )
        )
        if d.get("session"):
            edges.append({"source": nid, "target": "session:" + str(d["session"]), "rel": "raised_in"})
    return nodes, edges


@adapter
def sessions(root):
    src = "app/sessions.json"
    nodes = []
    for d in _rows(_load(root, "app", "sessions.json"), "sessions"):
        if not isinstance(d, dict) or not d.get("id"):
            continue
        nodes.append(
            _node(
                "session:" + str(d["id"]),
                "Session",
                title=d.get("title"),
                text=d.get("summary"),
                source=src,
                durability=_DURABILITY.get("Session"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("date", "duration_min") if d.get(k)},
            )
        )
    return nodes, []


@adapter
def specs(root):
    """Plan manifest -> Spec/Story nodes with the authored plan edges.

    The spec tree is the top-down decomposition (phase > epic > feature >
    story, see specs/STORY-STANDARD.md). A leaf `type: story` row becomes a
    first-class `Story` node; the containers above it (phase/epic/feature,
    declared by a `00-*.md`) stay `Spec` workstream nodes. Authored edges ride
    through verbatim: `child_of` (tree), `depends_on` (story frontmatter), and
    `derives_from` provenance from a story to the decision(s) it references
    (`references:` frontmatter -> decision nodes; a reference to an absent
    decision emits no edge, so the empty-state stays connected)."""
    src = "specs/manifest.json"
    nodes, edges = [], []
    for d in _rows(_load(root, "specs", "manifest.json"), "items"):
        if not isinstance(d, dict) or not d.get("id"):
            continue
        nid = "spec:" + str(d["id"])
        kind = "Story" if d.get("type") == "story" else "Spec"
        nodes.append(
            _node(
                nid,
                kind,
                title=d.get("title"),
                source=src,
                durability=_DURABILITY.get(kind),
                status=d.get("status"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("type", "priority", "estimate", "path") if d.get(k)},
            )
        )
        parent = d.get("parent")
        if parent:
            edges.append({"source": nid, "target": "spec:" + str(parent), "rel": "child_of"})
        for dep in d.get("depends_on") or []:
            if dep:
                edges.append({"source": nid, "target": "spec:" + str(dep), "rel": "depends_on"})
        for ref in d.get("references") or []:
            if ref:
                edges.append({"source": nid, "target": "decision:" + _slug(ref), "rel": "derives_from"})
    return nodes, edges


@adapter
def knowledge_graph(root):
    """conflict-kg/v1 nodes -> Concept; KG edges carried through verbatim."""
    src = "app/knowledge_graph.json"
    data = _load(root, "app", "knowledge_graph.json")
    nodes, edges = [], []
    for d in _rows(data, "nodes"):
        if not isinstance(d, dict) or not d.get("id"):
            continue
        nid = "kg:" + str(d["id"])
        extra = {k: v for k, v in d.items() if k not in ("id", "label", "title", "name", "type")}
        extra["subkind"] = "kg"
        if d.get("type"):
            extra.setdefault("kg_type", d["type"])
        nodes.append(
            _node(
                nid,
                "Concept",
                title=d.get("label") or d.get("title") or d.get("name"),
                source=src,
                derived=True,
                data=extra,
            )
        )
    for e in _rows(data, "edges"):
        if not isinstance(e, dict):
            continue
        s = e.get("source") or e.get("from") or e.get("src")
        t = e.get("target") or e.get("to") or e.get("dst")
        if not s or not t:
            continue
        edge = {"source": "kg:" + str(s), "target": "kg:" + str(t)}
        rel = e.get("rel") or e.get("type") or e.get("label")
        if rel:
            edge["rel"] = str(rel)
        edges.append(edge)
    return nodes, edges


@adapter
def glossary(root):
    src = "app/glossary.json"
    nodes = []
    for d in _rows(_load(root, "app", "glossary.json"), "terms"):
        if not isinstance(d, dict) or not d.get("term"):
            continue
        nodes.append(
            _node(
                "term:" + _slug(d["term"]),
                "Term",
                title=d.get("term"),
                text=d.get("definition"),
                source=src,
                durability=_DURABILITY.get("Term"),
                data={k: d[k] for k in ("aliases", "related") if d.get(k)},
            )
        )
    return nodes, []


@adapter
def raid(root):
    """Risks/Assumptions/Issues/Dependencies -> Risk; the R/A/I/D classification
    (the source `type`) is preserved as data.category."""
    src = "app/raid.json"
    nodes = []
    for i, d in enumerate(_rows(_load(root, "app", "raid.json"), "items")):
        if not isinstance(d, dict) or not d.get("title"):
            continue
        data = {k: d[k] for k in ("severity", "mitigation") if d.get(k)}
        if d.get("type"):
            data["category"] = d["type"]
        nodes.append(
            _node(
                f"raid:{i}:{_slug(d['title'])[:40]}",
                "Risk",
                title=d.get("title"),
                text=d.get("detail"),
                source=src,
                durability=_DURABILITY.get("Risk"),
                status=d.get("status"),
                owner=d.get("owner"),
                labels=d.get("labels"),
                data=data,
            )
        )
    return nodes, []


@adapter
def roadmap(root):
    src = "app/roadmap.json"
    nodes = []
    for d in _rows(_load(root, "app", "roadmap.json"), "tracks"):
        if not isinstance(d, dict) or not d.get("product"):
            continue
        nodes.append(
            _node(
                "track:" + _slug(d["product"]),
                "Roadmap",
                title=d.get("product"),
                text=d.get("summary") or d.get("tagline"),
                source=src,
                durability=_DURABILITY.get("Roadmap"),
                data={k: d[k] for k in ("tagline",) if d.get(k)},
            )
        )
    return nodes, []


@adapter
def deliverables(root):
    src = "app/deliverables.json"
    nodes, edges = [], []
    for d in _rows(_load(root, "app", "deliverables.json"), "deliverables"):
        if not isinstance(d, dict) or not (d.get("title") or d.get("id")):
            continue
        did = d.get("id") or _slug(d.get("title"))
        nid = "deliverable:" + str(did)
        nodes.append(
            _node(
                nid,
                "Deliverable",
                title=d.get("title"),
                text=d.get("summary"),
                source=src,
                durability=_DURABILITY.get("Deliverable"),
                status=d.get("status"),
                owner=d.get("owner"),
                labels=d.get("tags"),
                data={k: d[k] for k in ("phase", "category", "type", "date") if d.get(k)},
            )
        )
        for st in d.get("stories") or []:
            edges.append({"source": nid, "target": "story:" + str(st), "rel": "relates_to"})
        for ss in d.get("sessions") or []:
            edges.append({"source": nid, "target": "session:" + str(ss), "rel": "relates_to"})
        for sp in d.get("specs") or []:
            edges.append({"source": nid, "target": "spec:" + str(sp), "rel": "relates_to"})
    return nodes, edges


@adapter
def user_stories(root):
    src = "app/user-stories.json"
    nodes, edges = [], []
    for d in _rows(_load(root, "app", "user-stories.json"), "stories"):
        if not isinstance(d, dict) or not (d.get("id") or d.get("title")):
            continue
        sid = d.get("id") or _slug(d.get("title"))
        nid = "story:" + str(sid)
        nodes.append(
            _node(
                nid,
                "Story",
                title=d.get("title"),
                text=d.get("i_want"),
                source=src,
                durability=_DURABILITY.get("Story"),
                status=d.get("status"),
                labels=d.get("labels"),
                data={k: d[k] for k in ("as_a", "i_want", "so_that", "acceptance", "epic") if d.get(k)},
            )
        )
        if d.get("deliverable"):
            edges.append({"source": nid, "target": "deliverable:" + str(d["deliverable"]), "rel": "relates_to"})
        for ss in d.get("sessions") or []:
            edges.append({"source": nid, "target": "session:" + str(ss), "rel": "relates_to"})
    return nodes, edges


@adapter
def stakeholders(root):
    src = "app/stakeholders.json"
    nodes = []
    for d in _rows(_load(root, "app", "stakeholders.json"), "people"):
        if not isinstance(d, dict) or not d.get("name"):
            continue
        nodes.append(
            _node(
                "person:" + _slug(d["name"]),
                "Stakeholder",
                title=d.get("name"),
                text=d.get("notes"),
                source=src,
                durability=_DURABILITY.get("Stakeholder"),
                data={k: d[k] for k in ("role", "org", "email") if d.get(k)},
            )
        )
    return nodes, []


@adapter
def dependencies(root):
    """Plan dependency graph (app/dependencies.json) -> Concept nodes + edges."""
    src = "app/dependencies.json"
    data = _load(root, "app", "dependencies.json")
    nodes, edges = [], []
    for d in _rows(data, "nodes"):
        if not isinstance(d, dict) or not d.get("id"):
            continue
        nodes.append(
            _node(
                "dep:" + str(d["id"]),
                "Dependency",
                title=d.get("title"),
                source=src,
                durability=_DURABILITY.get("Dependency"),
                status=d.get("status"),
                data={k: d[k] for k in ("type",) if d.get(k)},
            )
        )
    for e in _rows(data, "edges"):
        if not isinstance(e, dict) or not e.get("from") or not e.get("to"):
            continue
        edges.append({"source": "dep:" + str(e["from"]), "target": "dep:" + str(e["to"]), "rel": "depends_on"})
    return nodes, edges


@adapter
def source_inventory(root):
    """Source inventory (app/sources.json, from scripts/ingest_sources.py) ->
    Source / Entity / Field nodes with the structural + provenance edges (#13).

    The pluggable source-ingestion module inventories every data source
    (source -> entity -> field, each with status/owner/provenance). This adapter
    projects that inventory into the brain: a `Source` node per source, an
    `Entity` per table/resource, a `Field` per column/property — wired with
    `has_entity`/`has_field` STRUCTURAL edges (source contains entity contains
    field) and `sourced_by` PROVENANCE edges back to the extractor input each
    node was read from (generalizing das gen-field-catalog.py's resolved_to ->
    edge idea). Empty inventory ({sources:[]}) -> no nodes, so the empty-state
    brain is unchanged."""
    src = "app/sources.json"
    data = _load(root, "app", "sources.json")
    nodes, edges = [], []
    for s in _rows(data, "sources"):
        if not isinstance(s, dict) or not s.get("id"):
            continue
        sid = "source:" + _slug(s["id"])
        nodes.append(
            _node(
                sid,
                "Source",
                title=s.get("title") or s.get("id"),
                source=src,
                durability=_DURABILITY.get("Source"),
                status=s.get("status"),
                owner=s.get("owner"),
                data={k: s[k] for k in ("kind", "provenance") if s.get(k)},
            )
        )
        for ent in s.get("entities") or []:
            if not isinstance(ent, dict) or not ent.get("name"):
                continue
            eid = f"{sid}:entity:{_slug(ent['name'])}"
            nodes.append(
                _node(
                    eid,
                    "Entity",
                    title=ent.get("title") or ent.get("name"),
                    source=src,
                    durability=_DURABILITY.get("Entity"),
                    status=ent.get("status"),
                    owner=ent.get("owner"),
                    data={"name": ent["name"]},
                )
            )
            edges.append({"source": sid, "target": eid, "rel": "has_entity", "class": "structural"})
            for fld in ent.get("fields") or []:
                if not isinstance(fld, dict) or not fld.get("name"):
                    continue
                fid = f"{eid}:field:{_slug(fld['name'])}"
                fdata = {k: fld[k] for k in ("name", "type", "nullable", "is_pk") if fld.get(k) is not None}
                nodes.append(
                    _node(
                        fid,
                        "Field",
                        title=fld.get("name"),
                        source=src,
                        durability=_DURABILITY.get("Field"),
                        status=fld.get("status"),
                        data=fdata,
                    )
                )
                edges.append({"source": eid, "target": fid, "rel": "has_field", "class": "structural"})
    return nodes, edges


@adapter
def artifacts(root):
    """Artifact catalog (analysis/artifacts/catalog.json) -> Catalog / Artifact
    nodes with the catalog membership + session-provenance edges (#14).

    The artifact pattern (docs/primitives/artifact-pattern.md) is the generic
    escape hatch for a bespoke deliverable — a golden record, an identity
    strategy, a timeline, an integration catalog — that does not fit a
    first-class authoring tool: a catalog stub + canonical data JSON + an
    index.html render. This adapter projects the manifest into the brain: one
    `Catalog` node for the manifest, one `Artifact` node per stub, wired with
    `in_catalog` edges (artifact belongs to the catalog) and `relates_to`
    PROVENANCE edges to each session the artifact was distilled from
    (generalizing the das stubs' `source_sessions`). A reference to an absent
    session emits no edge, so the empty-state stays connected. An empty manifest
    ({artifacts:[]}) -> no Artifact nodes, so the empty-state brain is
    unchanged."""
    src = "analysis/artifacts/catalog.json"
    data = _load(root, "analysis", "artifacts", "catalog.json")
    rows = _rows(data, "artifacts")
    if not rows:
        return [], []
    nodes, edges = [], []
    nodes.append(
        _node(
            "catalog:artifacts",
            "Catalog",
            title="Artifacts",
            text="Manifest of standalone analysis artifacts.",
            source=src,
            durability=_DURABILITY.get("Catalog"),
            data={"count": len(rows)},
        )
    )
    for a in rows:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        nid = "artifact:" + _slug(a["id"])
        nodes.append(
            _node(
                nid,
                "Artifact",
                title=a.get("title") or a.get("id"),
                text=a.get("description"),
                source=src,
                durability=_DURABILITY.get("Artifact"),
                data={k: a[k] for k in ("id", "icon", "href", "updated", "type", "source_sessions") if a.get(k)},
            )
        )
        edges.append({"source": nid, "target": "catalog:artifacts", "rel": "in_catalog"})
        for ss in a.get("source_sessions") or []:
            if ss:
                edges.append({"source": nid, "target": "session:" + str(ss), "rel": "relates_to"})
    return nodes, edges


# FUTURE adapter slot (issue #3 · B2): a markdown-crawl adapter over memory/*.md
# emitting `kind: "Memory"` nodes. Deferred — not built in this phase.


# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------


def _meta(nodes: list, edges: list) -> dict:
    """The self-describing envelope header. DETERMINISTIC — version + generator
    are fixed constants and counts are recomputed from the graph, so no timestamp
    or env leaks in (the golden + drift gates compare bytes every run)."""
    return {
        "version": BRAIN_VERSION,
        "generator": GENERATOR,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }


def canonicalize(nodes: list, edges: list) -> tuple[list, list]:
    """The single deterministic ordering contract for a brain graph: nodes
    first-writer-wins by id then sorted; edges sorted by (source, target, rel),
    deduped on that key, and any edge whose endpoints do not both resolve to a
    node dropped (a dangling reference never breaks integrity — same posture as
    aggregate-brains.py). check-brain.py's RECONCILE gate asserts this exact
    shape, so build() AND migrate-brain._restamp() both route through here to
    guarantee they can never drift."""
    nodes_by_id = {}
    for n in nodes:
        nodes_by_id.setdefault(n["id"], n)  # first writer wins, stable
    out_nodes = sorted(nodes_by_id.values(), key=lambda n: n["id"])

    seen = set()
    uniq_edges = []
    for e in sorted(edges, key=lambda e: (e["source"], e["target"], e.get("rel", ""))):
        if e["source"] not in nodes_by_id or e["target"] not in nodes_by_id:
            continue
        key = (e["source"], e["target"], e.get("rel", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq_edges.append(e)
    return out_nodes, uniq_edges


def build(root: str) -> dict:
    """Run every registered adapter and merge into one deterministic graph."""
    nodes = []
    edges = []
    for fn in ADAPTERS:
        try:
            ns, es = fn(root)
        except Exception:
            # An adapter must never sink the whole build — skip a bad source.
            ns, es = [], []
        nodes.extend(ns)
        edges.extend(es)

    nodes, uniq_edges = canonicalize(nodes, edges)
    return {"meta": _meta(nodes, uniq_edges), "nodes": nodes, "edges": uniq_edges}


def main():
    graph = build(ROOT)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1)
    print(f"Wrote {OUT}: {len(graph['nodes'])} node(s), {len(graph['edges'])} edge(s) from {len(ADAPTERS)} adapter(s)")


if __name__ == "__main__":
    main()
