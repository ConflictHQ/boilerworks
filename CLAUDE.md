# Claude — Boilerworks

Read [`bootstrap.md`](bootstrap.md) first — it is the canonical entry point for
this workspace: the repo is the Boilerworks **CLI** + the template **metarepo**
(submodules under `templates/`, primers under `primers/`) + a federated
**brain node** (`app/brain.json`). Metarepo workflow, brain contract, push
order, and the process mandate (`primers/PROCESS.md`) all live there. When this
file and `bootstrap.md` conflict, `bootstrap.md` wins.

The rest of this file covers the CLI package specifically.

This repo is the **Boilerworks CLI** — a Python package published to PyPI as `boilerworks`.
It is NOT a web application. It is a command-line tool built with Click, Questionary, and Rich.

---

## Stack

- **Language**: Python 3.12+
- **CLI framework**: Click 8+
- **Interactive prompts**: Questionary 2+
- **Output**: Rich 13+ (tables, panels, progress bars)
- **Manifest validation**: Pydantic v2
- **Template rendering**: string replacement (not Jinja2)
- **Git operations**: subprocess (git CLI) + GitPython
- **Config**: PyYAML 6+
- **Package manager**: uv (not pip)
- **Lint + format**: Ruff (not flake8/black/isort)
- **Tests**: pytest with coverage

## Package layout

```
boilerworks/         # Python package
  __init__.py        # __version__ = "0.3.0"
  cli.py             # Click group: setup, init, bootstrap, list
  wizard.py          # Questionary prompts → boilerworks.yaml
  generator.py       # Clone → render → wire → git init
  bootstrap.py       # Terraform stub (v2)
  manifest.py        # Pydantic models for boilerworks.yaml
  registry.py        # Load + query templates.yaml
  renderer.py        # String replacement in cloned files
  console.py         # Rich output helpers
  mcp_server.py      # MCP server exposing the CLI as agent tools
  data/
    templates.yaml   # All 27 templates with metadata
skill/
  skill.md           # Claude Code skill (catalogue section is generated)
scripts/
  gen_skill_catalogue.py  # regenerates the skill.md catalogue from templates.yaml
tests/
  conftest.py
  test_cli.py
  test_manifest.py
  test_registry.py
  test_renderer.py
  test_generator.py
  test_console.py
  test_wizard.py
```

## Running locally

```bash
uv sync                     # install deps
uv run boilerworks --help   # verify install
make lint                   # ruff check + format --check
make test                   # pytest with coverage
make format                 # ruff fix + format
```

## Adding a template

Edit `boilerworks/data/templates.yaml`. Add an entry following the existing schema.
Regenerate the skill catalogue: `uv run python scripts/gen_skill_catalogue.py`.
Run `make test` — `test_registry.py` catches count mismatches and
`test_skill_catalogue.py` catches skill.md drift.

## MCP server

`boilerworks/mcp_server.py` exposes the CLI as MCP tools (`list_templates`,
`get_template`, `search_templates`, `create_manifest`, `validate_manifest`,
`dry_run`, `init_project`). The `mcp` dependency is an optional extra:

```bash
pip install 'boilerworks[mcp]'   # or: uv sync --extra mcp
boilerworks-mcp                  # entry point defined in pyproject.toml
```

## Claude Code skill

`skill/skill.md` teaches an agent the catalogue and workflow. Its
"Template catalogue" section is generated from `boilerworks/data/templates.yaml`
by `scripts/gen_skill_catalogue.py` — never edit those tables by hand.

## Coding standards

- Fully typed: all function signatures have type hints
- Line length: 120 (ruff config in pyproject.toml)
- `ruff check . && ruff format .` after every change
- pytest coverage ≥ 80%
- No TODOs, no stubs (bootstrap is intentionally a v2 stub — document it clearly)
- No co-authorship messages in commits

## Common patterns

**Adding a CLI option**: edit `boilerworks/cli.py`, add `@click.option(...)` decorator

**Adding a manifest field**: edit `boilerworks/manifest.py` (BoilerworksManifest model)

**Adding a renderer rule**: edit `boilerworks/renderer.py` (`build_replacements` or `_SKIP_*`)

**Adding a template to the catalogue**: edit `boilerworks/data/templates.yaml`, then run `uv run python scripts/gen_skill_catalogue.py`
