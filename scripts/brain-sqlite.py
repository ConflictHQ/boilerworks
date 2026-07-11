#!/usr/bin/env python3
"""Encode app/brain.json as a queryable SQLite db (+ FTS5) and back, losslessly.

The compiled brain ships as app/brain.json (gen-brain.py, #3). This CLI mirrors
it into app/brain.db so the brain can be queried with SQL and full-text search,
and — when a brain outgrows a single diffable JSON blob — serves as the
migration path to a SQLite-canonical (and later Cloudflare D1) store.

WHICH STORE IS CANONICAL is a config setting, not a hardcoded assumption
(settings.brain.store in client.config.json, default "json"):
  - "json"   : app/brain.json is the source of truth (git-tracked, regenerated
               by gen-brain.py). brain.db is a derived, gitignored query cache.
  - "sqlite" : app/brain.db is the source of truth (queried/mutated via `exec`);
               `dump` produces the JSON export/snapshot that gets git-tracked.
  - "both"   : JSON and SQLite are kept in parallel and reconciled by `sync`;
               `check` asserts the two stores are equal (drift gate for #6).

Verbs:
  build [db]      app/brain.json -> brain.db
  dump  [db]      brain.db -> app/brain.json  (LOSSLESS, deterministic ordering)
  query "<SQL>"   read-only SELECT, print rows
  exec  "<SQL>"   mutate brain.db
  sync            reconcile per settings.brain.store (json: canonical->rebuild db;
                  sqlite: canonical->dump json; both: dual-write + assert equal)
  check           build->dump->== AND dump->build->== ; in "both" mode also
                  drift-asserts JSON==SQLite. Non-zero exit on mismatch (#6 gate).
  d1-export [out] emit app/brain.d1.sql — deterministic, D1-executable SQL (schema
                  + data) for `wrangler d1 execute DB --file=...` (#37 edge store)

LOSSLESS + DETERMINISTIC. The `json` column on each table carries the FULL
node/edge object, so round-trip fidelity is independent of the projected
columns. `dump` reproduces exactly what gen-brain.py emits: the {meta, nodes,
edges} envelope — meta first (the self-describing version header, #25; stored in
a single-row `meta` table + PRAGMA user_version so the SQLite schema migrates in
lockstep), then nodes sorted by id, edges by (source, target, rel) (deduped),
json.dump(..., indent=1). The typed columns (label/kind/source_path/src/dst/
type/...) exist only for query + index.

D1-COMPATIBLE SCHEMA — no SQLite-only features that block a future Cloudflare D1
edge target: plain tables + indexes + an FTS5 contentless mirror. (D1 supports
FTS5; if a deployment target ever lacks it, the json column + LIKE still works.)

Run from anywhere:  python3 scripts/brain-sqlite.py build
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

from brain_store import search_haystack  # single source of the search haystack
from config import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_JSON = os.path.join(ROOT, "app", "brain.json")
BRAIN_DB = os.path.join(ROOT, "app", "brain.db")


# ----------------------------------------------------------------------------
# Schema (D1-compatible)
# ----------------------------------------------------------------------------
#
# Column names follow the issue-body envelope (label/derived/durability/...,
# src/dst/type/class) for query ergonomics; app/brain.json conforms to the
# brain-node/brain-edge schemas (title/text/source; source/target/rel). The
# `json` column is the lossless carrier — typed columns are projections that
# stay NULL where the schema has no matching field.

_SCHEMA = """
CREATE TABLE meta (
  k    TEXT PRIMARY KEY,
  json TEXT NOT NULL
);
CREATE TABLE node (
  id          TEXT PRIMARY KEY,
  kind        TEXT,
  label       TEXT,
  derived     TEXT,
  durability  TEXT,
  status      TEXT,
  owner       TEXT,
  source_path TEXT,
  search_text TEXT,
  json        TEXT NOT NULL
);
CREATE TABLE edge (
  id    INTEGER PRIMARY KEY,
  src   TEXT NOT NULL,
  dst   TEXT NOT NULL,
  type  TEXT,
  class TEXT,
  json  TEXT NOT NULL
);
CREATE INDEX idx_node_kind ON node(kind);
CREATE INDEX idx_edge_src  ON edge(src);
CREATE INDEX idx_edge_dst  ON edge(dst);
CREATE INDEX idx_edge_type ON edge(type);
CREATE VIRTUAL TABLE node_fts USING fts5(id, label, kind, headings);
"""


# ----------------------------------------------------------------------------
# Field -> column projection (schema envelope -> issue-body columns)
# ----------------------------------------------------------------------------


def _node_columns(n: dict) -> dict:
    """Project a schema node onto the node table columns. Columns with no source
    field stay NULL; kind-specific extras live inside data and ride in `json`.

    derived/durability/status/owner are first-class node fields (gen-brain.py #3
    stamps them); we read them from the top level, falling back to `data` for any
    older node that still nests status/owner there. `derived` is stored as the
    string '1'/'0' (the column is TEXT) only when the node sets it. `source_path`
    accepts either a bare string source or a {path, locator} object."""
    data = n.get("data") or {}
    src = n.get("source")
    if isinstance(src, dict):
        src = src.get("path")
    return {
        "id": n["id"],
        "kind": n.get("kind"),
        "label": n.get("title"),
        "derived": "1" if n.get("derived") else None,
        "durability": n.get("durability"),
        "status": n.get("status", data.get("status")),
        "owner": n.get("owner", data.get("owner")),
        "source_path": src,
        # Precomputed, already-lowercased haystack the SQLite backend's search()
        # LIKE-matches against, so it returns byte-identical results to the JSON
        # backend (both build it from brain_store.search_haystack).
        "search_text": search_haystack(n),
        "json": _dumps_obj(n),
    }


def _node_fts_row(n: dict) -> tuple:
    """FTS5 row over (id, label, kind, headings). `headings` has no schema field
    — index the node's text there so search() can match body content too."""
    return (n["id"], n.get("title") or "", n.get("kind") or "", n.get("text") or "")


def _edge_columns(e: dict, eid: int) -> dict:
    return {
        "id": eid,
        "src": e["source"],
        "dst": e["target"],
        "type": e.get("rel"),
        "class": e.get("class"),
        "json": _dumps_obj(e),
    }


def _dumps_obj(obj: dict) -> str:
    """Compact, key-order-preserving JSON for the lossless `json` column."""
    return json.dumps(obj, ensure_ascii=False)


# ----------------------------------------------------------------------------
# Canonical ordering (must match gen-brain.py exactly)
# ----------------------------------------------------------------------------


def _sorted_graph(graph: dict) -> dict:
    """The {meta?, nodes, edges} envelope in gen-brain.py's exact emit shape: meta
    first (carried through verbatim when present), nodes by id, edges by (source,
    target, rel), deduped — so dump is byte-equivalent to a fresh build."""
    nodes = sorted((n for n in graph.get("nodes") or [] if n.get("id")), key=lambda n: n["id"])
    seen = set()
    edges = []
    for e in sorted(graph.get("edges") or [], key=lambda e: (e["source"], e["target"], e.get("rel", ""))):
        key = (e["source"], e["target"], e.get("rel", ""))
        if key in seen:
            continue
        seen.add(key)
        edges.append(e)
    out: dict = {}
    if isinstance(graph.get("meta"), dict):
        out["meta"] = graph["meta"]  # meta first — matches gen-brain.py key order
    out["nodes"] = nodes
    out["edges"] = edges
    return out


def _serialize(graph: dict) -> str:
    """The exact app/brain.json byte shape gen-brain.py emits (indent=1)."""
    return json.dumps(_sorted_graph(graph), indent=1)


# ----------------------------------------------------------------------------
# build / dump
# ----------------------------------------------------------------------------


def _load_json(path: str = BRAIN_JSON) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"nodes": [], "edges": []}
    if not isinstance(data, dict):
        return {"nodes": [], "edges": []}
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data


def build(db: str = BRAIN_DB, src: str = BRAIN_JSON) -> str:
    """app/brain.json -> brain.db. Empty/stub graph builds cleanly."""
    graph = _sorted_graph(_load_json(src))
    if os.path.exists(db):
        os.remove(db)
    os.makedirs(os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.executescript(_SCHEMA)
        meta = graph.get("meta")
        if isinstance(meta, dict):
            # Durable + queryable: the full header rides in the meta table; the
            # numeric format version also goes to PRAGMA user_version so the db
            # self-describes its schema generation for in-lockstep migration (#25).
            conn.execute("INSERT INTO meta (k, json) VALUES (?, ?)", ("envelope", _dumps_obj(meta)))
            ver = meta.get("version")
            if isinstance(ver, str) and ver.isdigit():
                conn.execute(f"PRAGMA user_version = {int(ver)}")
        for n in graph["nodes"]:
            cols = _node_columns(n)
            conn.execute(
                "INSERT INTO node (id, kind, label, derived, durability, status, "
                "owner, source_path, search_text, json) VALUES "
                "(:id, :kind, :label, :derived, :durability, :status, :owner, "
                ":source_path, :search_text, :json)",
                cols,
            )
            conn.execute("INSERT INTO node_fts (id, label, kind, headings) VALUES (?,?,?,?)", _node_fts_row(n))
        for i, e in enumerate(graph["edges"]):
            conn.execute(
                "INSERT INTO edge (id, src, dst, type, class, json) VALUES (:id, :src, :dst, :type, :class, :json)",
                _edge_columns(e, i),
            )
        conn.commit()
    finally:
        conn.close()
    return db


def _read_graph(db: str = BRAIN_DB) -> dict:
    """Reconstruct the {meta?, nodes, edges} envelope from the lossless `json`
    columns (meta from its table, re-emitted first so dump byte-matches)."""
    conn = sqlite3.connect(db)
    try:
        meta_row = conn.execute("SELECT json FROM meta WHERE k = 'envelope'").fetchone()
        nodes = [json.loads(r[0]) for r in conn.execute("SELECT json FROM node ORDER BY id")]
        edges = [json.loads(r[0]) for r in conn.execute("SELECT json FROM edge ORDER BY id")]
    finally:
        conn.close()
    out: dict = {}
    if meta_row is not None:
        out["meta"] = json.loads(meta_row[0])
    out["nodes"] = nodes
    out["edges"] = edges
    return out


def dump(db: str = BRAIN_DB, out: str = BRAIN_JSON) -> str:
    """brain.db -> app/brain.json (lossless, deterministic)."""
    text = _serialize(_read_graph(db))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out


# ----------------------------------------------------------------------------
# query / exec
# ----------------------------------------------------------------------------


def query(sql: str, db: str = BRAIN_DB) -> int:
    """Read-only SELECT. Prints header + rows. Refuses non-SELECT statements."""
    if not sql.lstrip().lower().startswith(("select", "with")):
        print("query: only SELECT/WITH statements are allowed (use `exec` to mutate)", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        if cols:
            print("\t".join(cols))
        for row in cur.fetchall():
            print("\t".join("" if v is None else str(v) for v in row))
    finally:
        conn.close()
    return 0


def execute(sql: str, db: str = BRAIN_DB) -> int:
    """Mutate brain.db. Prints rows-affected."""
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(sql)
        conn.commit()
        print(f"OK ({cur.rowcount} row(s) affected)")
    finally:
        conn.close()
    return 0


# ----------------------------------------------------------------------------
# d1-export — emit deterministic, D1-executable SQL (#37)
# ----------------------------------------------------------------------------
#
# Push path for serving the brain from Cloudflare D1: emit the SAME schema +
# data `build` writes to brain.db, but as a single SQL script that
# `wrangler d1 execute DB --file=app/brain.d1.sql` loads into the edge database.
# Deterministic (sorted nodes/edges, stable column order) so the export diffs
# cleanly and the deploy is reproducible. node_fts is contentless/derivable and
# NOT on the D1 search path (LIKE over search_text is — matching _SqliteBackend),
# so it is omitted; the schema stays a strict subset and FTS5-independent.


def _sql_literal(val) -> str:
    """A SQL literal for a column value: NULL, or a single-quote-escaped string."""
    if val is None:
        return "NULL"
    return "'" + str(val).replace("'", "''") + "'"


def _d1_export_sql(src: str = BRAIN_JSON) -> str:
    """The full D1 load script for the brain in `src`, as deterministic SQL text.
    Drops+recreates the tables (idempotent re-push) then inserts meta/nodes/edges
    in canonical order. Mirrors build()'s column projection exactly."""
    graph = _sorted_graph(_load_json(src))
    lines: list[str] = [
        "-- Generated by brain-sqlite.py d1-export (#37). Deterministic; do not edit.",
        "-- Load with: wrangler d1 execute DB --file=app/brain.d1.sql",
        "DROP TABLE IF EXISTS meta;",
        "DROP TABLE IF EXISTS node;",
        "DROP TABLE IF EXISTS edge;",
    ]
    # The non-FTS subset of _SCHEMA (D1 serves search via LIKE over search_text).
    for stmt in _SCHEMA.strip().split(";"):
        s = stmt.strip()
        if not s or "node_fts" in s:
            continue
        lines.append(s + ";")
    meta = graph.get("meta")
    if isinstance(meta, dict):
        lines.append(f"INSERT INTO meta (k, json) VALUES ('envelope', {_sql_literal(_dumps_obj(meta))});")
    node_cols = (
        "id",
        "kind",
        "label",
        "derived",
        "durability",
        "status",
        "owner",
        "source_path",
        "search_text",
        "json",
    )
    for n in graph["nodes"]:
        cols = _node_columns(n)
        vals = ", ".join(_sql_literal(cols[c]) for c in node_cols)
        lines.append(f"INSERT INTO node ({', '.join(node_cols)}) VALUES ({vals});")
    edge_cols = ("id", "src", "dst", "type", "class", "json")
    for i, e in enumerate(graph["edges"]):
        cols = _edge_columns(e, i)
        vals = ", ".join(_sql_literal(cols[c]) for c in edge_cols)
        lines.append(f"INSERT INTO edge ({', '.join(edge_cols)}) VALUES ({vals});")
    return "\n".join(lines) + "\n"


def d1_export(out: str | None = None, src: str = BRAIN_JSON) -> str:
    """Write the D1 load script (default app/brain.d1.sql). Gated at the deploy
    layer on features.brain_d1 + brain.store; the emitter itself is config-free so
    it is testable without D1."""
    out = out or os.path.join(ROOT, "app", "brain.d1.sql")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(_d1_export_sql(src))
    return out


# ----------------------------------------------------------------------------
# sync / check
# ----------------------------------------------------------------------------


def sync() -> int:
    """Reconcile the two stores per settings.brain.store.

    json   : canonical app/brain.json -> (re)build derived brain.db
    sqlite : canonical app/brain.db   -> dump JSON export/snapshot
    both   : dual-write (build from JSON) then assert JSON == dump(db)
    """
    store = settings.brain.store
    if store == "json":
        build()
        print(f"sync[json]: rebuilt {BRAIN_DB} from {BRAIN_JSON}")
        return 0
    if store == "sqlite":
        dump()
        print(f"sync[sqlite]: dumped {BRAIN_JSON} snapshot from {BRAIN_DB}")
        return 0
    if store == "both":
        build()
        on_disk = _read_text(BRAIN_JSON)
        from_db = _serialize(_read_graph(BRAIN_DB))
        if on_disk != from_db:
            print("sync[both]: DRIFT — app/brain.json != dump(brain.db)", file=sys.stderr)
            return 1
        print("sync[both]: JSON and SQLite reconciled (equal)")
        return 0
    print(f"sync: unknown brain.store {store!r} (expected json|sqlite|both)", file=sys.stderr)
    return 2


def check() -> int:
    """Round-trip gate (non-zero exit on any mismatch):

    build -> dump -> ==   (JSON survives a trip through SQLite unchanged)
    dump  -> build -> ==  (SQLite survives a trip through JSON unchanged)
    both mode: also drift-assert on-disk app/brain.json == dump(brain.db)
    """
    tmp_db = BRAIN_DB + ".check"
    tmp_json = BRAIN_JSON + ".check"
    ok = True
    try:
        # Direction 1: JSON -> db -> JSON must equal the canonical serialization.
        canonical = _serialize(_load_json(BRAIN_JSON))
        build(tmp_db, BRAIN_JSON)
        round1 = _serialize(_read_graph(tmp_db))
        if round1 != canonical:
            print("check: FAIL build->dump (JSON not preserved through SQLite)", file=sys.stderr)
            ok = False

        # Direction 2: db -> JSON -> db must yield the same graph.
        with open(tmp_json, "w", encoding="utf-8") as f:
            f.write(round1)
        build(tmp_db, tmp_json)
        round2 = _serialize(_read_graph(tmp_db))
        if round2 != round1:
            print("check: FAIL dump->build (SQLite not preserved through JSON)", file=sys.stderr)
            ok = False

        # both mode: live drift between the committed JSON and the built db.
        if settings.brain.store == "both":
            if not os.path.exists(BRAIN_DB):
                build()
            if _serialize(_read_graph(BRAIN_DB)) != _read_text(BRAIN_JSON):
                print("check: FAIL drift (app/brain.json != dump(brain.db))", file=sys.stderr)
                ok = False
    finally:
        for p in (tmp_db, tmp_json):
            if os.path.exists(p):
                os.remove(p)
    if ok:
        print("check: OK (round-trip lossless both directions)")
        return 0
    return 1


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# ----------------------------------------------------------------------------
# CLI dispatch
# ----------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    verb, rest = argv[0], argv[1:]
    if verb == "build":
        db = rest[0] if rest else BRAIN_DB
        out = build(db)
        print(f"Built {out} from {BRAIN_JSON}")
        return 0
    if verb == "dump":
        db = rest[0] if rest else BRAIN_DB
        out = dump(db)
        print(f"Dumped {out} from {db}")
        return 0
    if verb == "query":
        if not rest:
            print("query: missing SQL argument", file=sys.stderr)
            return 2
        return query(rest[0])
    if verb == "exec":
        if not rest:
            print("exec: missing SQL argument", file=sys.stderr)
            return 2
        return execute(rest[0])
    if verb == "sync":
        return sync()
    if verb == "check":
        return check()
    if verb == "d1-export":
        out = d1_export(rest[0] if rest else None)
        print(f"Wrote {out} from {BRAIN_JSON}")
        return 0
    print(f"unknown verb {verb!r} (build|dump|query|exec|sync|check|d1-export)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
