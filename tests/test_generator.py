"""Tests for boilerworks.generator."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from boilerworks.generator import (
    _clone_and_render_ops,
    _dry_run_plan,
    _write_ops_config,
    generate_from_manifest,
)
from boilerworks.manifest import BoilerworksManifest


class TestDryRun:
    def test_dry_run_no_files_created(self, tmp_path: Path, valid_manifest: BoilerworksManifest) -> None:
        """Dry-run should print the plan without touching the filesystem."""
        project_dir = tmp_path / valid_manifest.project
        _dry_run_plan(valid_manifest, tmp_path)
        assert not project_dir.exists()

    def test_generate_from_manifest_dry_run(self, tmp_path: Path, valid_manifest: BoilerworksManifest) -> None:
        """generate_from_manifest with dry_run=True must not create any files."""
        manifest_file = tmp_path / "boilerworks.yaml"
        valid_manifest.to_file(manifest_file)

        project_dir = tmp_path / valid_manifest.project
        generate_from_manifest(
            manifest_path=str(manifest_file),
            output_dir=str(tmp_path),
            dry_run=True,
        )
        assert not project_dir.exists()

    def test_dry_run_with_ops_standard(self, tmp_path: Path) -> None:
        """Dry-run with cloud + ops shows ops clone step (standard topology)."""
        manifest = BoilerworksManifest(
            project="test-app",
            family="django-nextjs",
            size="full",
            cloud="aws",
            ops=True,
            topology="standard",
        )
        _dry_run_plan(manifest, tmp_path)  # should not raise

    def test_dry_run_with_ops_omni(self, tmp_path: Path) -> None:
        """Dry-run with cloud + ops shows ops clone step (omni topology)."""
        manifest = BoilerworksManifest(
            project="test-app",
            family="django-nextjs",
            size="full",
            cloud="gcp",
            ops=True,
            topology="omni",
        )
        _dry_run_plan(manifest, tmp_path)  # should not raise

    def test_dry_run_no_ops_when_flag_false(self, tmp_path: Path) -> None:
        """Dry-run with cloud set but ops=False does not include ops steps."""
        manifest = BoilerworksManifest(
            project="test-app",
            family="django-nextjs",
            size="full",
            cloud="aws",
            ops=False,
        )
        _dry_run_plan(manifest, tmp_path)  # should not raise

    def test_dry_run_shows_mobile_step(self, tmp_path: Path) -> None:
        manifest = BoilerworksManifest(
            project="test-app",
            family="django-nextjs",
            size="full",
            mobile=True,
        )
        _dry_run_plan(manifest, tmp_path)


class TestWriteOpsConfig:
    def _make_ops_dir(self, tmp_path: Path, cloud: str) -> Path:
        ops_dir = tmp_path / "ops"
        cloud_dir = ops_dir / cloud
        cloud_dir.mkdir(parents=True)
        config = cloud_dir / "config.env"
        config.write_text('PROJECT="boilerworks"\nAWS_REGION="us-west-2"\nOWNER="conflict"\n')
        return ops_dir

    def test_aws_config_written(self, tmp_path: Path) -> None:
        ops_dir = self._make_ops_dir(tmp_path, "aws")
        _write_ops_config(ops_dir, "aws", "myproject", "eu-west-1", "myproject.com")

        content = (ops_dir / "aws" / "config.env").read_text()
        assert 'PROJECT="myproject"' in content
        assert 'AWS_REGION="eu-west-1"' in content
        assert 'OWNER="myproject"' in content
        assert 'DOMAIN="myproject.com"' in content

    def test_gcp_config_written(self, tmp_path: Path) -> None:
        ops_dir = self._make_ops_dir(tmp_path, "gcp")
        _write_ops_config(ops_dir, "gcp", "myproject", "us-central1", None)

        content = (ops_dir / "gcp" / "config.env").read_text()
        assert 'PROJECT="myproject"' in content
        assert 'GCP_REGION="us-central1"' in content
        assert "DOMAIN" not in content

    def test_azure_config_default_region(self, tmp_path: Path) -> None:
        ops_dir = self._make_ops_dir(tmp_path, "azure")
        _write_ops_config(ops_dir, "azure", "myproject", None, None)

        content = (ops_dir / "azure" / "config.env").read_text()
        assert 'AZURE_REGION="eastus"' in content

    def test_missing_config_file_is_noop(self, tmp_path: Path) -> None:
        """If config.env doesn't exist yet, write_ops_config should not raise."""
        ops_dir = tmp_path / "ops"
        ops_dir.mkdir()
        (ops_dir / "aws").mkdir()
        # No config.env file
        _write_ops_config(ops_dir, "aws", "myproject", "us-east-1", None)


class TestCloneAndRenderOps:
    def _fake_clone(self, src: Path) -> None:
        """Create a fake clone that looks like a minimal boilerworks-opscode."""
        src.mkdir(parents=True, exist_ok=True)
        (src / ".git").mkdir()
        (src / "aws").mkdir()
        (src / "aws" / "config.env").write_text('PROJECT="boilerworks"\nAWS_REGION="us-west-2"\nOWNER="conflict"\n')
        (src / "README.md").write_text("# Boilerworks Opscode\nBoilerworks infrastructure.\n")

    def test_ops_clone_and_render_standard(self, tmp_path: Path) -> None:
        """_clone_and_render_ops populates dest and renders project name."""
        ops_dest = tmp_path / "myproject-ops"

        def fake_clone(repo: str, dest: Path) -> None:
            self._fake_clone(dest)

        progress = MagicMock()
        progress.add_task.return_value = "task-id"

        with patch("boilerworks.generator._clone_repo", side_effect=fake_clone):
            _clone_and_render_ops("myproject", "aws", "us-east-1", "myproject.com", ops_dest, progress)

        assert ops_dest.exists()
        assert not (ops_dest / ".git").exists()
        config_content = (ops_dest / "aws" / "config.env").read_text()
        assert 'PROJECT="myproject"' in config_content

    def test_ops_clone_failure_exits(self, tmp_path: Path) -> None:
        """When cloning ops fails, process exits."""
        ops_dest = tmp_path / "myproject-ops"
        progress = MagicMock()
        progress.add_task.return_value = "task-id"

        with (
            patch("boilerworks.generator._clone_repo", side_effect=RuntimeError("clone failed")),
            pytest.raises(SystemExit),
        ):
            _clone_and_render_ops("myproject", "aws", "us-east-1", None, ops_dest, progress)


class TestGenerateFromManifestErrors:
    def test_missing_manifest_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            generate_from_manifest(
                manifest_path=str(tmp_path / "nonexistent.yaml"),
                output_dir=str(tmp_path),
            )

    def test_invalid_manifest_yaml_exits(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "boilerworks.yaml"
        bad_yaml.write_text("project: Invalid Name With Spaces\nfamily: django-nextjs\nsize: full\n")
        with pytest.raises(SystemExit):
            generate_from_manifest(
                manifest_path=str(bad_yaml),
                output_dir=str(tmp_path),
            )

    def test_existing_project_dir_exits(self, tmp_path: Path, valid_manifest: BoilerworksManifest) -> None:
        manifest_file = tmp_path / "boilerworks.yaml"
        valid_manifest.to_file(manifest_file)

        # Pre-create the project dir
        (tmp_path / valid_manifest.project).mkdir()

        with pytest.raises(SystemExit):
            generate_from_manifest(
                manifest_path=str(manifest_file),
                output_dir=str(tmp_path),
            )


class TestGenerateWithOps:
    """Integration-style tests using mocked git operations."""

    def _seed_template(self, dest: Path, project: str = "boilerworks") -> None:
        """Create a minimal template directory (simulates cloned repo)."""
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir()
        (dest / "README.md").write_text(f"# {project.title()}\nA {project} app.\n")
        (dest / "docker-compose.yaml").write_text(f"services:\n  db:\n    image: postgres\n    # {project}\n")

    def _seed_opscode(self, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir()
        (dest / "aws").mkdir()
        (dest / "aws" / "config.env").write_text('PROJECT="boilerworks"\nAWS_REGION="us-west-2"\nOWNER="conflict"\n')
        (dest / "README.md").write_text("# Boilerworks Opscode\n")

    def test_generate_standard_with_ops(self, tmp_path: Path) -> None:
        """Standard topology: app and ops end up as sibling dirs."""
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            topology="standard",
            cloud="aws",
            ops=True,
            region="us-east-1",
        )
        manifest_file = tmp_path / "boilerworks.yaml"
        manifest.to_file(manifest_file)

        call_count = 0

        def fake_clone(repo: str, dest: Path) -> None:
            nonlocal call_count
            call_count += 1
            if "opscode" in repo:
                self._seed_opscode(dest)
            else:
                self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert call_count == 2
        assert (tmp_path / "myapp").exists()
        assert (tmp_path / "myapp-ops").exists()
        assert not (tmp_path / "myapp-ops" / ".git").exists()

    def test_generate_omni_with_ops(self, tmp_path: Path) -> None:
        """Omni topology: ops/ lives inside the app directory."""
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            topology="omni",
            cloud="aws",
            ops=True,
            region="us-east-1",
        )
        manifest_file = tmp_path / "boilerworks.yaml"
        manifest.to_file(manifest_file)

        call_count = 0

        def fake_clone(repo: str, dest: Path) -> None:
            nonlocal call_count
            call_count += 1
            if "opscode" in repo:
                self._seed_opscode(dest)
            else:
                self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert call_count == 2
        assert (tmp_path / "myapp").exists()
        assert (tmp_path / "myapp" / "ops").exists()

    def test_generate_without_ops(self, tmp_path: Path) -> None:
        """When ops=False, only the app template is cloned."""
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            topology="standard",
            cloud="aws",
            ops=False,
        )
        manifest_file = tmp_path / "boilerworks.yaml"
        manifest.to_file(manifest_file)

        call_count = 0

        def fake_clone(repo: str, dest: Path) -> None:
            nonlocal call_count
            call_count += 1
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert call_count == 1
        assert (tmp_path / "myapp").exists()
        assert not (tmp_path / "myapp-ops").exists()

    def test_generate_existing_ops_dir_exits(self, tmp_path: Path) -> None:
        """Standard topology: if ops dir already exists, exits cleanly."""
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            topology="standard",
            cloud="aws",
            ops=True,
        )
        manifest_file = tmp_path / "boilerworks.yaml"
        manifest.to_file(manifest_file)

        # Pre-create ops dir
        (tmp_path / "myapp-ops").mkdir()

        def fake_clone(repo: str, dest: Path) -> None:
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
            pytest.raises(SystemExit),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        shutil.rmtree(tmp_path / "myapp", ignore_errors=True)
