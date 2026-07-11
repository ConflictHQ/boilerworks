#!/usr/bin/env python3
"""Migrate a compiled brain envelope to the current format version (issue #25).

The brain self-describes its format with `meta.version` (gen-brain.py stamps
BRAIN_VERSION). As the template is reused across long-lived engagements the
envelope/node/edge format will evolve; this script upgrades an OLD brain to the
current version so a stored brain never rots out from under the tooling.

How it works — an ordered registry of vN -> vN+1 transforms
-----------------------------------------------------------
Each migration is a small, pure `(envelope) -> envelope` function that takes a
brain at version N and returns it at version N+1, registered with the version it
upgrades FROM:

    @migration("1")          # upgrades a v1 brain to v2
    def v1_to_v2(env): ...

`migrate()` reads `meta.version` (a brain with no meta is treated as the EARLIEST
version — `_EARLIEST` — so a header-less legacy brain still has a path forward),
then applies each registered transform IN ORDER until the brain reaches
CURRENT_VERSION (gen-brain.py's BRAIN_VERSION). Migrations chain: v1->v2->v3.

v1 baseline
-----------
The template ships at v1 with an EMPTY registry — `migrate` is an identity no-op
that simply (re)stamps meta to the current version, since there is no older
format to upgrade from yet. The deliverable this phase is the FRAMEWORK plus the
first version stamp; `_example_v1_to_v2` below is a documented, NON-registered
scaffold showing exactly how the first real migration will be written and tested.

Downgrade policy
----------------
Downgrades are intentionally NOT applied automatically: a vN+1 brain may carry
fields a vN reader cannot represent, so a lossy downgrade is a deliberate, manual
act. Each forward migration documents (in its docstring) whether it is reversible
and how; recover an older brain by regenerating from sources at the older
template SHA, or by hand-reverting per that note. `migrate` refuses to run on a
brain whose version is NEWER than CURRENT (the tooling is older than the data).

Determinism
-----------
A no-op migration restamps meta to the deterministic current header (version +
generator + recomputed counts), so a migrated brain is byte-identical to a fresh
`gen-brain.py` build and passes the golden/drift gates.

CLI
---
    python3 scripts/migrate-brain.py app/brain.json          # in place
    python3 scripts/migrate-brain.py app/brain.json -o out   # to a file
    python3 scripts/migrate-brain.py app/brain.json --stdout # to stdout
    python3 scripts/migrate-brain.py --check app/brain.json  # 0 if current, 2 if stale
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

from config import settings  # noqa: F401  (Phase-0 frozen config singleton)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN = os.path.join(ROOT, "app", "brain.json")

# The version a brain with NO meta block is assumed to be (the earliest format
# the template ever emitted). A header-less legacy brain enters the chain here.
_EARLIEST = "1"


def _load_gen_brain():
    """Load gen-brain.py by file path (its hyphenated name is not importable) —
    the single source of truth for BRAIN_VERSION and the deterministic _meta()."""
    spec = importlib.util.spec_from_file_location("gen_brain", os.path.join(ROOT, "scripts", "gen-brain.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_GEN = _load_gen_brain()
CURRENT_VERSION = _GEN.BRAIN_VERSION


# ----------------------------------------------------------------------------
# Migration registry — ordered vN -> vN+1 transforms
# ----------------------------------------------------------------------------
#
# MIGRATIONS maps a FROM-version string to the transform that upgrades a brain at
# that version to the next one. At v1 it is intentionally empty (no older format
# exists yet); register the first transform the day BRAIN_VERSION becomes "2".

MIGRATIONS: dict[str, callable] = {}


def migration(from_version: str):
    """Register a `(envelope) -> envelope` transform that upgrades a brain FROM
    `from_version` to the next version. Decorated fns run in chained order."""

    def deco(fn):
        MIGRATIONS[str(from_version)] = fn
        return fn

    return deco


# --- EXAMPLE migration scaffold (NOT registered) ----------------------------
#
# This is the template for the first real migration — copy it, register it with
# @migration("1"), bump BRAIN_VERSION to "2" in gen-brain.py, and add a fixture
# to tests/test_migrate_brain.py. It is deliberately left UNREGISTERED so v1
# stays an identity no-op; it exists as executable documentation of the shape.
#
# REVERSIBLE? Yes — drop the added `data.kg_type` field to go back to v1. The
# downgrade is not auto-applied (see module docstring), only documented here.
def _example_v1_to_v2(env: dict) -> dict:
    """EXAMPLE (unregistered): a v1 -> v2 transform that backfills a default
    `data.schema_rev` on every node. Pure: returns a new envelope, mutating a
    shallow copy so the caller's input is untouched."""
    nodes = []
    for n in env.get("nodes") or []:
        m = dict(n)
        data = dict(m.get("data") or {})
        data.setdefault("schema_rev", 2)
        m["data"] = data
        nodes.append(m)
    return {"nodes": nodes, "edges": list(env.get("edges") or [])}


# ----------------------------------------------------------------------------
# Migrate
# ----------------------------------------------------------------------------


def _version_of(env: dict) -> str:
    """The brain's declared version, or `_EARLIEST` for a header-less brain."""
    meta = env.get("meta")
    if isinstance(meta, dict) and meta.get("version"):
        return str(meta["version"])
    return _EARLIEST


def _restamp(env: dict) -> dict:
    """Re-emit the envelope in gen-brain.py's exact {meta, nodes, edges} shape
    with a freshly computed, deterministic meta header at CURRENT_VERSION (version
    + generator + recomputed counts — no timestamp/env, so a no-op migration is
    byte-identical to a fresh gen-brain.py build).

    Canonicalizes through gen-brain.canonicalize() — the SAME sort/dedupe/drop
    contract build() uses — so migrating a non-canonical legacy brain (unsorted
    nodes, duplicate edges) produces output that passes check-brain.py's RECONCILE
    gate. Routing both paths through one helper means they can never drift."""
    nodes, edges = _GEN.canonicalize(list(env.get("nodes") or []), list(env.get("edges") or []))
    meta = {
        "version": CURRENT_VERSION,
        "generator": _GEN.GENERATOR,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }
    return {"meta": meta, "nodes": nodes, "edges": edges}


def needs_migration(env: dict) -> bool:
    """True iff the brain's version is behind CURRENT_VERSION."""
    return _version_of(env) != CURRENT_VERSION


def migrate(env: dict) -> dict:
    """Upgrade a brain envelope to CURRENT_VERSION by applying each registered
    vN -> vN+1 transform in order, then restamp the deterministic meta header.

    Raises ValueError if the brain is NEWER than the tooling, or if the chain
    stalls (a gap in the registry) before reaching the current version."""
    version = _version_of(env)
    if _ver_gt(version, CURRENT_VERSION):
        raise ValueError(
            f"brain meta.version={version!r} is NEWER than this tooling's "
            f"version {CURRENT_VERSION!r}; upgrade the template (downgrades are "
            "not auto-applied — see migrate-brain.py downgrade policy)."
        )
    guard = 0
    while version != CURRENT_VERSION:
        transform = MIGRATIONS.get(version)
        if transform is None:
            raise ValueError(
                f"no migration registered FROM version {version!r} (cannot reach "
                f"{CURRENT_VERSION!r}) — register one with @migration({version!r})."
            )
        env = transform(env)
        version = _next_version(version)
        guard += 1
        if guard > 999:  # impossible-loop guard
            raise ValueError("migration chain did not converge")
    return _restamp(env)


def _ver_gt(a: str, b: str) -> bool:
    """Compare numeric version strings; non-numeric compares lexically."""
    if a.isdigit() and b.isdigit():
        return int(a) > int(b)
    return a > b


def _next_version(v: str) -> str:
    """The version a vN -> vN+1 transform produces (numeric increment)."""
    return str(int(v) + 1) if v.isdigit() else v


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def _serialize(env: dict) -> str:
    """The exact app/brain.json byte shape gen-brain.py emits (indent=1)."""
    return json.dumps(env, indent=1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Migrate a compiled brain envelope to the current format.")
    ap.add_argument("path", nargs="?", default=BRAIN, help="brain JSON to migrate (default app/brain.json)")
    ap.add_argument("-o", "--out", help="write the migrated brain here (default: in place)")
    ap.add_argument("--stdout", action="store_true", help="print the migrated brain to stdout (no file written)")
    ap.add_argument(
        "--check",
        action="store_true",
        help="report only: exit 0 if already current, 2 if a migration is needed (writes nothing)",
    )
    args = ap.parse_args(argv)

    try:
        with open(args.path, encoding="utf-8") as f:
            env = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"migrate-brain: cannot read {args.path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(env, dict):
        print(f"migrate-brain: {args.path} is not a brain envelope object", file=sys.stderr)
        return 1

    if args.check:
        if needs_migration(env):
            print(
                f"stale: {args.path} is at version "
                f"{_version_of(env)!r}, current is {CURRENT_VERSION!r} — run "
                "'make migrate-brain'."
            )
            return 2
        print(f"ok: {args.path} is at the current version {CURRENT_VERSION!r}.")
        return 0

    try:
        migrated = migrate(env)
    except ValueError as exc:
        print(f"migrate-brain: {exc}", file=sys.stderr)
        return 1

    text = _serialize(migrated)
    if args.stdout:
        print(text)
        return 0
    out = args.out or args.path
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    was = _version_of(env)
    if was == CURRENT_VERSION:
        print(f"migrate-brain: {out} already at version {CURRENT_VERSION!r} (restamped, no-op).")
    else:
        print(f"migrate-brain: {out} migrated {was!r} -> {CURRENT_VERSION!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
