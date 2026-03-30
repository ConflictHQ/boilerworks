"""Tests for boilerworks.renderer."""

from __future__ import annotations

from pathlib import Path

from boilerworks.renderer import (
    _SKIP_DIRS,
    _SKIP_EXTENSIONS,
    build_replacements,
    rename_boilerworks_paths,
    render_directory,
    render_file,
)


class TestBuildReplacements:
    def test_lowercase_replacement(self) -> None:
        r = build_replacements("my-app")
        assert r["boilerworks"] == "my-app"

    def test_uppercase_replacement(self) -> None:
        r = build_replacements("my-app")
        assert r["BOILERWORKS"] == "MY-APP"

    def test_title_replacement(self) -> None:
        r = build_replacements("my-app")
        assert r["Boilerworks"] == "My-App"

    def test_underscore_prefix_replacement(self) -> None:
        r = build_replacements("my-app")
        assert r["boilerworks_"] == "my_app_"

    def test_underscore_suffix_replacement(self) -> None:
        r = build_replacements("my-app")
        assert r["_boilerworks"] == "_my_app"

    def test_single_word_project(self) -> None:
        r = build_replacements("myapp")
        assert r["boilerworks"] == "myapp"
        assert r["BOILERWORKS"] == "MYAPP"


class TestRenderFile:
    def test_replaces_lowercase(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("APP_NAME=boilerworks")
        replacements = build_replacements("my-app")
        changed = render_file(f, replacements)
        assert changed is True
        assert f.read_text() == "APP_NAME=my-app"

    def test_replaces_uppercase(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("DB_NAME=BOILERWORKS_DB")
        replacements = build_replacements("my-app")
        render_file(f, replacements)
        assert f.read_text() == "DB_NAME=MY-APP_DB"

    def test_no_match_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        changed = render_file(f, build_replacements("my-app"))
        assert changed is False
        assert f.read_text() == "hello world"

    def test_empty_file_unchanged(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        changed = render_file(f, build_replacements("my-app"))
        assert changed is False
        assert f.read_text() == ""

    def test_binary_extension_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG boilerworks")
        changed = render_file(f, build_replacements("my-app"))
        assert changed is False
        # File content unchanged
        assert b"boilerworks" in f.read_bytes()

    def test_lock_extension_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "uv.lock"
        f.write_text("boilerworks = 1.0")
        changed = render_file(f, build_replacements("my-app"))
        assert changed is False

    def test_multiple_replacements_in_one_file(self, tmp_path: Path) -> None:
        f = tmp_path / "settings.py"
        content = "APP = 'boilerworks'\nNAME = 'Boilerworks'\nKEY = 'BOILERWORKS'"
        f.write_text(content)
        render_file(f, build_replacements("cool-app"))
        result = f.read_text()
        assert "cool-app" in result
        assert "Cool-App" in result
        assert "COOL-APP" in result
        assert "boilerworks" not in result

    def test_case_variant_python_module(self, tmp_path: Path) -> None:
        f = tmp_path / "settings.py"
        f.write_text("from boilerworks_config import settings")
        replacements = build_replacements("myproject")
        render_file(f, replacements)
        assert f.read_text() == "from myproject_config import settings"


class TestRenderDirectory:
    def test_renders_text_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("APP = 'boilerworks'")
        (tmp_path / "README.md").write_text("# boilerworks\n")
        modified = render_directory(tmp_path, build_replacements("newapp"))
        assert len(modified) == 2

    def test_skips_excluded_dirs(self, tmp_path: Path) -> None:
        skip_dir = tmp_path / "node_modules"
        skip_dir.mkdir()
        (skip_dir / "file.js").write_text("module.exports = 'boilerworks'")
        modified = render_directory(tmp_path, build_replacements("newapp"))
        assert not any("node_modules" in str(p) for p in modified)
        # Original file unchanged
        assert "boilerworks" in (skip_dir / "file.js").read_text()

    def test_skips_git_dir(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("url = boilerworks")
        modified = render_directory(tmp_path, build_replacements("newapp"))
        assert not any(".git" in str(p) for p in modified)

    def test_skips_binary_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "logo.png").write_bytes(b"\x89PNG boilerworks")
        (tmp_path / "app.py").write_text("# boilerworks")
        modified = render_directory(tmp_path, build_replacements("newapp"))
        modified_names = [p.name for p in modified]
        assert "logo.png" not in modified_names
        assert "app.py" in modified_names

    def test_nested_directories(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src" / "config"
        subdir.mkdir(parents=True)
        (subdir / "settings.py").write_text("APP = 'boilerworks'")
        modified = render_directory(tmp_path, build_replacements("newapp"))
        assert len(modified) == 1
        assert (subdir / "settings.py").read_text() == "APP = 'newapp'"


class TestRenameBoilerworksPaths:
    def test_renames_file_with_boilerworks(self, tmp_path: Path) -> None:
        f = tmp_path / "boilerworks.iml"
        f.write_text("")
        renames = rename_boilerworks_paths(tmp_path, "my-project")
        assert len(renames) == 1
        assert not (tmp_path / "boilerworks.iml").exists()
        assert (tmp_path / "my-project.iml").exists()

    def test_renames_directory_with_boilerworks(self, tmp_path: Path) -> None:
        subdir = tmp_path / "boilerworks_config"
        subdir.mkdir()
        (subdir / "settings.py").write_text("")
        rename_boilerworks_paths(tmp_path, "myproject")
        assert not (tmp_path / "boilerworks_config").exists()
        assert (tmp_path / "myproject_config").exists()

    def test_no_boilerworks_paths_unchanged(self, tmp_path: Path) -> None:
        f = tmp_path / "other_file.txt"
        f.write_text("content")
        renames = rename_boilerworks_paths(tmp_path, "myproject")
        assert len(renames) == 0
        assert f.exists()


class TestSkipSets:
    def test_skip_dirs_contains_expected(self) -> None:
        assert ".git" in _SKIP_DIRS
        assert "node_modules" in _SKIP_DIRS
        assert "__pycache__" in _SKIP_DIRS
        assert ".venv" in _SKIP_DIRS

    def test_skip_extensions_contains_expected(self) -> None:
        assert ".png" in _SKIP_EXTENSIONS
        assert ".lock" in _SKIP_EXTENSIONS
        assert ".pyc" in _SKIP_EXTENSIONS
        assert ".woff" in _SKIP_EXTENSIONS
