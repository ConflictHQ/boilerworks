# Changelog

## 0.2.0 — 2026-07-11

- MCP server: `boilerworks-mcp` entry point (optional `mcp` extra) exposing
  `list_templates`, `get_template`, `search_templates`, `create_manifest`,
  `validate_manifest`, `dry_run`, and `init_project` as agent tools, with full
  test coverage
- Claude Code skill (`skill/skill.md`); catalogue tables single-sourced from
  `boilerworks/data/templates.yaml` via `scripts/gen_skill_catalogue.py` with a
  drift-guard test
- `mobile: true` and `web_presence: true` manifest flags now generate:
  react-native-expo into `mobile/`, astro-site into `site/`, both inside the
  app repo; dry-run plan matches
- Fix: `python -m boilerworks.cli` was a no-op (missing `__main__` guard),
  which made the MCP `dry_run`/`init_project` tools silently do nothing
- Repo hygiene: Python/uv `.gitignore`, removed pre-Ruff lint configs, doc path
  fixes, lockfile catch-up for the `mcp` extra

## 0.1.0 — 2026-03-29

- Initial release: `setup` wizard, `init` generator, `list`, `bootstrap` stub;
  26-template registry; ops repo wiring (standard + omni topologies); Ruff +
  pytest + CI
