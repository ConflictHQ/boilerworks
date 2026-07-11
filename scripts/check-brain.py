#!/usr/bin/env python3
"""Validate app/brain.json — the no-new-data CI gate for the compiled brain.

Asserts the brain is a faithful projection of the JSON sources, not an authored
artifact:

  1. PROVENANCE  — every node has a resolvable `source` that exists under ROOT
                   (a bare string path, or {path: ...}), unless it is flagged
                   `derived: true`. Nothing floats free.
  2. INTEGRITY   — node ids are unique; every edge `source`/`target` references a
                   real node.
  3. RECONCILE   — the brain is canonically ordered (nodes sorted by id, edges
                   deduped + sorted) exactly as gen-brain.py emits, so a stale or
                   hand-edited brain is caught. Recomputed counts are reported.
                   When `brain.store == "both"` the JSON store is additionally
                   reconciled against the SQLite store (round-trip lossless).

The template brain envelope is the {meta, nodes, edges} shape gen-brain.py emits;
edges use source/target/rel (not src/dst/type). This gate reads those field names
and recomputes node/edge counts rather than trusting meta.counts. It DOES read
meta.version: a brain whose version is older than the current BRAIN_VERSION is
refused with a pointer to `make migrate-brain` (#25), so the pipeline never
operates on an out-of-version brain.

Run from repo root:  python3 scripts/check-brain.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from config import settings

ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "app" / "brain.json"


def _brain_version() -> str:
    """The current authoritative envelope version — the single source of truth in
    gen-brain.py (loaded by file path since the script name is hyphenated)."""
    spec = importlib.util.spec_from_file_location("gen_brain", ROOT / "scripts" / "gen-brain.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BRAIN_VERSION


def _source_path(node: dict) -> str | None:
    """Resolve a node's source to a repo-relative path string, or None.

    The template schema permits `source` to be a bare string (e.g.
    'app/decisions.json') or an object {path, locator}.
    """
    src = node.get("source")
    if isinstance(src, str):
        return src or None
    if isinstance(src, dict):
        return src.get("path")
    return None


def _canonical(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    """Mirror gen-brain.py's emit ordering: nodes sorted by id, edges deduped
    (by source/target/rel) then sorted."""
    nodes_sorted = sorted(nodes, key=lambda n: n.get("id", ""))
    seen = set()
    deduped = []
    for e in edges:
        key = (e.get("source"), e.get("target"), e.get("rel"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    edges_sorted = sorted(deduped, key=lambda e: (e.get("source", ""), e.get("target", ""), e.get("rel", "")))
    return nodes_sorted, edges_sorted


def main() -> int:
    b = json.loads(BRAIN.read_text(encoding="utf-8"))
    nodes, edges = b["nodes"], b["edges"]
    errors: list[str] = []

    # 0. VERSION — refuse an out-of-version brain before anything else, pointing
    # at the migration command (#25). A header-less brain (no meta, e.g. a freshly
    # aggregated metarepo brain) is tolerated; only a meta.version that is present
    # and BEHIND the current envelope version is a hard stop.
    current = _brain_version()
    meta = b.get("meta")
    found = meta.get("version") if isinstance(meta, dict) else None
    if found is not None and str(found) != current:
        print(f"Brain validation FAILED: brain meta.version={found!r} is not the current envelope version {current!r}.")
        print("  Run 'make migrate-brain' to upgrade app/brain.json to the current format, then re-run this gate.")
        return 1

    # The derived: true carve-out (portal/agent-authored records, #38) is allowed
    # ONLY when the writable authoring layer is on. With authoring OFF a sourceless
    # `derived` node is orphan author-content and fails the gate — so the empty-
    # state brain (0 derived nodes) stays green and no unprovenanced content can
    # slip in unless the engagement has explicitly opted into authoring.
    authoring_on = bool(settings.features.authoring)

    # 1. PROVENANCE + unique ids
    ids: set[str] = set()
    kind_counts: dict[str, int] = {}
    for n in nodes:
        nid = n.get("id")
        if nid in ids:
            errors.append(f"INTEGRITY: duplicate node id {nid!r}")
        ids.add(nid)
        kind_counts[n.get("kind")] = kind_counts.get(n.get("kind"), 0) + 1
        path = _source_path(n)
        derived_ok = bool(n.get("derived")) and authoring_on
        if not path and not derived_ok:
            if n.get("derived"):
                errors.append(
                    f"PROVENANCE: node {nid!r} is derived (portal/agent-authored) but "
                    f"features.authoring is off — enable authoring or give it a source"
                )
            else:
                errors.append(f"PROVENANCE: node {nid!r} has no source and is not derived")
        if path and not (ROOT / path).exists():
            errors.append(f"PROVENANCE: node {nid!r} source path does not exist: {path}")

    # 2. INTEGRITY — edges reference real nodes
    for e in edges:
        if e.get("source") not in ids:
            errors.append(f"INTEGRITY: edge -> {e.get('target')!r} has missing source: {e.get('source')!r}")
        if e.get("target") not in ids:
            errors.append(f"INTEGRITY: edge {e.get('source')!r} -> has missing target: {e.get('target')!r}")

    # 3. RECONCILE — brain is canonically ordered as gen-brain.py emits.
    nodes_sorted, edges_sorted = _canonical(nodes, edges)
    if [n.get("id") for n in nodes] != [n.get("id") for n in nodes_sorted]:
        errors.append("RECONCILE: nodes are not sorted by id (run 'make brain' to regenerate)")
    if len(edges_sorted) != len(edges):
        errors.append(f"RECONCILE: edges contain {len(edges) - len(edges_sorted)} duplicate(s) (run 'make brain')")
    elif [(e.get("source"), e.get("target"), e.get("rel")) for e in edges] != [
        (e.get("source"), e.get("target"), e.get("rel")) for e in edges_sorted
    ]:
        errors.append("RECONCILE: edges are not deduped/sorted as gen-brain emits (run 'make brain')")

    # 3b. STORE reconcile — in 'both' mode JSON must round-trip with SQLite.
    store = settings.brain.store
    if store == "both" and not errors:
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "brain-sqlite.py"), "check"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:  # noqa: BLE001 - surface the round-trip failure
            errors.append(f"RECONCILE: brain.store='both' JSON<->SQLite round-trip failed: {exc.stderr.strip()}")

    if errors:
        print(f"Brain validation FAILED ({len(errors)} issue(s)):")
        for e in errors[:40]:
            print(f"  - {e}")
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
        return 1

    derived = sum(1 for n in nodes if n.get("derived"))
    print(
        f"OK: brain valid — {len(nodes)} nodes ({derived} derived), {len(edges)} edges; "
        f"every node sourced, every edge connects real nodes, canonically ordered (store={store})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
