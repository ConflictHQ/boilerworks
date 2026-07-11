"""skill/skill.md catalogue must stay in sync with boilerworks/data/templates.yaml."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_skill_catalogue.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_skill_catalogue", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_catalogue_matches_registry() -> None:
    gen = _load_generator()
    current = gen.SKILL_MD.read_text()
    assert gen.render_skill_md(current) == current, (
        "skill/skill.md catalogue drifted from boilerworks/data/templates.yaml — "
        "run: uv run python scripts/gen_skill_catalogue.py"
    )
