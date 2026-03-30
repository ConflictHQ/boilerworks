"""File renderer — string replacement across a cloned template directory."""

from __future__ import annotations

import os
from pathlib import Path

# Directories to skip entirely during rendering
_SKIP_DIRS: frozenset[str] = frozenset(
    [".git", "node_modules", "vendor", "__pycache__", "_build", "deps", "target", ".venv"]
)

# Binary/lock file extensions to skip (don't attempt text replacement)
_SKIP_EXTENSIONS: frozenset[str] = frozenset(
    [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".lock",
        ".pyc",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".exe",
        ".bin",
        ".so",
        ".dylib",
        ".dll",
        ".wasm",
        ".db",
        ".sqlite",
        ".sqlite3",
    ]
)


def build_replacements(project: str) -> dict[str, str]:
    """Build the standard case-variant replacement map from a project name.

    E.g. project='my-app' produces:
      'boilerworks'  → 'my-app'
      'Boilerworks'  → 'My-App'
      'BOILERWORKS'  → 'MY-APP'
      'boilerworks_' → 'my_app_'   (underscore variant for Python identifiers)
    """
    # underscore variant (Python module names)
    project_under = project.replace("-", "_")
    project_title = project.replace("-", " ").title().replace(" ", "-")
    project_upper = project.upper()

    return {
        "boilerworks_": f"{project_under}_",
        "_boilerworks": f"_{project_under}",
        "BOILERWORKS": project_upper,
        "Boilerworks": project_title,
        "boilerworks": project,
    }


def render_file(path: Path, replacements: dict[str, str]) -> bool:
    """Apply string replacements to a single file in-place.

    Returns True if the file was modified, False if skipped or unchanged.
    """
    if path.suffix.lower() in _SKIP_EXTENSIONS:
        return False

    try:
        original = path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, PermissionError):
        # Binary or unreadable file — skip
        return False

    modified = original
    for old, new in replacements.items():
        modified = modified.replace(old, new)

    if modified == original:
        return False

    path.write_text(modified, encoding="utf-8")
    return True


def render_directory(
    root: Path,
    replacements: dict[str, str],
    skip_dirs: frozenset[str] | None = None,
    skip_extensions: frozenset[str] | None = None,
) -> list[Path]:
    """Apply replacements to all eligible files under root.

    Returns the list of files that were modified.
    """
    skip_d = skip_dirs if skip_dirs is not None else _SKIP_DIRS
    skip_e = skip_extensions if skip_extensions is not None else _SKIP_EXTENSIONS

    modified: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in-place so os.walk doesn't recurse into them
        dirnames[:] = [d for d in dirnames if d not in skip_d]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.suffix.lower() in skip_e:
                continue
            try:
                was_changed = render_file(filepath, replacements)
            except OSError:
                continue
            if was_changed:
                modified.append(filepath)

    return modified


def rename_boilerworks_paths(root: Path, project: str) -> list[tuple[Path, Path]]:
    """Rename any files or directories containing 'boilerworks' in their name.

    Walks the tree bottom-up so child renames happen before parents.
    Returns list of (old_path, new_path) pairs.
    """
    project_under = project.replace("-", "_")
    renames: list[tuple[Path, Path]] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        current_dir = Path(dirpath)

        # Rename files
        for filename in filenames:
            if "boilerworks" in filename.lower():
                old = current_dir / filename
                new_name = filename.replace("boilerworks", project).replace("BOILERWORKS", project.upper())
                new_name = new_name.replace("Boilerworks", project.replace("-", " ").title().replace(" ", "-"))
                # Also handle underscore variant
                new_name = new_name.replace("boilerworks_", f"{project_under}_")
                new = current_dir / new_name
                if old != new:
                    old.rename(new)
                    renames.append((old, new))

        # Rename subdirectories
        for dirname in dirnames:
            if "boilerworks" in dirname.lower():
                old = current_dir / dirname
                new_dirname = dirname.replace("boilerworks", project).replace("BOILERWORKS", project.upper())
                new_dirname = new_dirname.replace("Boilerworks", project.replace("-", " ").title().replace(" ", "-"))
                new_dirname = new_dirname.replace("boilerworks_", f"{project_under}_")
                new = current_dir / new_dirname
                if old != new and old.exists():
                    old.rename(new)
                    renames.append((old, new))

    return renames
