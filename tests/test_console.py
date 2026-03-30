"""Tests for boilerworks.console."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from boilerworks.console import (
    print_error,
    print_info,
    print_success,
    print_template_detail,
    print_template_table,
    print_warning,
)
from boilerworks.registry import Registry, TemplateInfo


def _capture(fn, *args, **kwargs) -> str:
    """Call fn with a capturing console and return the output."""
    buf = StringIO()
    cap = Console(file=buf, highlight=False, markup=True)
    # Temporarily override the module-level console
    import boilerworks.console as _mod

    original = _mod.console
    _mod.console = cap
    try:
        fn(*args, **kwargs)
    finally:
        _mod.console = original
    return buf.getvalue()


class TestPrintTemplateTable:
    def test_shows_all_templates(self) -> None:
        registry = Registry()
        templates = registry.list_all()
        output = _capture(print_template_table, templates)
        assert "django-nextjs" in output
        assert "astro-site" in output

    def test_shows_26_count(self) -> None:
        registry = Registry()
        templates = registry.list_all()
        output = _capture(print_template_table, templates)
        assert "26" in output

    def test_empty_list_shows_message(self) -> None:
        output = _capture(print_template_table, [])
        assert "No templates match" in output

    def test_filtered_table(self) -> None:
        registry = Registry()
        templates = registry.filter_by_size("micro")
        output = _capture(print_template_table, templates)
        assert "fastapi-micro" in output
        assert "django-nextjs" not in output


class TestPrintTemplateDetail:
    def test_shows_template_fields(self) -> None:
        registry = Registry()
        template = registry.get_by_name("django-nextjs")
        assert template is not None
        output = _capture(print_template_detail, template)
        assert "django-nextjs" in output
        assert "python" in output.lower()
        assert "Django" in output

    def test_template_without_frontend(self) -> None:
        # Micro templates have no frontend
        t = TemplateInfo(
            name="test-micro",
            repo="ConflictHQ/test",
            size="micro",
            language="python",
            backend="FastAPI",
            frontend="",
            status="planned",
            description="Test",
        )
        output = _capture(print_template_detail, t)
        assert "test-micro" in output


class TestPrintHelpers:
    def test_print_success(self) -> None:
        output = _capture(print_success, "All good")
        assert "All good" in output

    def test_print_error(self) -> None:
        output = _capture(print_error, "Something failed")
        assert "Something failed" in output

    def test_print_info(self) -> None:
        output = _capture(print_info, "Just FYI")
        assert "Just FYI" in output

    def test_print_warning(self) -> None:
        output = _capture(print_warning, "Be careful")
        assert "Be careful" in output
