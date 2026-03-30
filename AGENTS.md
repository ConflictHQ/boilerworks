# Agents — Boilerworks CLI

This file is for Cursor, Windsurf, and generic AI coding agents.

**Read `CLAUDE.md` for the full stack summary and conventions.**

## Quick orientation

- This is the `boilerworks` Python CLI package, not a web app
- Entry point: `boilerworks/cli.py` → `main()` Click group
- Template data: `data/templates.yaml` (26 templates)
- Manifest model: `boilerworks/manifest.py` → `BoilerworksManifest`
- Registry: `boilerworks/registry.py` → `Registry`
- Renderer: `boilerworks/renderer.py` → `render_directory`, `build_replacements`

## Before writing code

1. Run `uv run boilerworks --help` to verify the CLI works
2. Run `make lint` to check for style issues
3. Run `make test` to ensure tests pass

## After writing code

1. `make format` — fix style issues
2. `make lint` — verify zero violations
3. `make test` — verify tests pass and coverage ≥ 80%
