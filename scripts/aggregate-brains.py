#!/usr/bin/env python3
"""Aggregate per-submodule sub-brains into one top-level federated brain.

`gen-brain.py` (#3) federates a SINGLE repo: it reads that repo's structured
JSON sources and compiles app/brain.json. Real product builds (maturity Tier
2/3) span a metarepo — a portal repo plus product/infra submodules, each with
its OWN compiled brain — and planning intelligence needs the whole picture in
one queryable graph. This script is the SECOND-LEVEL compiler: it consumes the
already-compiled sub-brains and merges them, rather than re-reading any source.

    sub-brain  (each submodule's app/brain.json — emitted by gen-brain.py)
       └─ aggregate-brains.py  -> one federated app/brain.json (the metarepo)

It is deliberately SEPARATE from gen-brain.py: gen-brain.py owns "one repo's
sources -> that repo's brain"; this owns "many repos' brains -> the metarepo's
brain". The federated output conforms to the SAME envelope schema (schemas/
brain-envelope, $refs brain-node + brain-edge), so the store-agnostic accessor
(brain_store.py, #4) and the kb skill (#8) work over it UNCHANGED. It carries its
OWN `meta` header (#25) — the metarepo's federated brain is a first-class brain
at the current BRAIN_VERSION (sourced from gen-brain.py), so it is just as
version-checkable and migratable as a single-repo brain. Sub-brain meta headers
are NOT merged in; only the federated graph's own header is emitted.

What aggregation does to each sub-brain
---------------------------------------
1. NAMESPACE — every node id is prefixed by its repo, `<repo>/<id>`, and every
   edge's source/target is rewritten the same way. Two submodules can both have a
   `decision:pick-x` node without colliding; ids stay globally unique and the
   origin is legible in the id itself.
2. ANCHOR — a synthetic repo node is emitted per submodule (id `repo:<repo>`,
   kind `Source` — a system-of-record, marked `derived` since it is synthesized,
   not read from a file), and every namespaced node from that repo gets an
   `in_repo` STRUCTURAL edge to it. The repo node is the join handle: walk
   `in_repo` to enumerate a repo's contents, or to hop from a node to its origin.
3. CROSS-REPO LINKS — edges whose endpoints both exist (after namespacing, in any
   repo) are carried through, so a spec authored in repo A can reference code in
   repo B. A sub-brain expresses a cross-repo reference with a BARE (un-prefixed)
   target id `<repo>/<id>` already namespaced to the OTHER repo — those pass
   through verbatim. (A reference to an id that resolves nowhere is dropped, so a
   dangling link never breaks integrity — same posture as gen-brain's adapters.)

Code-KG join slot
-----------------
A code knowledge graph (Navegador) is folded in as JUST ANOTHER sub-brain
source: point `--code-kg <repo>=<path>` (or config `metabrain.code_kg`) at a
conflict-kg/v1 (or {nodes,edges}) json and it is namespaced + anchored exactly
like a submodule's brain, so code entities link to specs/decisions through the
same federated graph.

Empty-state
-----------
The standalone template has NO submodules (Makefile `SUBMODULES` is empty), so a
bare run aggregates nothing and writes a trivial empty federated graph
(`{nodes: [], edges: []}`) — no crash. A federated brain only exists in a
metarepo; it is NOT a tracked/GENERATED artifact of the template.

Determinism: identical ordering contract to gen-brain.py — nodes sorted by id,
edges deduped + sorted by (source, target, rel), json.dump(indent=1).

Usage
-----
    # explicit submodule dirs (what the Makefile passes from $(SUBMODULES)):
    python3 scripts/aggregate-brains.py product-api infra-terraform

    # or read the list from the SUBMODULES env var (Makefile export):
    SUBMODULES="product-api infra" python3 scripts/aggregate-brains.py

    # fold a code KG in as another source:
    python3 scripts/aggregate-brains.py api --code-kg api=../navegador/kg.json

    # choose the output (default: app/brain.json under the metarepo root):
    python3 scripts/aggregate-brains.py api --out app/brain.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os

from config import settings  # noqa: F401  (Phase-0 frozen config singleton)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "brain.json")


def _load_gen_brain():
    """Load gen-brain.py by file path (hyphenated name is not importable) for the
    shared BRAIN_VERSION + deterministic _meta() — the federated brain stamps the
    same version surface as a single-repo brain (#25)."""
    spec = importlib.util.spec_from_file_location("gen_brain", os.path.join(ROOT, "scripts", "gen-brain.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_GEN = _load_gen_brain()
GENERATOR = "aggregate-brains"

# Where each submodule keeps its compiled sub-brain (gen-brain.py's output).
SUB_BRAIN = ("app", "brain.json")

# The synthetic repo anchor: a system-of-record node per repo. `Source` is the
# closest first-class kind (a repo IS a source of nodes); it is `derived` because
# it is synthesized by the aggregator, not read from a source file.
_REPO_KIND = "Source"
_IN_REPO_REL = "in_repo"


def _load(path: str):
    """Read a JSON file. Missing/invalid -> None (never raises). utf-8-sig tolerates
    (and strips) an optional leading BOM so a BOM'd sub-brain is not silently
    dropped as a parse error."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _repo_name(submodule_dir: str) -> str:
    """Stable repo namespace from a submodule path — its basename, no slashes.

    `product/api` and `../api` both namespace to `api`. The namespace must not
    contain `/` (the id separator) so `<repo>/<id>` parses unambiguously."""
    name = os.path.basename(os.path.normpath(submodule_dir)) or submodule_dir
    return name.replace("/", "-")


def _ns(repo: str, nid: str) -> str:
    """Namespace a node id by repo. An id ALREADY namespaced (`<other>/...`) is
    a deliberate cross-repo reference and passes through untouched."""
    if "/" in str(nid):
        return str(nid)
    return f"{repo}/{nid}"


def _sub_brain(graph, repo: str, source_path: str | None = None) -> tuple[list[dict], list[dict]]:
    """Project one repo's compiled brain into the federated namespace.

    Returns (nodes, edges): every node id prefixed with `<repo>/`, a synthetic
    `repo:<repo>` anchor node, every edge endpoint rewritten, and an `in_repo`
    edge from each of the repo's own nodes to its anchor.

    The anchor carries a `source` — the repo-relative path of the sub-brain it was
    synthesized from (`<sub>/app/brain.json`, or the code-KG json) — so
    check-brain.py's provenance rule is satisfied by a genuinely traceable,
    on-disk path INDEPENDENT of features.authoring (the authoring carve-out is for
    portal/agent-authored content, not aggregator-synthesized structural anchors).
    `derived` stays true because the node is synthesized, not read row-by-row from
    that file."""
    if not isinstance(graph, dict):
        return [], []
    repo_id = f"repo:{repo}"
    anchor: dict = {
        "id": repo_id,
        "kind": _REPO_KIND,
        "title": repo,
        "text": f"Submodule '{repo}' — federated sub-brain.",
        "derived": True,
        "data": {"repo": repo},
    }
    if source_path:
        anchor["source"] = source_path
    nodes: list[dict] = [anchor]
    edges: list[dict] = []
    for n in graph.get("nodes") or []:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        m = dict(n)
        m["id"] = _ns(repo, n["id"])
        nodes.append(m)
        # Anchor only the repo's OWN nodes (not pass-through cross-repo ids).
        if m["id"].startswith(f"{repo}/"):
            edges.append({"source": m["id"], "target": repo_id, "rel": _IN_REPO_REL, "class": "structural"})
    for e in graph.get("edges") or []:
        if not isinstance(e, dict) or not e.get("source") or not e.get("target"):
            continue
        m = dict(e)
        m["source"] = _ns(repo, e["source"])
        m["target"] = _ns(repo, e["target"])
        edges.append(m)
    return nodes, edges


def _normalize_kg(graph):
    """Accept a conflict-kg/v1 code-KG (Navegador) shape and return a brain-ish
    {nodes, edges}: KG edges may name endpoints `from`/`to`/`src`/`dst` and a
    relation `type`/`label` — normalize to source/target/rel so the code KG
    folds in as just another sub-brain."""
    if not isinstance(graph, dict):
        return {"nodes": [], "edges": []}
    edges = []
    for e in graph.get("edges") or []:
        if not isinstance(e, dict):
            continue
        s = e.get("source") or e.get("from") or e.get("src")
        t = e.get("target") or e.get("to") or e.get("dst")
        if not s or not t:
            continue
        m = {"source": str(s), "target": str(t)}
        rel = e.get("rel") or e.get("type") or e.get("label")
        if rel:
            m["rel"] = str(rel)
        edges.append(m)
    return {"nodes": graph.get("nodes") or [], "edges": edges}


def aggregate(sources: list[tuple]) -> dict:
    """Merge namespaced sub-brains into one deterministic federated graph.

    `sources` is a list of (repo_namespace, sub_brain_graph[, source_path]) — the
    optional third element is the repo-relative path the sub-brain was loaded from
    (anchors the synthetic repo node's provenance so check-brain's rule holds with
    authoring off); a 2-tuple leaves the anchor sourceless. Empty -> a trivial
    empty graph. Mirrors gen-brain.py's merge exactly: nodes first-writer-wins by
    id then sorted; edges deduped by (source, target, rel) then sorted; integrity
    preserved by dropping any edge whose endpoints are not both present."""
    nodes_by_id: dict[str, dict] = {}
    edges: list[dict] = []
    for src in sources:
        repo, graph = src[0], src[1]
        source_path = src[2] if len(src) > 2 else None
        ns, es = _sub_brain(graph, repo, source_path)
        for n in ns:
            nodes_by_id.setdefault(n["id"], n)  # first writer wins, stable
        edges.extend(es)

    # Drop edges whose endpoints do not both resolve — a dangling cross-repo
    # reference never breaks integrity (same posture as gen-brain's adapters).
    ids = set(nodes_by_id)
    edges = [e for e in edges if e["source"] in ids and e["target"] in ids]

    nodes = sorted(nodes_by_id.values(), key=lambda n: n["id"])
    seen = set()
    uniq_edges = []
    for e in sorted(edges, key=lambda e: (e["source"], e["target"], e.get("rel", ""))):
        key = (e["source"], e["target"], e.get("rel", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq_edges.append(e)
    # The federated brain's OWN deterministic header (#25): the metarepo's version
    # at the shared BRAIN_VERSION, generated by this aggregator, counts recomputed.
    meta = {
        "version": _GEN.BRAIN_VERSION,
        "generator": GENERATOR,
        "counts": {"nodes": len(nodes), "edges": len(uniq_edges)},
    }
    return {"meta": meta, "nodes": nodes, "edges": uniq_edges}


def _collect(submodules: list[str], code_kg: list[str]) -> list[tuple[str, dict, str | None]]:
    """Load each submodule's sub-brain + each code-KG into (repo, graph, source)
    triples — `source` is the repo-relative path the graph came from, used as the
    synthetic anchor's provenance.

    A submodule with no compiled sub-brain yet (app/brain.json absent) is
    skipped cleanly — federate what exists, never crash on a missing one."""
    sources: list[tuple[str, dict, str | None]] = []
    for sub in submodules:
        repo = _repo_name(sub)
        rel = os.path.join(sub, *SUB_BRAIN)
        graph = _load(os.path.join(ROOT, sub, *SUB_BRAIN))
        if isinstance(graph, dict):
            sources.append((repo, graph, rel))
    for spec in code_kg:
        repo, _, path = spec.partition("=")
        repo, path = repo.strip(), path.strip()
        if not repo or not path:
            continue
        full = path if os.path.isabs(path) else os.path.join(ROOT, path)
        graph = _load(full)
        if isinstance(graph, dict):
            # A code-KG outside the repo tree (absolute, or a `..` path) has no
            # repo-relative on-disk provenance; leave source unset rather than
            # stamp a path check-brain can't resolve under ROOT.
            rel = None if os.path.isabs(path) or path.startswith("..") else path
            sources.append((_repo_name(repo), _normalize_kg(graph), rel))
    return sources


def _submodules_from_args(args) -> list[str]:
    """Submodule list precedence: positional args, then $SUBMODULES (the Makefile
    export), then config `metabrain.submodules`. Empty -> empty-state."""
    if args.submodules:
        return args.submodules
    env = os.environ.get("SUBMODULES", "").split()
    if env:
        return env
    try:
        cfg = settings.metabrain.get("submodules", [])
    except AttributeError:
        cfg = []
    return [str(s) for s in (cfg or [])]


def _code_kg_from_args(args) -> list[str]:
    """Code-KG `<repo>=<path>` specs: CLI flags, then config `metabrain.code_kg`
    (a {repo: path} map)."""
    if args.code_kg:
        return args.code_kg
    try:
        cfg = settings.metabrain.get("code_kg", {})
    except AttributeError:
        cfg = {}
    if isinstance(cfg, dict):
        return [f"{r}={p}" for r, p in cfg.items() if r and p]
    return []


def main():
    ap = argparse.ArgumentParser(description="Aggregate submodule sub-brains into one federated brain.")
    ap.add_argument("submodules", nargs="*", help="submodule directories (default: $SUBMODULES or config)")
    ap.add_argument(
        "--code-kg",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help="fold a code KG json in as another sub-brain source",
    )
    ap.add_argument("--out", default=OUT, help="output path (default app/brain.json)")
    args = ap.parse_args()

    submodules = _submodules_from_args(args)
    code_kg = _code_kg_from_args(args)
    sources = _collect(submodules, code_kg)

    # Non-destructive guard: with no sub-brains (the standalone single-repo
    # template — SUBMODULES empty), there is nothing to federate. Do NOT write,
    # so we never clobber gen-brain.py's authoritative single-repo app/brain.json
    # with an empty graph. Aggregation only writes when it has real sub-brains.
    if not sources:
        print(
            "aggregate-brains: no sub-brains found (no submodules) — nothing "
            "to federate; leaving app/brain.json (gen-brain.py's single-repo "
            "output) untouched."
        )
        return 0

    graph = aggregate(sources)

    out = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1)
    print(f"Wrote {out}: {len(graph['nodes'])} node(s), {len(graph['edges'])} edge(s) from {len(sources)} sub-brain(s)")


if __name__ == "__main__":
    main()
