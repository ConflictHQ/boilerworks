#!/usr/bin/env python3
"""Regenerate the template catalogue section of skill/skill.md from the registry.

The catalogue tables in skill/skill.md are generated from
boilerworks/data/templates.yaml — edit the registry, then run:

    uv run python scripts/gen_skill_catalogue.py

Pass --check to verify without writing (exits 1 on drift).
tests/test_skill_catalogue.py runs the same comparison in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "skill" / "skill.md"
SECTION_HEADING = "## Template catalogue"

sys.path.insert(0, str(REPO_ROOT))

from boilerworks.registry import Registry  # noqa: E402


def build_catalogue() -> str:
    """Render the '## Template catalogue' section from the registry."""
    registry = Registry()
    lines = [
        SECTION_HEADING,
        "",
        "<!-- Generated from boilerworks/data/templates.yaml by scripts/gen_skill_catalogue.py"
        " — do not edit by hand. -->",
        "",
        "### Full templates — apps with users, org management, session auth",
        "",
        "| Template | Backend | Frontend |",
        "|---|---|---|",
    ]
    lines += [f"| {t.name} | {t.backend} | {t.frontend} |" for t in registry.filter_by_size("full")]
    lines += [
        "",
        "### Micro templates — API services with API-key auth",
        "",
        "| Template | Backend |",
        "|---|---|",
    ]
    lines += [f"| {t.name} | {t.backend} |" for t in registry.filter_by_size("micro")]
    lines += [
        "",
        "### Edge templates — serverless / Cloudflare",
        "",
        "| Template | Framework |",
        "|---|---|",
    ]
    lines += [f"| {t.name} | {t.backend} |" for t in registry.filter_by_size("edge")]
    lines.append("")
    return "\n".join(lines)


def render_skill_md(current: str) -> str:
    """Return skill.md content with the catalogue section replaced by the generated one."""
    start = current.index(SECTION_HEADING)
    end = current.index("\n## ", start + len(SECTION_HEADING))
    return current[:start] + build_catalogue() + current[end:]


def main() -> int:
    check = "--check" in sys.argv[1:]
    current = SKILL_MD.read_text()
    updated = render_skill_md(current)
    if updated == current:
        print("skill/skill.md catalogue is up to date.")
        return 0
    if check:
        print("skill/skill.md catalogue drifted from boilerworks/data/templates.yaml.")
        print("Run: uv run python scripts/gen_skill_catalogue.py")
        return 1
    SKILL_MD.write_text(updated)
    print("skill/skill.md catalogue regenerated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
