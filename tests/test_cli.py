"""Tests for boilerworks.cli — Click command interface."""

from __future__ import annotations

import json

from click.testing import CliRunner

from boilerworks import __version__
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
        assert "info" in result.output

    def test_list_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--help"])
        assert result.exit_code == 0
        assert "--size" in result.output
        assert "--language" in result.output
        assert "--status" in result.output
        assert "--json" in result.output

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
        assert __version__ in result.output


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


class TestListJsonOutput:
    def test_json_is_valid_and_lists_all_27(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--json"])
        assert result.exit_code == 0
        rows = json.loads(result.output)
        assert len(rows) == 27
        names = {r["name"] for r in rows}
        assert "django-nextjs-copilotkit" in names

    def test_json_rows_carry_repo_and_github_url(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--json"])
        rows = json.loads(result.output)
        row = next(r for r in rows if r["name"] == "django-nextjs-copilotkit")
        expected = {"name", "repo", "github_url", "size", "language", "backend", "frontend", "status", "best_for"}
        assert expected <= set(row)
        assert row["repo"] == "ConflictHQ/boilerworks-django-nextjs-copilotkit"
        assert row["github_url"] == "https://github.com/ConflictHQ/boilerworks-django-nextjs-copilotkit"

    def test_json_respects_filters(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--json", "--size", "micro"])
        rows = json.loads(result.output)
        assert rows
        assert all(r["size"] == "micro" for r in rows)


class TestInfoCommand:
    def test_info_shows_details_and_github_url(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["info", "django-nextjs-copilotkit"])
        assert result.exit_code == 0
        assert "django-nextjs-copilotkit" in result.output
        # The GitHub URL row is present (assert wrap-safe fragments, not the whole URL)
        assert "github.com" in result.output
        assert "ConflictHQ/boilerworks-django-nextjs-copilotkit" in result.output

    def test_info_unknown_name_exits_nonzero_with_suggestion(self) -> None:
        runner = CliRunner()
        # "copilot" is a substring of a real template name → offered as a suggestion
        result = runner.invoke(main, ["info", "copilot"])
        assert result.exit_code == 1
        assert "Unknown template" in result.output
        assert "django-nextjs-copilotkit" in result.output

    def test_info_no_match_points_to_list(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["info", "zzz-not-a-template"])
        assert result.exit_code == 1
        assert "Unknown template" in result.output
        assert "boilerworks list" in result.output


class TestBootstrapCommand:
    def test_bootstrap_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["bootstrap"])
        assert result.exit_code == 0
        assert "Bootstrap Plan" in result.output or "v1" in result.output or "v2" in result.output
