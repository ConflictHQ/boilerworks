"""The Calliope AI happy path: ``boilerworks new`` for the supported Next.js templates.

Each supported template ships ``@calliopelabs/ui``, a Storybook and three Astrolift manifests
(the backend at the root, the web app in its web directory, ``storybook/astrolift.toml``) with
placeholder slugs. ``new`` generates the project with those slugs and the product name renamed,
then, only when asked, registers the three apps with the Astrolift CLI and adds the Storybook
to the Calliope AI UX front door (``catalogs.json`` in calliopeai/calliope-ux).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from boilerworks.console import console, print_error, print_info, print_success

# Supported template → its Next.js web app directory (the second manifest and ui-app/ live there).
SUPPORTED: dict[str, str] = {
    "nestjs-nextjs": "apps/web",
    "django-nextjs": "frontend",
    "fastapi-nextjs": "frontend",
}

CATALOG_REPO = "calliopeai/calliope-ux"
# Astrolift namespaces an app's workloads as <org>-<app slug>; the front door runs in the conflict org.
CLUSTER_ORG = "conflict"
STORYBOOK_WORKLOAD = "web"

_PLACEHOLDER = "boilerworks-app"
_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$")

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class AstroliftApp:
    role: str  # backend | web | storybook
    manifest: str  # path from the project root
    slug: str
    display_name: str


@dataclass(frozen=True)
class HappyPathApp:
    template: str
    project: str
    name: str
    repo: str | None = None

    @property
    def web_dir(self) -> str:
        return SUPPORTED[self.template]

    @property
    def storybook_slug(self) -> str:
        return f"storybook-{self.project}"

    def apps(self) -> list[AstroliftApp]:
        return [
            AstroliftApp("backend", "astrolift.toml", self.project, self.name),
            AstroliftApp("web", f"{self.web_dir}/astrolift.toml", f"{self.project}-web", f"{self.name} Web"),
            AstroliftApp("storybook", "storybook/astrolift.toml", self.storybook_slug, f"{self.name} Storybook"),
        ]

    @property
    def product_file(self) -> str:
        return f"{self.web_dir}/ui-app/product.ts"


def default_name(project: str) -> str:
    """'my-app' → 'My App'."""
    return project.replace("-", " ").title()


def validate_repo(repo: str) -> str:
    if not _REPO_RE.match(repo):
        raise ValueError(f"repo '{repo}' must be in owner/name form")
    return repo


def slug_replacements(app: HappyPathApp, template_repo: str) -> dict[str, str]:
    """Replacements that must run before the standard 'boilerworks' → project ones, longest first.

    The placeholders appear in the manifests, the managed service names (boilerworks-app-db) and
    the README's commands and catalog entry; the template's own repo becomes the new app's repo.
    """
    replacements = {
        f"storybook-{_PLACEHOLDER}": app.storybook_slug,
        f"{_PLACEHOLDER}-web": f"{app.project}-web",
        _PLACEHOLDER: app.project,
        # The README's catalog entry, so it matches the one `new` prints.
        '"title": "Boilerworks",': f'"title": {_quoted(app.name)},',
    }
    if app.repo:
        replacements[template_repo] = app.repo
    return replacements


def _quoted(value: str) -> str:
    # A JSON string is a valid TOML basic string and a valid TypeScript string literal.
    return json.dumps(value, ensure_ascii=False)


def apply_identity(project_dir: Path, app: HappyPathApp) -> list[Path]:
    """Set the display names in the three manifests and the product id and name in ui-app/product.ts.

    Runs after the standard render, which has already turned the slugs into the project's.
    Returns the files changed.
    """
    changed: list[Path] = []
    for astro_app in app.apps():
        path = project_dir / astro_app.manifest
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        line = f"display_name = {_quoted(astro_app.display_name)}"
        new = re.sub(r'^display_name = ".*"$', line.replace("\\", "\\\\"), text, count=1, flags=re.M)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path)

    product = project_dir / app.product_file
    if product.exists():
        text = product.read_text(encoding="utf-8")
        start = text.find("defineProduct({", text.find("export const product"))
        if start != -1:
            head, tail = text[:start], text[start:]
            tail = re.sub(
                r'^(\s*)id: ".*",$', lambda m: f"{m[1]}id: {_quoted(app.project)},", tail, count=1, flags=re.M
            )
            tail = re.sub(
                r'^(\s*)name: ".*",$', lambda m: f"{m[1]}name: {_quoted(app.name)},", tail, count=1, flags=re.M
            )
            if head + tail != text:
                product.write_text(head + tail, encoding="utf-8")
                changed.append(product)
    return changed


def register_commands(app: HappyPathApp, project_id: str, manifest_raw: bool = False) -> list[list[str]]:
    """`astro app register` for each manifest, run from the project root."""
    if not app.repo:
        raise ValueError("registering needs the app's repo (--repo owner/name)")
    commands = []
    for astro_app in app.apps():
        cmd = [
            "astro",
            "app",
            "register",
            "-f",
            astro_app.manifest,
            "--manifest-path",
            astro_app.manifest,
            "--project-id",
            project_id,
            "--source-repo",
            app.repo,
            "--yes",
        ]
        if manifest_raw:
            cmd.append("--manifest-raw")
        commands.append(cmd)
    return commands


def register_apps(project_dir: Path, commands: list[list[str]], run: Runner | None = None) -> bool:
    """Run the register commands in order; stop at the first failure. Returns True when all succeed."""
    run = run or subprocess.run
    if shutil.which("astro") is None:
        print_error("The Astrolift CLI (astro) is not on PATH. Install it, run `astro login`, then:")
        for cmd in commands:
            console.print(f"  {' '.join(cmd)}", markup=False, highlight=False)
        return False
    for cmd in commands:
        console.print(f"$ {' '.join(cmd)}", markup=False, highlight=False)
        result = run(cmd, cwd=project_dir)
        if result.returncode != 0:
            print_error(f"astro app register failed for {cmd[4]} (exit {result.returncode})")
            return False
    print_success("Registered the backend, web and Storybook apps with Astrolift")
    return True


def catalog_entry(app: HappyPathApp) -> dict[str, str]:
    """The front door's catalogs.json entry for the app's Storybook."""
    if not app.repo:
        raise ValueError("the catalog entry needs the app's repo (--repo owner/name)")
    return {
        "id": app.project,
        "title": app.name,
        "group": "web",
        "kind": "storybook",
        "repo": app.repo,
        "app": app.storybook_slug,
        "upstream": f"{STORYBOOK_WORKLOAD}.{CLUSTER_ORG}-{app.storybook_slug}.svc.cluster.local:8080",
    }


def add_catalog_entry(catalogs: dict[str, Any], entry: dict[str, str]) -> dict[str, Any]:
    """Append the entry to a parsed catalogs.json, refusing an id or app already listed."""
    for existing in catalogs.get("catalogs", []):
        if existing.get("id") == entry["id"] or existing.get("app") == entry["app"]:
            raise ValueError(f"catalogs.json already has an entry for id '{entry['id']}' or app '{entry['app']}'")
    catalogs.setdefault("catalogs", []).append(entry)
    return catalogs


def _check(run: Runner, cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {result.stderr.strip()}")
    return result


def open_catalog_pr(entry: dict[str, str], workdir: Path, run: Runner | None = None) -> str:
    """Clone the front door, add the entry on a branch and open a PR with gh. Returns the PR URL."""
    run = run or subprocess.run
    clone = workdir / "calliope-ux"
    _check(run, ["gh", "repo", "clone", CATALOG_REPO, str(clone), "--", "--depth", "1"])
    path = clone / "catalogs.json"
    catalogs = add_catalog_entry(json.loads(path.read_text(encoding="utf-8")), entry)
    path.write_text(json.dumps(catalogs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    branch = f"catalog/{entry['id']}"
    title = f"Add {entry['title']} to the front door"
    body = (
        f"Adds the Storybook of `{entry['repo']}` (Astrolift app `{entry['app']}`) as a section of the front door.\n\n"
        f"```json\n{json.dumps(entry, indent=2, ensure_ascii=False)}\n```\n\n"
        "The Storybook app must be deployed on the cluster before this merges."
    )
    _check(run, ["git", "checkout", "-b", branch], cwd=clone)
    _check(run, ["git", "add", "catalogs.json"], cwd=clone)
    _check(run, ["git", "commit", "-m", title], cwd=clone)
    _check(run, ["git", "push", "-u", "origin", branch], cwd=clone)
    result = _check(
        run,
        [
            "gh",
            "pr",
            "create",
            "-R",
            CATALOG_REPO,
            "--head",
            branch,
            "--base",
            "main",
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=clone,
    )
    return result.stdout.strip()


def print_catalog_entry(entry: dict[str, str]) -> None:
    console.print(f"\n[bold]Front door entry[/bold] (add to catalogs.json in {CATALOG_REPO}):\n")
    console.print(json.dumps(entry, indent=2, ensure_ascii=False), markup=False, highlight=False)


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask_text(message: str) -> str:
    import questionary

    return (questionary.text(message).ask() or "").strip()


def _ask_confirm(message: str) -> bool:
    import questionary

    return bool(questionary.confirm(message, default=False).ask())


def _ask_catalog() -> str:
    import questionary

    choice = questionary.select(
        "Add the Storybook to the Calliope AI UX front door?",
        choices=["skip", "print", "pr"],
        default="skip",
    ).ask()
    return choice or "skip"


def run_new(
    template: str,
    project: str,
    name: str | None,
    repo: str | None,
    output_dir: str,
    dry_run: bool,
    register: bool | None,
    project_id: str | None,
    manifest_raw: bool,
    catalog: str | None,
) -> None:
    """Entry point for ``boilerworks new``. ``register``/``catalog`` of None means ask when interactive."""
    from boilerworks.generator import _dry_run_plan, _generate
    from boilerworks.manifest import BoilerworksManifest
    from boilerworks.registry import Registry

    try:
        manifest = BoilerworksManifest(project=project, family=template, size="full")
        if repo:
            validate_repo(repo)
    except ValueError as exc:
        print_error(str(exc))
        sys.exit(1)

    if register and not project_id:
        print_error("--register needs --project-id (the Astrolift project GUID)")
        sys.exit(1)
    if (register or catalog in ("print", "pr")) and not repo:
        print_error("--register and --catalog need --repo owner/name (the new app's GitHub repo)")
        sys.exit(1)

    template_info = Registry().get_by_name(template)
    assert template_info is not None  # validated by the manifest
    app = HappyPathApp(template=template, project=project, name=name or default_name(project), repo=repo)
    out = Path(output_dir).resolve()

    if dry_run:
        _dry_run_plan(manifest, out)
        console.print("\n[bold]Calliope AI happy path[/bold]")
        for astro_app in app.apps():
            console.print(f"  {astro_app.manifest}: {astro_app.slug} ({astro_app.display_name})", markup=False)
        console.print(f"  {app.product_file}: id {app.project}, name {app.name}", markup=False)
        if register:
            assert project_id is not None
            for cmd in register_commands(app, project_id, manifest_raw):
                console.print(f"  $ {' '.join(cmd)}", markup=False, highlight=False)
        if catalog in ("print", "pr"):
            print_catalog_entry(catalog_entry(app))
        return

    project_dir = _generate(
        manifest,
        out,
        extra_replacements=slug_replacements(app, template_info.repo),
        post_render=lambda d: apply_identity(d, app),
    )

    # Registration and the catalog entry name the repo the manifests were rendered with, so
    # without --repo they are not offered.
    if not app.repo:
        print_info(
            "Pass --repo owner/name to register the apps with Astrolift and add the Storybook to the front door."
        )
        return

    # ── Astrolift registration (only when asked) ──────────────────────────────
    if register is None and _interactive():
        register = _ask_confirm("Register the backend, web and Storybook apps with Astrolift (astro app register)?")
        if register:
            project_id = _ask_text("Astrolift project GUID:")
            if not project_id:
                print_error("Registration needs a project GUID; skipped.")
                register = False
    if register:
        assert project_id is not None
        register_apps(project_dir, register_commands(app, project_id, manifest_raw))

    # ── Front door catalog entry (only when asked) ────────────────────────────
    if catalog is None and _interactive():
        catalog = _ask_catalog()
    if catalog not in ("print", "pr"):
        return
    entry = catalog_entry(app)
    print_catalog_entry(entry)
    if catalog == "pr":
        with tempfile.TemporaryDirectory() as tmp:
            try:
                url = open_catalog_pr(entry, Path(tmp))
            except (RuntimeError, ValueError) as exc:
                print_error(str(exc))
                sys.exit(1)
        print_success(f"Opened the front door PR: {url}")
