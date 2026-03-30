# Contributing

## Ways to contribute

- **Add a template** — build a new stack using the [boilerworks conventions](https://github.com/ConflictHQ/boilerworks/blob/main/primers/PROCESS.md) and open a PR to add it to the catalogue
- **Improve docs** — fix errors, improve clarity, add examples
- **Report bugs** — open an issue with steps to reproduce
- **Request a template** — open an issue describing the stack

## Template conventions

All templates must:

- Boot with `docker compose up -d` from scratch (no local installs required)
- Use standard ports (app: 3000/8000, postgres: 5432, redis: 6379)
- Use `boilerworks` as the placeholder name throughout (the renderer replaces it)
- Include: Items, Categories, FormDefinitions, FormSubmissions, WorkflowDefinitions (Full only)
- Have health check at `/up` or `/health/`
- Include a `CLAUDE.md` pointing to `bootstrap.md`
- Pass `make test` and `make lint`

## CLI development

```bash
git clone https://github.com/ConflictHQ/boilerworks.git
cd boilerworks
uv sync
uv run boilerworks --help

make lint    # ruff check + format --check
make test    # pytest with coverage
make format  # ruff fix + format
```

Coverage must stay at ≥ 80%.

## Adding a template to the catalogue

1. Build and test the template repo (must live at `ConflictHQ/boilerworks-{name}`)
2. Edit `data/templates.yaml` — add an entry with `name`, `repo`, `size`, `language`, `status`, `description`, `topologies`
3. Run `make test` — `test_registry.py` will catch count or schema mismatches
4. Open a PR

## Code standards

- Python 3.12+, fully typed
- Line length: 120 (ruff config in `pyproject.toml`)
- `ruff check . && ruff format .` before every commit
- No TODOs, no stubs
- No co-authorship messages in commits

## Issues and PRs

[github.com/ConflictHQ/boilerworks/issues](https://github.com/ConflictHQ/boilerworks/issues)
