#!/usr/bin/env python3
"""Project the template catalogue into a knowledge graph (conflict-kg/v1).

boilerworks/data/templates.yaml is the machine-readable source of truth for
the catalogue. This generator projects it into app/knowledge_graph.json — the
{format, nodes, edges} conflict-kg/v1 envelope — so the brain compiler
(scripts/gen-brain.py, knowledge_graph adapter) folds the catalogue into
app/brain.json as Concept nodes and the metarepo becomes a queryable node in
the federated brain.

Graph shape
-----------
- One node per template: id `template:<name>`, type = its size class
  (full / micro / edge), plus the catalogue props (language, backend,
  frontend, status, best_for, repo). The props are extra keys beyond the
  strict kg-node schema; the brain adapter carries them into Concept.data.
- One node per language: id `language:<lang>`, type `language`.
- One node per size class: id `size:<size>`, type `size-class`.
- One shared concept: id `concept:shared-nextjs-frontend` — every *-nextjs
  template shares the same Next.js frontend (primers/NEXTJS_FRONTEND.md).
- Edges: template -> language (written_in), template -> size class (sized),
  *-nextjs template -> shared frontend concept (uses).

Determinism: nodes sorted by id, edges by (source, target, type), indent=1 —
no timestamps, no randomness, byte-stable across runs.

Run from anywhere:  uv run python scripts/gen-template-kg.py
"""

from __future__ import annotations

import json
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(ROOT, "boilerworks", "data", "templates.yaml")
OUT = os.path.join(ROOT, "app", "knowledge_graph.json")

SHARED_NEXTJS = "concept:shared-nextjs-frontend"

_SIZE_TITLES = {
    "full": "Full (complete application platform)",
    "micro": "Micro (lightweight service)",
    "edge": "Edge (Cloudflare-first)",
}


def build(templates: list[dict]) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    nodes[SHARED_NEXTJS] = {
        "id": SHARED_NEXTJS,
        "name": "Shared Next.js frontend",
        "type": "concept",
        "descriptions": ["The single Next.js frontend shared by every *-nextjs template (primers/NEXTJS_FRONTEND.md)."],
    }

    for t in templates:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        name = str(t["name"])
        size = str(t.get("size", "")) or "unsized"
        lang = str(t.get("language", "")) or "unknown"
        tid = f"template:{name}"

        node = {
            "id": tid,
            "name": name,
            "type": size,
            "language": lang,
            "repo": t.get("repo", ""),
            "status": t.get("status", ""),
        }
        for key in ("backend", "frontend", "best_for"):
            if t.get(key):
                node[key] = t[key]
        if t.get("description"):
            node["descriptions"] = [t["description"]]
        nodes[tid] = node

        lid = f"language:{lang}"
        nodes.setdefault(lid, {"id": lid, "name": lang, "type": "language"})
        edges.append({"source": tid, "target": lid, "type": "written_in"})

        sid = f"size:{size}"
        nodes.setdefault(sid, {"id": sid, "name": _SIZE_TITLES.get(size, size), "type": "size-class"})
        edges.append({"source": tid, "target": sid, "type": "sized"})

        if name.endswith("-nextjs"):
            edges.append({"source": tid, "target": SHARED_NEXTJS, "type": "uses"})

    return {
        "format": "conflict-kg/v1",
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["source"], e["target"], e["type"])),
    }


def main() -> None:
    with open(CATALOGUE, encoding="utf-8") as f:
        templates = yaml.safe_load(f) or []
    graph = build(templates)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1)
    print(f"Wrote {OUT}: {len(graph['nodes'])} node(s), {len(graph['edges'])} edge(s)")


if __name__ == "__main__":
    main()
