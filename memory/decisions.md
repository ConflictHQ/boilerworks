# Decisions

Cross-template decisions, newest first. Mirror durable entries into
`app/decisions.json` so they federate into the brain.

## 2026-07-11 — CLI repo doubles as metarepo + federated brain node

The `ConflictHQ/boilerworks` repo stays the published CLI package and
additionally becomes:

- **the boilerworks metarepo** — all 36 `boilerworks-*` template repos pinned
  as git submodules under `templates/` (internal metarepo pattern: `bootstrap` / `pin` /
  `sync` / `all-status` / `all-push`, submodules pushed before the parent),
  with `primers/` folded in as the canonical home of the process and per-stack
  conventions docs;
- **a federated brain node** — the project-brain engine (`gen-brain.py`,
  `aggregate-brains.py`, `brain_store.py`, `brain-sqlite.py`,
  `check-brain.py`, `migrate-brain.py` + the brain-* schemas) instantiated
  here, sources seeded from `templates.yaml` (via `gen-template-kg.py`),
  decisions, and a glossary; `app/brain.json` compiled deterministically and
  committed so a parent aggregator (conflict-brain) can federate it at the
  pinned SHA, namespaced `boilerworks/…`.

Rationale: one control surface for the template fleet, and the ecosystem's
knowledge becomes queryable through the same brain interface as every other
CONFLICT repo. (Issues #24, #25.)
