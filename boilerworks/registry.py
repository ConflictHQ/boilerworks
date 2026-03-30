"""Template registry — loads and queries templates.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

_DATA_DIR = Path(__file__).parent / "data"


class TemplateInfo(BaseModel):
    """A single template entry from templates.yaml."""

    name: str
    repo: str
    size: Literal["full", "micro", "edge"]
    language: str
    backend: str
    frontend: str
    status: Literal["done", "building", "planned"]
    description: str
    topologies: list[str] = Field(default_factory=list)
    best_for: str = ""


class Registry:
    """Loads templates.yaml and provides query methods."""

    def __init__(self, yaml_path: Path | None = None) -> None:
        path = yaml_path or (_DATA_DIR / "templates.yaml")
        raw: list[dict] = yaml.safe_load(path.read_text())
        self._templates: list[TemplateInfo] = [TemplateInfo(**entry) for entry in raw]

    def list_all(self) -> list[TemplateInfo]:
        """Return all templates."""
        return list(self._templates)

    def filter_by_size(self, size: str) -> list[TemplateInfo]:
        """Return templates matching the given size."""
        return [t for t in self._templates if t.size == size]

    def filter_by_language(self, language: str) -> list[TemplateInfo]:
        """Return templates matching the given language."""
        return [t for t in self._templates if t.language == language]

    def filter_by_status(self, status: str) -> list[TemplateInfo]:
        """Return templates matching the given status."""
        return [t for t in self._templates if t.status == status]

    def get_by_name(self, name: str) -> TemplateInfo | None:
        """Return the template with the given name, or None."""
        for t in self._templates:
            if t.name == name:
                return t
        return None

    def search(self, query: str) -> list[TemplateInfo]:
        """Return templates whose name, description, or best_for contains the query (case-insensitive)."""
        q = query.lower()
        return [
            t for t in self._templates if q in t.name.lower() or q in t.description.lower() or q in t.best_for.lower()
        ]

    def names(self) -> list[str]:
        """Return all template names."""
        return [t.name for t in self._templates]
