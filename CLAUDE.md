# Claude — Boilerworks CLI

Primary conventions doc: read this file, then the source code.

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
  __init__.py        # __version__ = "0.1.0"
  cli.py             # Click group: setup, init, bootstrap, list
  wizard.py          # Questionary prompts → boilerworks.yaml
  generator.py       # Clone → render → wire → git init
  bootstrap.py       # Terraform stub (v2)
  manifest.py        # Pydantic models for boilerworks.yaml
  registry.py        # Load + query templates.yaml
  renderer.py        # String replacement in cloned files
  console.py         # Rich output helpers
data/
  templates.yaml     # All 26 templates with metadata
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

Edit `data/templates.yaml`. Add an entry following the existing schema.
Run `make test` — `test_registry.py` will catch count mismatches.

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

**Adding a template to the catalogue**: edit `data/templates.yaml`
