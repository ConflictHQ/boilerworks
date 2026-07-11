# Build Spec — Boilerworks CLI

## Context

Build the Boilerworks CLI — a Python package that assembles production-ready projects from a catalogue of 26 opinionated templates. Published to PyPI as `boilerworks`. This replaces the old monorepo contents in this directory.

## Required Reading (before writing ANY code)

1. `../primers/PROCESS.md` — development philosophy, coding standards (Ruff, uv, PEP 8), testing standards
2. `../primers/CATALOGUE.md` — full template catalogue, sizes (Full/Micro/Edge), selection guide, two-template decisions
3. `../primers/RELEASE_CHECKLIST.md` — what the release looks like
4. `../boilerworks-django-nextjs/CLAUDE.md` — reference agent shim pattern
5. `../boilerworks-django-nextjs/bootstrap.md` — reference conventions doc pattern
6. `../boilerworks-fastapi-micro/.env.example` — example of literal "boilerworks" strings in templates (informs renderer)

## Tech Stack

- Python 3.12+
- Click 8+ (CLI framework)
- Questionary 2+ (interactive prompts)
- Rich 13+ (pretty output — tables, panels, progress bars)
- Pydantic v2 (manifest validation)
- Jinja2 3+ (available but primary approach is string replacement)
- GitPython 3+ (git operations)
- PyYAML 6+ (registry loading)
- Ruff (lint + format, NOT flake8)
- uv (package manager, NOT pip directly)
- pytest (testing)

## Repo Setup

This directory (`boilerworks/`) is the CLI package. It lives inside the parent boilerworks catalogue repo. The git remote is `ConflictHQ/boilerworks`.

1. The old monorepo contents have been removed (backend/, frontend/, docker/ are gone)
2. Keep the existing README.md for now (will be rewritten)
3. Create the Python package structure here

## Package Structure

```
boilerworks/                    # This directory (CLI package root)
├── pyproject.toml
├── uv.lock
├── Makefile
├── README.md                   # Rewrite for CLI
├── CLAUDE.md
├── AGENTS.md
├── boilerworks.yaml.example
├── boilerworks/                # Python package
│   ├── __init__.py             # __version__ = "0.1.0"
│   ├── cli.py                  # Click group: setup, init, bootstrap, list
│   ├── wizard.py               # Questionary prompts → boilerworks.yaml
│   ├── generator.py            # Clone → render → wire → git init
│   ├── bootstrap.py            # Terraform layer orchestration (stub for now)
│   ├── manifest.py             # Pydantic models for boilerworks.yaml
│   ├── registry.py             # Load + query template catalogue
│   ├── renderer.py             # String replacement in cloned files
│   └── console.py              # Rich output helpers
├── data/
│   └── templates.yaml          # All 26 templates with metadata
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_manifest.py
│   ├── test_registry.py
│   ├── test_renderer.py
│   └── test_generator.py
└── .github/
    ├── workflows/ci.yml
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   ├── feature_request.md
    │   └── config.yml
    ├── pull_request_template.md
    └── dependabot.yml
```

## Build Phases (execute in order)

### Phase 0: Scaffolding

Get `boilerworks --help` working.

1. Create `pyproject.toml` with:
   - name = "boilerworks", version = "0.1.0"
   - requires-python = ">=3.12"
   - All dependencies listed above
   - Entry point: `boilerworks = "boilerworks.cli:main"`
   - Ruff config: target-version = "py312", line-length = 120, select = ["E", "F", "I", "W", "UP", "B", "SIM", "N"]
   - pytest config
2. Create `boilerworks/__init__.py` with `__version__ = "0.1.0"`
3. Create `boilerworks/cli.py` with Click group and stub commands:
   ```python
   @click.group()
   def main():
       """Boilerworks — production-ready project templates."""
       pass

   @main.command()
   def setup(): ...
   @main.command()
   def init(): ...
   @main.command()
   def bootstrap(): ...
   @main.command()
   def list(): ...
   ```
4. Create Makefile: lint, test, build, install targets
5. Run `uv lock`
6. Verify: `uv run boilerworks --help` shows all 4 commands

### Phase 1: Registry + List Command

Make `boilerworks list` show all 26 templates in a Rich table.

1. Create `boilerworks/data/templates.yaml` with ALL 26 templates. Each entry:
   ```yaml
   - name: django-nextjs
     repo: ConflictHQ/boilerworks-django-nextjs
     size: full           # full | micro | edge
     language: python
     backend: Django 5
     frontend: Next.js 16
     status: done          # done | building | planned
     description: "Data-heavy backends, admin-rich, rapid prototyping"
     topologies: [standard, omni, api-only]
     best_for: "Python teams wanting batteries-included backend with rich SPA frontend"
   ```
   Include ALL templates from the catalogue (check ../primers/CATALOGUE.md for the full list):
   - Full: django-nextjs, django-htmx, nestjs-nextjs, saleor-nextjs, rails-hotwire, rails-nextjs, laravel-vue, laravel-livewire, fastapi-nextjs, fastapi-htmx, spring-angular, spring-nextjs, go-htmx, go-nextjs, phoenix-liveview
   - Micro: django-micro, fastapi-micro, nestjs-micro, go-micro, rust-micro, cherrypy-micro
   - Edge: hono-micro, sveltekit-full, nuxt-full, remix-full, astro-site

2. Create `boilerworks/registry.py`:
   - `TemplateInfo` Pydantic model
   - `Registry` class: loads YAML, provides `list_all()`, `filter_by_size()`, `filter_by_language()`, `get_by_name()`, `search(query)`
   - YAML path resolved relative to package using `importlib.resources` or `Path(__file__).parent`

3. Create `boilerworks/console.py`:
   - Rich table builder for template listing
   - Rich panel for template details
   - Colored status badges (done=green, building=yellow, planned=dim)

4. Implement `boilerworks list`:
   - No flags: show all templates in Rich table (Name, Size, Language, Backend, Frontend, Status, Description)
   - `--size full|micro|edge`: filter
   - `--language python|typescript|ruby|php|java|go|elixir|rust|svelte`: filter
   - `--status done|building|planned`: filter
   - Combine filters: `boilerworks list --size micro --language python`

5. Write `tests/test_registry.py`:
   - YAML loads without error
   - All 26 templates present
   - Filter by size returns correct subset
   - Filter by language returns correct subset
   - get_by_name returns correct template
   - get_by_name with invalid name returns None

### Phase 2: Manifest + Setup Wizard

Make `boilerworks setup` generate a `boilerworks.yaml`.

1. Create `boilerworks/manifest.py`:
   ```python
   class BoilerworksManifest(BaseModel):
       project: str  # must be slug format (lowercase, hyphens, no spaces)
       family: str   # must exist in registry
       size: Literal["full", "micro", "edge"]
       topology: Literal["standard", "omni", "api-only"] = "standard"
       cloud: Optional[Literal["aws", "gcp", "azure"]] = None
       region: Optional[str] = None
       domain: Optional[str] = None
       mobile: bool = False
       web_presence: bool = False
       compliance: list[str] = Field(default_factory=list)
       services: ServicesConfig = Field(default_factory=ServicesConfig)
       data: DataConfig = Field(default_factory=DataConfig)
       testing: TestingConfig = Field(default_factory=TestingConfig)
       template_versions: dict[str, str] = Field(default_factory=dict)
   ```
   - Nested models for services, data, testing sections
   - Validator: family must exist in registry
   - Validator: project must be slug format
   - `to_yaml()` and `from_yaml()` methods

2. Create `boilerworks/wizard.py`:
   - Uses questionary for prompts, Rich for display
   - Question flow (13 steps):
     1. Project name (text, validated as slug)
     2. Template size (select: Full / Micro / Edge)
     3. Template family (select, filtered by size, grouped by language)
        - Show Rich panel with selection guide before asking
     4. Topology (select: standard / omni / api-only, filtered by family support)
     5. Cloud provider (select: aws / gcp / azure / none)
     6. Region (text, shown only if cloud selected)
     7. Domain (text, optional)
     8. Mobile (confirm, shown only for Full size)
     9. Web presence (confirm, shown only for Full size)
     10. Compliance (checkbox: soc2, hipaa, pci-dss, gdpr, none)
     11. Email provider (select: ses / sendgrid / mailgun / none)
     12. E2E testing (select: playwright / cypress / none)
     13. Confirm and write
   - Writes `boilerworks.yaml` to current directory
   - Shows Rich panel summary before confirming

3. Implement `boilerworks setup` command

4. Write `tests/test_manifest.py`:
   - Valid manifest passes validation
   - Invalid project name (spaces, uppercase) fails
   - Unknown family fails
   - to_yaml/from_yaml roundtrip
   - Optional fields have correct defaults

### Phase 3: Init Generator

Make `boilerworks init` generate a configured project.

1. Create `boilerworks/renderer.py`:
   - `render_file(path, replacements)`: read file, apply replacements, write back
   - `render_directory(root, replacements, skip_dirs, skip_extensions)`:
     - Walk directory tree
     - Skip: `.git/`, `node_modules/`, `vendor/`, `__pycache__/`, `_build/`, `deps/`, `target/`, `.venv/`
     - Skip binary extensions: `.png`, `.jpg`, `.jpeg`, `.gif`, `.ico`, `.woff`, `.woff2`, `.ttf`, `.eot`, `.lock`, `.pyc`
     - For text files: apply all replacements
   - Replacements are case-variant:
     - `boilerworks` → `{project}` (lowercase)
     - `Boilerworks` → `{Project}` (capitalized)
     - `BOILERWORKS` → `{PROJECT}` (uppercase)
     - `boilerworks_` → `{project}_` (underscore variant for Python)
   - Also replace port numbers if template has standard ports (configurable per template in registry)

2. Create `boilerworks/generator.py`:
   - `generate(manifest, output_dir)`:
     1. Load manifest + validate
     2. Look up template in registry
     3. Clone repo:
        - Try: `git clone git@github.com:{repo}.git {output_dir}/{project}`
        - Fallback: `git clone https://github.com/{repo}.git` (using gh auth token)
        - Show Rich progress spinner during clone
     4. Remove `.git/` from cloned dir
     5. Run renderer across all files
     6. Rename any files/dirs containing "boilerworks" (e.g., `boilerworks.iml`)
     7. Update CLAUDE.md: replace template-specific references with project name
     8. Update README.md: replace template header with project name
     9. `git init` + `git add .` + `git commit -m "Initial project from boilerworks-{family}"`
     10. If topology=standard and cloud is set:
         - Also clone ops template if it exists
         - Render + init ops repo
     11. If mobile=true: clone + render mobile template
     12. Print Rich panel with next steps:
         ```
         Project created at: {output_dir}/{project}/

         Next steps:
           cd {project}
           docker compose up -d
           # Visit http://localhost:3000

         Documentation:
           bootstrap.md  — conventions
           CLAUDE.md     — AI agent guide
         ```

3. Implement `boilerworks init`:
   - `boilerworks init` — reads boilerworks.yaml from cwd
   - `--manifest PATH` — specify manifest path
   - `--output DIR` — specify output directory (default: cwd)
   - `--dry-run` — show what would be done without doing it

4. Write `tests/test_renderer.py`:
   - Case-variant replacement works
   - Binary files skipped
   - Excluded directories skipped
   - Empty files handled
   - Files with no matches unchanged

5. Write `tests/test_generator.py`:
   - Dry-run mode outputs plan
   - (Integration test with real clone can be marked slow/optional)

### Phase 4: Bootstrap (Stub)

For v1, bootstrap is a documented stub — it prints what WOULD happen but doesn't execute Terraform.

1. Create `boilerworks/bootstrap.py`:
   - `bootstrap(manifest, ops_dir)`:
     - Validates ops directory exists
     - Shows Rich panel with the 5 layers it would execute
     - Prints "Infrastructure bootstrapping coming in v2. For now, follow the ops template README."
   - This is intentionally incomplete — Terraform modules don't exist yet

2. Implement `boilerworks bootstrap`:
   - Shows execution plan
   - `--dry-run` is the only real mode for now

### Phase 5: Polish + Ship

1. Create `boilerworks.yaml.example` — fully annotated example manifest
2. Rewrite `README.md` for PyPI:
   - What is Boilerworks
   - `pip install boilerworks`
   - Quick start (setup → init → docker compose up)
   - Template catalogue preview (table)
   - Link to boilerworks.dev
3. Create `CLAUDE.md` agent shim for the CLI repo itself
4. Create `AGENTS.md`
5. Create `.github/workflows/ci.yml`: lint + test + build
6. Create `.github/dependabot.yml`
7. Create `.github/ISSUE_TEMPLATE/` (bug_report, feature_request, config)
8. Create `.github/pull_request_template.md`
9. Add brand footer to README: "Boilerworks is a [Conflict](https://weareconflict.com) brand. CONFLICT is a registered trademark of Conflict LLC."
10. Run full test suite, ensure 80%+ coverage
11. `ruff check . && ruff format --check .` — zero issues

## Quality Rules (non-negotiable)

- Python 3.12+, fully typed (type hints on all function signatures)
- PEP 8 via Ruff. `ruff check . && ruff format .` after every phase. Zero violations.
- Use uv: `pyproject.toml` + `uv.lock`
- pytest for all tests. Meaningful assertions. No `assert True`.
- 80%+ test coverage target
- No TODOs, no stubs (except bootstrap which is explicitly a v2 feature)
- No co-authorship messages in commits
- Repo is private

## What NOT to do

- Do NOT use pip directly — use uv
- Do NOT use flake8/isort/black — use Ruff
- Do NOT mock extensively — test real behavior where possible
- Do NOT hardcode ConflictHQ anywhere users would see — use registry data
- Do NOT implement Terraform execution in v1 — bootstrap is a stub
- Do NOT implement omni topology in v1 — standard only

## Completion

When ALL of the following are true:
- `uv run boilerworks --help` shows setup, init, bootstrap, list
- `uv run boilerworks list` shows 26 templates in a Rich table
- `uv run boilerworks list --size micro --language python` filters correctly
- `uv run boilerworks setup` walks through wizard, writes valid boilerworks.yaml
- `uv run boilerworks init` clones a template, renames everything, git inits
- `ruff check .` passes
- `ruff format --check .` passes
- `pytest` passes with 80%+ coverage
- README.md is a real PyPI README
- All .github/ community files exist

The CLI is done.
