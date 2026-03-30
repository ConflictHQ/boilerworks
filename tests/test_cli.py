"""Tests for boilerworks.cli — Click command interface."""

from __future__ import annotations

from click.testing import CliRunner

from boilerworks.cli import main


class TestHelpOutput:
    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "init" in result.output
        assert "bootstrap" in result.output
        assert "list" in result.output

    def test_list_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--help"])
        assert result.exit_code == 0
        assert "--size" in result.output
        assert "--language" in result.output
        assert "--status" in result.output

    def test_init_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "--manifest" in result.output
        assert "--output" in result.output
        assert "--dry-run" in result.output

    def test_bootstrap_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["bootstrap", "--help"])
        assert result.exit_code == 0

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestListCommand:
    def test_list_all(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "django-nextjs" in result.output
        assert "fastapi-micro" in result.output
        assert "astro-site" in result.output

    def test_list_filter_size_micro(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--size", "micro"])
        assert result.exit_code == 0
        assert "fastapi-micro" in result.output
        assert "django-nextjs" not in result.output

    def test_list_filter_size_edge(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--size", "edge"])
        assert result.exit_code == 0
        assert "astro-site" in result.output
        assert "django-nextjs" not in result.output

    def test_list_filter_language_python(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--language", "python"])
        assert result.exit_code == 0
        assert "django-nextjs" in result.output
        assert "nestjs-nextjs" not in result.output

    def test_list_filter_size_and_language(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--size", "micro", "--language", "python"])
        assert result.exit_code == 0
        assert "fastapi-micro" in result.output
        assert "nestjs-micro" not in result.output

    def test_list_filter_status_done(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--status", "done"])
        assert result.exit_code == 0
        assert "django-nextjs" in result.output

    def test_list_no_results_shows_message(self) -> None:
        runner = CliRunner()
        # rust + full → no results
        result = runner.invoke(main, ["list", "--size", "full", "--language", "rust"])
        assert result.exit_code == 0
        assert "No templates match" in result.output


class TestBootstrapCommand:
    def test_bootstrap_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["bootstrap"])
        assert result.exit_code == 0
        assert "Bootstrap Plan" in result.output or "v1" in result.output or "v2" in result.output
