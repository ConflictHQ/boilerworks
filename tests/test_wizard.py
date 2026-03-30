"""Tests for boilerworks.wizard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from boilerworks.wizard import _template_choices, _validate_slug


class TestValidateSlug:
    def test_valid_slugs(self) -> None:
        for slug in ["my-app", "app", "a1b2", "my-project-v2"]:
            assert _validate_slug(slug) is True

    def test_empty_returns_message(self) -> None:
        result = _validate_slug("")
        assert isinstance(result, str)
        assert "required" in result.lower()

    def test_spaces_returns_message(self) -> None:
        result = _validate_slug("my app")
        assert isinstance(result, str)

    def test_uppercase_returns_message(self) -> None:
        result = _validate_slug("MyApp")
        assert isinstance(result, str)

    def test_leading_digit_returns_message(self) -> None:
        result = _validate_slug("1app")
        assert isinstance(result, str)


class TestTemplateChoices:
    def test_returns_choices_list(self) -> None:
        from boilerworks.registry import Registry

        registry = Registry()
        templates = registry.filter_by_size("full")
        choices = _template_choices(templates)
        assert len(choices) > 0

    def test_separators_per_language(self) -> None:
        import questionary

        from boilerworks.registry import Registry

        registry = Registry()
        templates = registry.list_all()
        choices = _template_choices(templates)
        separators = [c for c in choices if isinstance(c, questionary.Separator)]
        # Should have at least one separator per language group
        assert len(separators) >= 5

    def test_choice_values_are_template_names(self) -> None:
        import questionary

        from boilerworks.registry import Registry

        registry = Registry()
        templates = registry.filter_by_size("micro")
        choices = _template_choices(templates)
        # Separator is a subclass of Choice in questionary, so exclude them explicitly
        real_choices = [
            c for c in choices if isinstance(c, questionary.Choice) and not isinstance(c, questionary.Separator)
        ]
        names = {c.value for c in real_choices}
        expected = {t.name for t in templates}
        assert names == expected


class TestRunWizard:
    """Integration tests for run_wizard using mocked questionary."""

    def test_wizard_writes_manifest(self, tmp_path: Path) -> None:
        output_file = tmp_path / "boilerworks.yaml"

        with (
            patch("questionary.text") as mock_text,
            patch("questionary.select") as mock_select,
            patch("questionary.confirm") as mock_confirm,
            patch("questionary.checkbox") as mock_checkbox,
        ):
            mock_text.return_value.ask.side_effect = [
                "my-test-app",  # project name
                "",  # region (empty → None)
                "",  # domain (empty → None)
            ]
            mock_select.return_value.ask.side_effect = [
                "full",  # size
                "django-nextjs",  # family
                "standard",  # topology
                "none",  # cloud
                "none",  # email
                "none",  # e2e
            ]
            mock_confirm.return_value.ask.side_effect = [
                False,  # mobile
                False,  # web_presence
                True,  # confirm write
            ]
            mock_checkbox.return_value.ask.return_value = []  # compliance

            from boilerworks.wizard import run_wizard

            run_wizard(output_path=output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "my-test-app" in content
        assert "django-nextjs" in content

    def test_wizard_cancelled_on_project_name(self, tmp_path: Path) -> None:
        output_file = tmp_path / "boilerworks.yaml"
        with patch("questionary.text") as mock_text:
            mock_text.return_value.ask.return_value = None  # user hit Ctrl+C
            from boilerworks.wizard import run_wizard

            with pytest.raises(SystemExit):
                run_wizard(output_path=output_file)

        assert not output_file.exists()

    def test_wizard_cancelled_on_confirm(self, tmp_path: Path) -> None:
        output_file = tmp_path / "boilerworks.yaml"
        with (
            patch("questionary.text") as mock_text,
            patch("questionary.select") as mock_select,
            patch("questionary.confirm") as mock_confirm,
            patch("questionary.checkbox") as mock_checkbox,
        ):
            mock_text.return_value.ask.side_effect = ["my-app", "", ""]
            mock_select.return_value.ask.side_effect = ["full", "django-nextjs", "standard", "none", "none", "none"]
            mock_confirm.return_value.ask.side_effect = [False, False, False]  # all confirms → False
            mock_checkbox.return_value.ask.return_value = []

            from boilerworks.wizard import run_wizard

            with pytest.raises(SystemExit):
                run_wizard(output_path=output_file)

        assert not output_file.exists()

    def test_wizard_with_cloud_and_region(self, tmp_path: Path) -> None:
        output_file = tmp_path / "boilerworks.yaml"
        with (
            patch("questionary.text") as mock_text,
            patch("questionary.select") as mock_select,
            patch("questionary.confirm") as mock_confirm,
            patch("questionary.checkbox") as mock_checkbox,
        ):
            mock_text.return_value.ask.side_effect = [
                "cloud-app",  # project name
                "us-east-1",  # region
                "myapp.com",  # domain
            ]
            # fastapi-micro has only one topology, so topology select is skipped
            mock_select.return_value.ask.side_effect = [
                "micro",  # size
                "fastapi-micro",  # family
                "aws",  # cloud (topology prompt skipped — single option)
                "ses",  # email
                "playwright",  # e2e
            ]
            mock_confirm.return_value.ask.return_value = True
            mock_checkbox.return_value.ask.return_value = ["soc2"]

            from boilerworks.wizard import run_wizard

            run_wizard(output_path=output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "cloud-app" in content
        assert "fastapi-micro" in content
