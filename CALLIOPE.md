# Calliope — Boilerworks
<!-- Agent shim for https://github.com/calliopeai/calliope-cli -->

Primary conventions doc: [`bootstrap.md`](bootstrap.md)

Read it before writing any code. When this file and `bootstrap.md` conflict,
`bootstrap.md` wins.

---

## Project-specific notes

- This repo is three things at once: the Boilerworks **CLI** (PyPI `boilerworks`),
  the template **metarepo** (submodules under `templates/`, primers under
  `primers/`), and a federated **brain node** (`app/brain.json`).
- Python 3.12+ / uv / Ruff / Click / pytest — see `CLAUDE.md` for the CLI
  package map and coding standards.
- Process mandate: `primers/PROCESS.md`. Push order: submodules first, then
  metarepo (`make all-push`).
