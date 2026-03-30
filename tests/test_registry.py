"""Tests for boilerworks.registry."""

from __future__ import annotations

import pytest

from boilerworks.registry import Registry, TemplateInfo


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry()


def test_yaml_loads_without_error(registry: Registry) -> None:
    templates = registry.list_all()
    assert isinstance(templates, list)
    assert len(templates) > 0


def test_all_26_templates_present(registry: Registry) -> None:
    assert len(registry.list_all()) == 26


def test_templates_are_template_info_instances(registry: Registry) -> None:
    for t in registry.list_all():
        assert isinstance(t, TemplateInfo)


def test_filter_by_size_full(registry: Registry) -> None:
    full = registry.filter_by_size("full")
    assert len(full) == 15
    assert all(t.size == "full" for t in full)


def test_filter_by_size_micro(registry: Registry) -> None:
    micro = registry.filter_by_size("micro")
    assert len(micro) == 6
    assert all(t.size == "micro" for t in micro)


def test_filter_by_size_edge(registry: Registry) -> None:
    edge = registry.filter_by_size("edge")
    assert len(edge) == 5
    assert all(t.size == "edge" for t in edge)


def test_filter_by_language_python(registry: Registry) -> None:
    python = registry.filter_by_language("python")
    names = {t.name for t in python}
    assert "django-nextjs" in names
    assert "fastapi-micro" in names
    assert "nestjs-nextjs" not in names


def test_filter_by_language_typescript(registry: Registry) -> None:
    ts = registry.filter_by_language("typescript")
    names = {t.name for t in ts}
    assert "nestjs-nextjs" in names
    assert "django-nextjs" not in names


def test_filter_by_language_go(registry: Registry) -> None:
    go = registry.filter_by_language("go")
    assert all(t.language == "go" for t in go)
    assert len(go) >= 2


def test_get_by_name_returns_correct_template(registry: Registry) -> None:
    t = registry.get_by_name("django-nextjs")
    assert t is not None
    assert t.name == "django-nextjs"
    assert t.size == "full"
    assert t.language == "python"
    assert t.status == "done"


def test_get_by_name_returns_none_for_unknown(registry: Registry) -> None:
    assert registry.get_by_name("this-does-not-exist") is None


def test_get_by_name_fastapi_micro(registry: Registry) -> None:
    t = registry.get_by_name("fastapi-micro")
    assert t is not None
    assert t.size == "micro"
    assert t.language == "python"


def test_search_by_keyword(registry: Registry) -> None:
    results = registry.search("e-commerce")
    names = {t.name for t in results}
    assert "saleor-nextjs" in names


def test_search_case_insensitive(registry: Registry) -> None:
    results = registry.search("Python")
    assert len(results) > 0


def test_filter_by_status_done(registry: Registry) -> None:
    done = registry.filter_by_status("done")
    assert len(done) == 26
    assert all(t.status == "done" for t in done)


def test_all_templates_have_required_fields(registry: Registry) -> None:
    for t in registry.list_all():
        assert t.name, f"Template missing name: {t}"
        assert t.repo, f"Template {t.name} missing repo"
        assert t.size in ("full", "micro", "edge"), f"Template {t.name} has invalid size"
        assert t.language, f"Template {t.name} missing language"
        assert t.status in ("done", "building", "planned"), f"Template {t.name} has invalid status"
        assert t.description, f"Template {t.name} missing description"


def test_names_returns_all_names(registry: Registry) -> None:
    names = registry.names()
    assert len(names) == 26
    assert "django-nextjs" in names
    assert "astro-site" in names
