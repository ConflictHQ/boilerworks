"""Tests for boilerworks.happy_path and `boilerworks new`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from boilerworks.cli import main
from boilerworks.happy_path import (
    SUPPORTED,
    HappyPathApp,
    add_catalog_entry,
    apply_identity,
    catalog_entry,
    default_name,
    open_catalog_pr,
    register_apps,
    register_commands,
    slug_replacements,
    validate_repo,
)
from boilerworks.renderer import build_replacements, render_directory

_ROOT_MANIFEST = """astrolift_version = 1
name = "boilerworks-app"

[app]
slug = "boilerworks-app"
display_name = "Boilerworks"
repo = "ConflictHQ/boilerworks-{template}"

[[managed_services]]
kind = "postgres"
name = "boilerworks-app-db"
"""

_WEB_MANIFEST = """# ("boilerworks-app-web" becomes "<your app>-web").
name = "boilerworks-app-web"

[app]
slug = "boilerworks-app-web"
display_name = "Boilerworks Web"
repo = "ConflictHQ/boilerworks-{template}"
"""

_STORYBOOK_MANIFEST = """name = "storybook-boilerworks-app"

[app]
slug = "storybook-boilerworks-app"
display_name = "Boilerworks Storybook"
"""

_PRODUCT = """import { defineProduct, type NavModel } from "@calliopelabs/ui";

export const NAV: NavModel = [{ key: "home", label: "Home", groups: [] }];

export const product = defineProduct({
  id: "boilerworks",
  name: "Boilerworks",
  accent: "periwinkle",
  nav: NAV,
});
"""

_README = """```json
{
  "id": "boilerworks-app",
  "title": "Boilerworks",
  "repo": "ConflictHQ/boilerworks-{template}",
  "app": "storybook-boilerworks-app",
  "upstream": "web.conflict-storybook-boilerworks-app.svc.cluster.local:8080"
}
```
"""


def seed_template(dest: Path, template: str) -> None:
    """A minimal copy of a happy-path template: the three manifests, product.ts and the README entry."""
    web = dest / SUPPORTED[template]
    (web / "ui-app").mkdir(parents=True)
    (dest / "storybook").mkdir()
    (dest / ".git").mkdir()
    (dest / "astrolift.toml").write_text(_ROOT_MANIFEST.replace("{template}", template))
    (web / "astrolift.toml").write_text(_WEB_MANIFEST.replace("{template}", template))
    (dest / "storybook" / "astrolift.toml").write_text(_STORYBOOK_MANIFEST)
    (web / "ui-app" / "product.ts").write_text(_PRODUCT)
    (dest / "README.md").write_text(_README.replace("{template}", template))


def render(dest: Path, app: HappyPathApp) -> None:
    """What the generator does: happy-path replacements first, the standard ones, then the identity."""
    replacements = {
        **slug_replacements(app, f"ConflictHQ/boilerworks-{app.template}"),
        **build_replacements(app.project),
    }
    render_directory(dest, replacements)
    apply_identity(dest, app)


@pytest.fixture()
def app() -> HappyPathApp:
    return HappyPathApp(template="django-nextjs", project="acme-portal", name="Acme Portal", repo="acme/acme-portal")


class TestNames:
    def test_default_name(self) -> None:
        assert default_name("acme-portal") == "Acme Portal"
        assert default_name("shop") == "Shop"

    def test_validate_repo(self) -> None:
        assert validate_repo("acme/acme-portal") == "acme/acme-portal"
        with pytest.raises(ValueError):
            validate_repo("acme-portal")
        with pytest.raises(ValueError):
            validate_repo("https://github.com/acme/acme-portal")

    def test_apps(self, app: HappyPathApp) -> None:
        assert [(a.manifest, a.slug, a.display_name) for a in app.apps()] == [
            ("astrolift.toml", "acme-portal", "Acme Portal"),
            ("frontend/astrolift.toml", "acme-portal-web", "Acme Portal Web"),
            ("storybook/astrolift.toml", "storybook-acme-portal", "Acme Portal Storybook"),
        ]

    def test_nestjs_web_dir(self) -> None:
        app = HappyPathApp(template="nestjs-nextjs", project="x", name="X")
        assert app.apps()[1].manifest == "apps/web/astrolift.toml"
        assert app.product_file == "apps/web/ui-app/product.ts"


class TestRename:
    @pytest.mark.parametrize("template", sorted(SUPPORTED))
    def test_manifests_and_product(self, tmp_path: Path, template: str) -> None:
        app = HappyPathApp(template=template, project="acme-portal", name="Acme Portal", repo="acme/acme-portal")
        seed_template(tmp_path, template)
        render(tmp_path, app)

        root = (tmp_path / "astrolift.toml").read_text()
        assert 'name = "acme-portal"' in root
        assert 'slug = "acme-portal"' in root
        assert 'display_name = "Acme Portal"' in root
        assert 'repo = "acme/acme-portal"' in root
        assert 'name = "acme-portal-db"' in root

        web = (tmp_path / SUPPORTED[template] / "astrolift.toml").read_text()
        assert 'slug = "acme-portal-web"' in web
        assert 'display_name = "Acme Portal Web"' in web
        assert 'repo = "acme/acme-portal"' in web

        storybook = (tmp_path / "storybook" / "astrolift.toml").read_text()
        assert 'slug = "storybook-acme-portal"' in storybook
        assert 'display_name = "Acme Portal Storybook"' in storybook

        product = (tmp_path / app.product_file).read_text()
        assert 'id: "acme-portal",' in product
        assert 'name: "Acme Portal",' in product

        for path in tmp_path.rglob("*"):
            if path.is_file():
                text = path.read_text()
                assert "boilerworks" not in text.lower(), path

    def test_readme_entry_matches_printed_entry(self, tmp_path: Path, app: HappyPathApp) -> None:
        seed_template(tmp_path, app.template)
        render(tmp_path, app)
        readme = (tmp_path / "README.md").read_text()
        block = readme.split("```json\n")[1].split("```")[0]
        entry = catalog_entry(app)
        for key in ("id", "title", "repo", "app", "upstream"):
            assert json.loads(block)[key] == entry[key]

    def test_without_repo_keeps_standard_render(self, tmp_path: Path) -> None:
        app = HappyPathApp(template="fastapi-nextjs", project="acme", name="Acme")
        seed_template(tmp_path, app.template)
        render(tmp_path, app)
        assert 'slug = "storybook-acme"' in (tmp_path / "storybook" / "astrolift.toml").read_text()
        assert 'repo = "ConflictHQ/acme-fastapi-nextjs"' in (tmp_path / "astrolift.toml").read_text()

    def test_quotes_in_name_are_escaped(self, tmp_path: Path) -> None:
        app = HappyPathApp(template="django-nextjs", project="acme", name='Acme "Beta"')
        seed_template(tmp_path, app.template)
        render(tmp_path, app)
        assert 'display_name = "Acme \\"Beta\\""' in (tmp_path / "astrolift.toml").read_text()
        assert 'name: "Acme \\"Beta\\"",' in (tmp_path / app.product_file).read_text()

    def test_missing_files_are_skipped(self, tmp_path: Path, app: HappyPathApp) -> None:
        assert apply_identity(tmp_path, app) == []


class TestRegisterCommands:
    def test_one_command_per_manifest(self, app: HappyPathApp) -> None:
        commands = register_commands(app, "1111-2222")
        assert commands == [
            [
                "astro",
                "app",
                "register",
                "-f",
                manifest,
                "--manifest-path",
                manifest,
                "--project-id",
                "1111-2222",
                "--source-repo",
                "acme/acme-portal",
                "--yes",
            ]
            for manifest in ("astrolift.toml", "frontend/astrolift.toml", "storybook/astrolift.toml")
        ]

    def test_manifest_raw(self, app: HappyPathApp) -> None:
        assert all(cmd[-1] == "--manifest-raw" for cmd in register_commands(app, "p", manifest_raw=True))

    def test_needs_repo(self) -> None:
        with pytest.raises(ValueError):
            register_commands(HappyPathApp(template="django-nextjs", project="x", name="X"), "p")

    def test_runs_each_command_in_the_project(self, tmp_path: Path, app: HappyPathApp) -> None:
        calls: list[tuple[list[str], Path]] = []

        def fake_run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            calls.append((cmd, cwd))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        commands = register_commands(app, "p")
        with patch("boilerworks.happy_path.shutil.which", return_value="/usr/local/bin/astro"):
            assert register_apps(tmp_path, commands, run=fake_run) is True
        assert calls == [(cmd, tmp_path) for cmd in commands]

    def test_stops_at_first_failure(self, tmp_path: Path, app: HappyPathApp) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 1, "", "")

        with patch("boilerworks.happy_path.shutil.which", return_value="/usr/local/bin/astro"):
            assert register_apps(tmp_path, register_commands(app, "p"), run=fake_run) is False
        assert len(calls) == 1

    def test_no_astro_on_path(self, tmp_path: Path, app: HappyPathApp) -> None:
        def fail_run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("must not run")

        with patch("boilerworks.happy_path.shutil.which", return_value=None):
            assert register_apps(tmp_path, register_commands(app, "p"), run=fail_run) is False


class TestCatalog:
    def test_entry(self, app: HappyPathApp) -> None:
        assert catalog_entry(app) == {
            "id": "acme-portal",
            "title": "Acme Portal",
            "group": "web",
            "kind": "storybook",
            "repo": "acme/acme-portal",
            "app": "storybook-acme-portal",
            "upstream": "web.conflict-storybook-acme-portal.svc.cluster.local:8080",
        }

    def test_entry_needs_repo(self) -> None:
        with pytest.raises(ValueError):
            catalog_entry(HappyPathApp(template="django-nextjs", project="x", name="X"))

    def test_add_entry(self, app: HappyPathApp) -> None:
        catalogs = {"$comment": "c", "catalogs": [{"id": "ui", "app": "calliope-ui"}]}
        add_catalog_entry(catalogs, catalog_entry(app))
        assert catalogs["catalogs"][-1]["id"] == "acme-portal"

    def test_add_entry_refuses_duplicate(self, app: HappyPathApp) -> None:
        catalogs = {"catalogs": [{"id": "acme-portal", "app": "other"}]}
        with pytest.raises(ValueError):
            add_catalog_entry(catalogs, catalog_entry(app))

    def test_open_pr(self, tmp_path: Path, app: HappyPathApp) -> None:
        calls: list[list[str]] = []
        existing = {"$comment": "c", "catalogs": [{"id": "ui", "app": "calliope-ui"}]}

        def fake_run(cmd: list[str], cwd: Path | None = None, **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            if cmd[:3] == ["gh", "repo", "clone"]:
                Path(cmd[4]).mkdir()
                (Path(cmd[4]) / "catalogs.json").write_text(json.dumps(existing, indent=2) + "\n")
            out = "https://github.com/calliopeai/calliope-ux/pull/9\n" if cmd[:3] == ["gh", "pr", "create"] else ""
            return subprocess.CompletedProcess(cmd, 0, out, "")

        url = open_catalog_pr(catalog_entry(app), tmp_path, run=fake_run)

        assert url == "https://github.com/calliopeai/calliope-ux/pull/9"
        written = json.loads((tmp_path / "calliope-ux" / "catalogs.json").read_text())
        assert written["catalogs"][-1] == catalog_entry(app)
        assert ["git", "checkout", "-b", "catalog/acme-portal"] in calls
        assert ["git", "push", "-u", "origin", "catalog/acme-portal"] in calls
        assert calls[-1][:5] == ["gh", "pr", "create", "-R", "calliopeai/calliope-ux"]

    def test_open_pr_reports_failure(self, tmp_path: Path, app: HappyPathApp) -> None:
        def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(cmd, 1, "", "no access")

        with pytest.raises(RuntimeError, match="no access"):
            open_catalog_pr(catalog_entry(app), tmp_path, run=fake_run)


class TestNewCommand:
    def _invoke(self, tmp_path: Path, *args: str) -> tuple[object, list[list[str]]]:
        astro_calls: list[list[str]] = []

        def fake_clone(repo: str, dest: Path) -> None:
            seed_template(dest, repo.removeprefix("ConflictHQ/boilerworks-"))

        def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            # One subprocess module: the generator's git calls and the astro calls both land here.
            if cmd[0] == "astro":
                astro_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with (
            patch("boilerworks.generator._clone_repo", side_effect=fake_clone),
            patch("subprocess.run", side_effect=fake_run),
            patch("boilerworks.happy_path.shutil.which", return_value="/usr/local/bin/astro"),
        ):
            result = CliRunner().invoke(main, ["new", *args, "--output", str(tmp_path)])
        return result, astro_calls

    def test_help_lists_new(self) -> None:
        result = CliRunner().invoke(main, ["--help"])
        assert "new" in result.output

    def test_unsupported_template(self, tmp_path: Path) -> None:
        result, _ = self._invoke(tmp_path, "rails-hotwire", "acme")
        assert result.exit_code == 2

    def test_invalid_project(self, tmp_path: Path) -> None:
        result, _ = self._invoke(tmp_path, "django-nextjs", "Acme Portal")
        assert result.exit_code == 1

    def test_generates_without_side_effects_by_default(self, tmp_path: Path) -> None:
        result, astro_calls = self._invoke(tmp_path, "nestjs-nextjs", "acme-portal", "--repo", "acme/acme-portal")
        assert result.exit_code == 0, result.output
        assert astro_calls == []
        assert '"upstream"' not in result.output
        assert 'slug = "acme-portal-web"' in (tmp_path / "acme-portal" / "apps/web/astrolift.toml").read_text()
        assert 'name: "Acme Portal",' in (tmp_path / "acme-portal" / "apps/web/ui-app/product.ts").read_text()

    def test_register_and_print_catalog(self, tmp_path: Path) -> None:
        result, astro_calls = self._invoke(
            tmp_path,
            "fastapi-nextjs",
            "acme-portal",
            "--name",
            "Acme",
            "--repo",
            "acme/acme-portal",
            "--register",
            "--project-id",
            "p-1",
            "--catalog",
            "print",
        )
        assert result.exit_code == 0, result.output
        assert [cmd[4] for cmd in astro_calls] == [
            "astrolift.toml",
            "frontend/astrolift.toml",
            "storybook/astrolift.toml",
        ]
        assert "web.conflict-storybook-acme-portal.svc.cluster.local:8080" in result.output
        assert '"title": "Acme"' in result.output

    def test_register_needs_project_id(self, tmp_path: Path) -> None:
        result, _ = self._invoke(tmp_path, "django-nextjs", "acme", "--repo", "a/b", "--register")
        assert result.exit_code == 1
        assert not (tmp_path / "acme").exists()

    def test_catalog_needs_repo(self, tmp_path: Path) -> None:
        result, _ = self._invoke(tmp_path, "django-nextjs", "acme", "--catalog", "print")
        assert result.exit_code == 1

    def test_catalog_pr(self, tmp_path: Path) -> None:
        with patch("boilerworks.happy_path.open_catalog_pr", return_value="https://example.test/pr/1") as opened:
            result, _ = self._invoke(tmp_path, "django-nextjs", "acme", "--repo", "a/acme", "--catalog", "pr")
        assert result.exit_code == 0, result.output
        assert opened.call_args.args[0]["app"] == "storybook-acme"
        assert "https://example.test/pr/1" in result.output

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        result, astro_calls = self._invoke(
            tmp_path,
            "django-nextjs",
            "acme",
            "--repo",
            "a/acme",
            "--register",
            "--project-id",
            "p-1",
            "--catalog",
            "print",
            "--dry-run",
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "acme").exists()
        assert astro_calls == []
        assert "astro app register -f storybook/astrolift.toml" in result.output
        assert "storybook-acme" in result.output

    def test_prompts_when_interactive(self, tmp_path: Path) -> None:
        with (
            patch("boilerworks.happy_path._interactive", return_value=True),
            patch("boilerworks.happy_path._ask_confirm", return_value=False) as confirm,
            patch("boilerworks.happy_path._ask_catalog", return_value="print") as ask_catalog,
        ):
            result, astro_calls = self._invoke(tmp_path, "django-nextjs", "acme", "--repo", "a/acme")
        assert result.exit_code == 0, result.output
        confirm.assert_called_once()
        ask_catalog.assert_called_once()
        assert astro_calls == []
        assert "storybook-acme" in result.output

    def test_prompts_for_project_id(self, tmp_path: Path) -> None:
        with (
            patch("boilerworks.happy_path._interactive", return_value=True),
            patch("boilerworks.happy_path._ask_confirm", return_value=True),
            patch("boilerworks.happy_path._ask_text", return_value="p-9"),
            patch("boilerworks.happy_path._ask_catalog", return_value="skip"),
        ):
            result, astro_calls = self._invoke(tmp_path, "django-nextjs", "acme", "--repo", "a/acme")
        assert result.exit_code == 0, result.output
        assert len(astro_calls) == 3
        assert all("p-9" in cmd for cmd in astro_calls)

    def test_no_offers_without_repo(self, tmp_path: Path) -> None:
        with (
            patch("boilerworks.happy_path._interactive", return_value=True),
            patch("boilerworks.happy_path._ask_confirm") as confirm,
        ):
            result, astro_calls = self._invoke(tmp_path, "django-nextjs", "acme")
        assert result.exit_code == 0, result.output
        confirm.assert_not_called()
        assert astro_calls == []
