"""Tests for boilerworks.generator."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from boilerworks.generator import (
    _clone_and_render_ops,
    _clone_repo,
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


class TestCloneRepo:
    """_clone_repo tries SSH, falls back to HTTPS, and reports both errors on failure."""

    @staticmethod
    def _is_ssh(cmd: list[str]) -> bool:
        return any("git@github.com" in part for part in cmd)

    def test_ssh_success_skips_https(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], capture_output: bool = False, text: bool = False, **_: object):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("boilerworks.generator.subprocess.run", side_effect=fake_run):
            _clone_repo("ConflictHQ/boilerworks-x", tmp_path / "dest")

        assert len(calls) == 1  # HTTPS never attempted
        assert self._is_ssh(calls[0])

    def test_https_fallback_succeeds(self, tmp_path: Path) -> None:
        def fake_run(cmd: list[str], capture_output: bool = False, text: bool = False, **_: object):
            rc = 1 if self._is_ssh(cmd) else 0
            return subprocess.CompletedProcess(cmd, rc, "", "ssh unavailable" if rc else "")

        with patch("boilerworks.generator.subprocess.run", side_effect=fake_run):
            _clone_repo("ConflictHQ/boilerworks-x", tmp_path / "dest")  # must not raise

    def test_both_fail_reports_both_errors_and_network_hint(self, tmp_path: Path) -> None:
        def fake_run(cmd: list[str], capture_output: bool = False, text: bool = False, **_: object):
            err = "SSH_BOOM" if self._is_ssh(cmd) else "HTTPS_BOOM"
            return subprocess.CompletedProcess(cmd, 128, "", err)

        with (
            patch("boilerworks.generator.subprocess.run", side_effect=fake_run),
            pytest.raises(RuntimeError) as exc,
        ):
            _clone_repo("ConflictHQ/boilerworks-x", tmp_path / "dest")

        msg = str(exc.value)
        assert "SSH_BOOM" in msg  # SSH error surfaced
        assert "HTTPS_BOOM" in msg  # HTTPS error surfaced, not mislabeled as SSH
        assert "network access" in msg  # generic failure → network hint

    def test_private_repo_failure_triggers_auth_hint(self, tmp_path: Path) -> None:
        def fake_run(cmd: list[str], capture_output: bool = False, text: bool = False, **_: object):
            if self._is_ssh(cmd):
                err = "ERROR: Repository not found.\nfatal: Could not read from remote repository."
            else:
                err = "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
            return subprocess.CompletedProcess(cmd, 128, "", err)

        with (
            patch("boilerworks.generator.subprocess.run", side_effect=fake_run),
            pytest.raises(RuntimeError) as exc,
        ):
            _clone_repo("ConflictHQ/boilerworks-private", tmp_path / "dest")

        msg = str(exc.value)
        assert "private" in msg.lower()
        assert "gh auth login" in msg


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


class TestGenerateWithAddons:
    """mobile and web_presence flags clone addon templates into the app repo."""

    def _seed_template(self, dest: Path, project: str = "boilerworks") -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir()
        (dest / "README.md").write_text(f"# {project.title()}\nA {project} app.\n")

    def _manifest_file(self, tmp_path: Path, *, mobile: bool = False, web_presence: bool = False) -> Path:
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            topology="standard",
            mobile=mobile,
            web_presence=web_presence,
        )
        manifest_file = tmp_path / "boilerworks.yaml"
        manifest.to_file(manifest_file)
        return manifest_file

    def test_generate_with_mobile(self, tmp_path: Path) -> None:
        """mobile=True clones the react-native-expo repo into mobile/ inside the app."""
        manifest_file = self._manifest_file(tmp_path, mobile=True)
        cloned: list[str] = []

        def fake_clone(repo: str, dest: Path) -> None:
            cloned.append(repo)
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert "ConflictHQ/boilerworks-react-native-expo" in cloned
        assert (tmp_path / "myapp" / "mobile").exists()
        assert not (tmp_path / "myapp" / "mobile" / ".git").exists()
        assert "Myapp" in (tmp_path / "myapp" / "mobile" / "README.md").read_text()

    def test_generate_with_web_presence(self, tmp_path: Path) -> None:
        """web_presence=True clones the astro-site repo into site/ inside the app."""
        manifest_file = self._manifest_file(tmp_path, web_presence=True)
        cloned: list[str] = []

        def fake_clone(repo: str, dest: Path) -> None:
            cloned.append(repo)
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert "ConflictHQ/boilerworks-astro-site" in cloned
        assert (tmp_path / "myapp" / "site").exists()
        assert not (tmp_path / "myapp" / "site" / ".git").exists()

    def test_generate_with_both_addons(self, tmp_path: Path) -> None:
        """Both flags: app + mobile/ + site/ (three clones total)."""
        manifest_file = self._manifest_file(tmp_path, mobile=True, web_presence=True)
        cloned: list[str] = []

        def fake_clone(repo: str, dest: Path) -> None:
            cloned.append(repo)
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert len(cloned) == 3
        assert (tmp_path / "myapp" / "mobile").exists()
        assert (tmp_path / "myapp" / "site").exists()

    def test_generate_without_addons_clones_nothing_extra(self, tmp_path: Path) -> None:
        manifest_file = self._manifest_file(tmp_path)
        cloned: list[str] = []

        def fake_clone(repo: str, dest: Path) -> None:
            cloned.append(repo)
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

        assert cloned == ["ConflictHQ/boilerworks-django-nextjs"]

    def test_addon_clone_failure_exits(self, tmp_path: Path) -> None:
        """When cloning an addon fails, process exits."""
        manifest_file = self._manifest_file(tmp_path, mobile=True)

        def fake_clone(repo: str, dest: Path) -> None:
            if "react-native-expo" in repo:
                raise RuntimeError("clone failed")
            self._seed_template(dest)

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("boilerworks.generator.subprocess.run"),
            pytest.raises(SystemExit),
        ):
            generate_from_manifest(manifest_path=str(manifest_file), output_dir=str(tmp_path))

    def test_dry_run_with_addons_creates_nothing(self, tmp_path: Path) -> None:
        """Dry-run with both addon flags shows the plan without cloning or writing."""
        manifest = BoilerworksManifest(
            project="myapp",
            family="django-nextjs",
            size="full",
            mobile=True,
            web_presence=True,
        )
        _dry_run_plan(manifest, tmp_path)
        assert not (tmp_path / "myapp").exists()
