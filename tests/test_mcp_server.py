"""Tests for boilerworks.mcp_server."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("mcp")

from boilerworks import mcp_server  # noqa: E402
from boilerworks.manifest import BoilerworksManifest  # noqa: E402


class TestListTemplates:
    def test_lists_all_26_templates(self) -> None:
        rows = json.loads(mcp_server.list_templates())
        assert len(rows) == 26

    def test_rows_have_expected_fields(self) -> None:
        rows = json.loads(mcp_server.list_templates())
        for row in rows:
            assert {"name", "size", "language", "backend", "frontend", "status", "best_for"} <= set(row)

    def test_filter_by_size(self) -> None:
        rows = json.loads(mcp_server.list_templates(size="micro"))
        assert len(rows) == 6
        assert all(r["size"] == "micro" for r in rows)

    def test_filter_by_language(self) -> None:
        rows = json.loads(mcp_server.list_templates(language="go"))
        assert rows
        assert all(r["language"] == "go" for r in rows)

    def test_filter_by_status(self) -> None:
        rows = json.loads(mcp_server.list_templates(status="done"))
        assert all(r["status"] == "done" for r in rows)

    def test_filters_combine(self) -> None:
        rows = json.loads(mcp_server.list_templates(size="full", language="python"))
        assert all(r["size"] == "full" and r["language"] == "python" for r in rows)


class TestGetTemplate:
    def test_found_returns_full_details(self) -> None:
        data = json.loads(mcp_server.get_template("django-nextjs"))
        assert data["name"] == "django-nextjs"
        assert data["repo"] == "ConflictHQ/boilerworks-django-nextjs"
        assert data["size"] == "full"

    def test_not_found_lists_available(self) -> None:
        result = mcp_server.get_template("no-such-template")
        assert "not found" in result
        assert "django-nextjs" in result


class TestSearchTemplates:
    def test_match_returns_rows(self) -> None:
        rows = json.loads(mcp_server.search_templates("django"))
        names = {r["name"] for r in rows}
        assert "django-nextjs" in names

    def test_no_match_returns_message(self) -> None:
        assert mcp_server.search_templates("zzz-no-match") == "No templates matched 'zzz-no-match'."


class TestCreateManifest:
    def test_valid_args_return_parseable_yaml(self) -> None:
        yaml_content = mcp_server.create_manifest(project="my-app", family="django-nextjs", size="full")
        manifest = BoilerworksManifest.from_yaml(yaml_content)
        assert manifest.project == "my-app"
        assert manifest.family == "django-nextjs"
        assert manifest.size == "full"

    def test_flags_are_preserved(self) -> None:
        yaml_content = mcp_server.create_manifest(
            project="my-app",
            family="django-nextjs",
            size="full",
            cloud="aws",
            region="us-east-1",
            ops=True,
            mobile=True,
            web_presence=True,
        )
        manifest = BoilerworksManifest.from_yaml(yaml_content)
        assert manifest.cloud == "aws"
        assert manifest.ops is True
        assert manifest.mobile is True
        assert manifest.web_presence is True

    def test_invalid_project_slug_returns_error(self) -> None:
        result = mcp_server.create_manifest(project="Bad Name!", family="django-nextjs", size="full")
        assert result.startswith("Invalid manifest:")

    def test_invalid_size_returns_error(self) -> None:
        result = mcp_server.create_manifest(project="my-app", family="django-nextjs", size="giant")
        assert result.startswith("Invalid manifest:")


class TestValidateManifest:
    def test_valid_manifest(self, valid_manifest: BoilerworksManifest) -> None:
        assert mcp_server.validate_manifest(valid_manifest.to_yaml()) == "valid"

    def test_invalid_manifest(self) -> None:
        result = mcp_server.validate_manifest("project: Bad Name!\nfamily: django-nextjs\nsize: full\n")
        assert result.startswith("invalid:")


class TestRunCli:
    def test_dry_run_via_subprocess(self, tmp_path: Path, valid_manifest: BoilerworksManifest) -> None:
        """_run_cli really invokes the CLI: dry-run prints the plan and writes nothing."""
        output = mcp_server._run_cli(["init", "--dry-run", "--output", str(tmp_path)], valid_manifest.to_yaml())
        assert "Dry run" in output
        assert valid_manifest.project in output
        assert not (tmp_path / valid_manifest.project).exists()


class TestDryRun:
    def test_wires_dry_run_args(self, valid_manifest: BoilerworksManifest) -> None:
        yaml_content = valid_manifest.to_yaml()
        with patch.object(mcp_server, "_run_cli", return_value="plan") as run_cli:
            result = mcp_server.dry_run(yaml_content, output_dir="/some/dir")
        assert result == "plan"
        run_cli.assert_called_once_with(["init", "--dry-run", "--output", "/some/dir"], yaml_content)


class TestInitProject:
    def test_wires_init_args(self, valid_manifest: BoilerworksManifest) -> None:
        yaml_content = valid_manifest.to_yaml()
        with patch.object(mcp_server, "_run_cli", return_value="done") as run_cli:
            result = mcp_server.init_project(yaml_content, output_dir="/some/dir")
        assert result == "done"
        run_cli.assert_called_once_with(["init", "--output", "/some/dir"], yaml_content)
