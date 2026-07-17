# Changelog

## 0.3.0 — 2026-07-17

- 27-template registry: `django-nextjs-copilotkit` — the first template with a
  pre-wired agentic in-app copilot (CopilotKit + AG-UI over django-nextjs, wired
  to auth, forms, and workflows)
- CLI: `boilerworks info <template>` — full detail panel for a single template,
  including its GitHub URL, with "did you mean" suggestions on an unknown name
  (wires up the previously unreachable template-detail view)
- CLI: `boilerworks list --json` — machine-readable, filter-aware output for
  scripts and agents (name, repo, github_url, size, language, backend, frontend,
  status, best_for)
- Clearer clone failures: the generator now reports both the SSH and HTTPS
  errors (the old message mislabeled the HTTPS failure as "SSH error") and hints
  at private-repo / auth issues when git reports a missing repo or denied access
- Security: raise the `click` floor to `>=8.3.3` for PYSEC-2026-2132 /
  CVE-2026-7246 (command injection in `click.edit()`; fixed in 8.3.3)
- Docs: 26 → 27 template count across the README, the Claude Code skill, and the
  MCP server instructions

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
