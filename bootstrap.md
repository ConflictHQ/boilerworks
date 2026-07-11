# Boilerworks — workspace bootstrap

Canonical entry point for conventions in this repo. Agent shims (`CLAUDE.md`,
`AGENTS.md`) point here; when any document conflicts with this one, this one
wins. The process mandate is [`primers/PROCESS.md`](primers/PROCESS.md) — read
it before contributing.

## What this repo is

Three things, one control surface:

1. **The Boilerworks CLI** — a Python package published to PyPI as
   `boilerworks` (Click + Questionary + Rich). Production-ready project
   templates, assembled in seconds. See `CLAUDE.md` for the CLI stack detail.
2. **The boilerworks metarepo** — every `ConflictHQ/boilerworks-*` template
   repo pinned as a git submodule under `templates/`, so the whole template
   fleet is versioned, synced, and released from one place.
3. **A federated brain node** — the repo compiles its structured sources
   (`app/*.json`) into `app/brain.json`, a queryable property graph a parent
   aggregator (e.g. the CONFLICT company brain) federates at the pinned SHA.

## Workspace layout

```
boilerworks/          # the Python package (CLI, wizard, generator, registry, MCP server)
  data/templates.yaml #   ← machine-readable template registry, single source of truth
templates/            # every boilerworks-* template repo as a pinned submodule
primers/              # canonical conventions docs: PROCESS.md, CATALOGUE.md,
                      #   RELEASE_CHECKLIST.md, PRIMER_TEMPLATE.md, NEXTJS_FRONTEND.md,
                      #   plus one <template>/PRIMER.md per stack
app/                  # brain node sources + compiled artifacts
  decisions.json      #   standing decisions (authored)
  glossary.json       #   ecosystem terms (authored)
  knowledge_graph.json#   conflict-kg/v1 projection of templates.yaml (generated: make kg)
  brain.json          #   the compiled brain (generated: make brain, committed)
scripts/              # brain engine (gen-brain, aggregate-brains, brain_store,
                      #   brain-sqlite, check-brain, migrate-brain, config) +
                      #   gen-template-kg.py + gen_skill_catalogue.py
schemas/              # brain-envelope / brain-node / brain-edge JSON Schemas
skill/                # Claude Code skill (catalogue section generated from templates.yaml)
memory/               # cross-template decisions log (memory/decisions.md)
tests/                # pytest suite (CLI + brain pipeline)
```

`boilerworks/data/templates.yaml` is the **only** machine-readable registry.
The skill catalogue (`scripts/gen_skill_catalogue.py`) and the knowledge graph
(`scripts/gen-template-kg.py`) are generated from it — never hand-edit their
outputs.

## Metarepo workflow

Submodules live at `templates/<short-name>` (repo name minus the
`boilerworks-` prefix), pinned to exact SHAs, `https://` URLs in `.gitmodules`.
Eight are private (`django-internal`, `hugo-be`, `mobile`, `mobile-e2e`,
`new-cms`, `site`, `storybook`, `typeforms`); `make bootstrap` warns and
continues when it cannot clone them, so an unauthenticated checkout still
bootstraps the public fleet.

```sh
make bootstrap        # init/update all submodules to their pinned SHAs (private failures warn)
make pin              # force initialized submodules back to the pinned SHAs
make sync             # pull every initialized submodule's tip (--remote --merge); review, then stage
make all-status       # git status across metarepo + submodules
make all-push         # push submodules FIRST, then the metarepo
make sub-status SUB=django-nextjs   # single-submodule ops: sub-status / sub-pull / sub-push
```

**Push order is law**: submodules first, then the parent — a pinned SHA must
never reference an unpushed commit. `make all-push` encodes this; don't push
the metarepo by hand while a submodule pin is ahead of its remote.

Updating a pin: work inside `templates/<name>` (or `make sub-pull`), push the
submodule, then `git add templates/<name>` and commit the metarepo pointer.

## The brain

This repo is a **brain node**: a self-contained repo whose knowledge compiles
into one deterministic graph artifact.

**Node contract.** `app/brain.json` is the {meta, nodes, edges} envelope
defined by `schemas/brain-envelope.schema.json` (nodes/edges conform to
`brain-node` / `brain-edge`). `meta.version` self-describes the format
(`scripts/migrate-brain.py` upgrades stale brains). The file is deterministic
— nodes sorted by id, edges deduped and sorted, `indent=1` — and **committed**,
so any consumer at a pinned SHA gets a consumable graph without running
anything.

```sh
make kg               # templates.yaml -> app/knowledge_graph.json (conflict-kg/v1)
make brain            # app/* sources -> app/brain.json (runs kg first)
make brain-db         # derived SQLite + FTS5 query cache app/brain.db (gitignored)
make check-brain      # provenance / integrity / canonical-ordering gate
make aggregate-brain  # federate submodule sub-brains (skips templates without app/brain.json)
```

**Sources.** `gen-brain.py` is an adapter registry — every `app/*.json` source
maps to first-class node kinds (Decision, Term, Concept, …). Adapters tolerate
missing sources, so the node compiles from whatever exists. Today's sources:
decisions, glossary, and the template knowledge graph.

**Aggregation.** `make aggregate-brain` federates any submodule that carries
its own compiled `app/brain.json`, namespacing ids as `<repo>/<id>` and
anchoring each repo's nodes to a synthetic `repo:<name>` node via `in_repo`
edges. Templates without a brain are skipped cleanly; with none, it is a no-op
that leaves the single-repo brain untouched.

**Upward federation.** A parent metarepo (conflict-brain) consumes this node
the same way: it reads this repo's committed `app/brain.json` at the pinned
SHA and namespaces everything under `boilerworks/…`. Nothing here needs to
know it is being federated — emit a valid brain, keep it committed, and the
parent's `make aggregate-brain` does the rest.

## Quality bar

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

All three green before every push (CI runs the same). Template submodules are
excluded from ruff — each template repo lints and tests in its own CI. See
`primers/PROCESS.md` for the full process mandate and
`primers/RELEASE_CHECKLIST.md` for what must be true before a template ships.

## Memory

Cross-template decisions are logged in [`memory/decisions.md`](memory/decisions.md)
(newest first) and mirrored as structured entries in `app/decisions.json` so
they federate into the brain.
