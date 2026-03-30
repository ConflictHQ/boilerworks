"""Project generator — clone → render → rename → git init."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from boilerworks.console import console, print_error, print_info, print_success
from boilerworks.manifest import BoilerworksManifest
from boilerworks.registry import Registry
from boilerworks.renderer import build_replacements, rename_boilerworks_paths, render_directory

_OPS_REPO = "ConflictHQ/boilerworks-opscode"

_NEXT_STEPS_TEMPLATE = """[bold]Project created at:[/bold] {project_dir}

[bold]Next steps:[/bold]
  cd {project}
  docker compose up -d
  # Visit http://localhost:3000

[bold]Documentation:[/bold]
  bootstrap.md  — conventions
  CLAUDE.md     — AI agent guide
"""

_NEXT_STEPS_OPS_STANDARD = """[bold]Infrastructure repo:[/bold] {ops_dir}

[bold]Infrastructure next steps:[/bold]
  cd {ops_name}
  # Edit {cloud}/config.env to review settings
  ./run.sh bootstrap {cloud} dev
  ./run.sh plan {cloud} dev

[bold]Documentation:[/bold]
  bootstrap.md  — Terraform conventions and setup
"""

_NEXT_STEPS_OPS_OMNI = """[bold]Infrastructure (ops/) is inside the app repo[/bold]

[bold]Infrastructure next steps:[/bold]
  cd {project}/ops
  # Edit {cloud}/config.env to review settings
  ./run.sh bootstrap {cloud} dev
  ./run.sh plan {cloud} dev

[bold]Documentation:[/bold]
  ops/bootstrap.md  — Terraform conventions and setup
"""


def _clone_repo(repo: str, dest: Path) -> None:
    """Clone repo to dest. Tries SSH first, falls back to HTTPS."""
    ssh_url = f"git@github.com:{repo}.git"
    https_url = f"https://github.com/{repo}.git"

    result = subprocess.run(
        ["git", "clone", "--depth", "1", ssh_url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # SSH failed — try HTTPS
        result = subprocess.run(
            ["git", "clone", "--depth", "1", https_url, str(dest)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to clone {repo}.\n"
                f"SSH error: {result.stderr.strip()}\n"
                "Ensure you have GitHub access (SSH key or gh auth login)."
            )


def _remove_git_dir(project_dir: Path) -> None:
    git_dir = project_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)


def _git_init(project_dir: Path, family: str) -> None:
    """Initialise a fresh git repo and make the initial commit."""
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"Initial project from boilerworks-{family}"],
        cwd=project_dir,
        capture_output=True,
    )


def _git_add_commit(project_dir: Path, message: str) -> None:
    """Stage all and commit in an existing repo."""
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=project_dir,
        capture_output=True,
    )


def _write_ops_config(ops_dir: Path, cloud: str, project: str, region: str | None, domain: str | None) -> None:
    """Write {cloud}/config.env with project-specific values."""
    config_path = ops_dir / cloud / "config.env"
    if not config_path.exists():
        return

    region_default = {"aws": "us-east-1", "gcp": "us-central1", "azure": "eastus"}.get(cloud, "us-east-1")
    effective_region = region or region_default

    lines = [
        "# -----------------------------------------------------------------------------",
        f"# {project} — {cloud.upper()} Configuration",
        "#",
        "# Shared configuration for all environments. Sourced by run.sh and bootstrap.sh.",
        "# Review and update before running bootstrap.",
        "# -----------------------------------------------------------------------------",
        "",
        "# Project slug — used in all resource naming",
        f'PROJECT="{project}"',
        "",
        f"# {cloud.upper()} region",
    ]

    if cloud == "aws":
        lines.append(f'AWS_REGION="{effective_region}"')
    elif cloud == "gcp":
        lines.append(f'GCP_REGION="{effective_region}"')
    elif cloud == "azure":
        lines.append(f'AZURE_REGION="{effective_region}"')

    lines += [
        "",
        "# Owner tag",
        f'OWNER="{project}"',
    ]

    if domain:
        lines += [
            "",
            "# Domain",
            f'DOMAIN="{domain}"',
        ]

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clone_and_render_ops(
    project: str,
    cloud: str,
    region: str | None,
    domain: str | None,
    dest: Path,
    progress: Progress,
) -> None:
    """Clone boilerworks-opscode, render, rename, and configure for this project."""
    task = progress.add_task(f"Cloning {_OPS_REPO}…", total=None)
    try:
        _clone_repo(_OPS_REPO, dest)
    except RuntimeError as exc:
        progress.stop()
        print_error(str(exc))
        sys.exit(1)
    progress.remove_task(task)

    task = progress.add_task("Removing .git/ from ops…", total=None)
    _remove_git_dir(dest)
    progress.remove_task(task)

    task = progress.add_task("Applying ops substitutions…", total=None)
    replacements = build_replacements(project)
    render_directory(dest, replacements)
    progress.remove_task(task)

    task = progress.add_task("Renaming ops paths…", total=None)
    rename_boilerworks_paths(dest, project)
    progress.remove_task(task)

    task = progress.add_task("Configuring ops for your project…", total=None)
    _write_ops_config(dest, cloud, project, region, domain)
    progress.remove_task(task)


def _dry_run_plan(manifest: BoilerworksManifest, output_dir: Path) -> None:
    """Print what would happen without doing it."""
    registry = Registry()
    template = registry.get_by_name(manifest.family)
    repo = template.repo if template else f"ConflictHQ/boilerworks-{manifest.family}"
    project_dir = output_dir / manifest.project

    console.print("\n[bold]Dry run — no files will be written[/bold]\n")
    steps = [
        f"[dim]1.[/dim] Clone [cyan]{repo}[/cyan]",
        "[dim]2.[/dim] Remove .git/ from cloned directory",
        f"[dim]3.[/dim] Replace all 'boilerworks' → '[bold]{manifest.project}[/bold]' (case-variant)",
        "[dim]4.[/dim] Rename files/dirs containing 'boilerworks'",
        "[dim]5.[/dim] Update CLAUDE.md and README.md headers",
        f"[dim]6.[/dim] git init + initial commit in [bold]{project_dir}[/bold]",
    ]
    if manifest.ops and manifest.cloud:
        ops_dest = f"{project_dir}/ops/" if manifest.topology == "omni" else str(output_dir / f"{manifest.project}-ops")
        steps += [
            f"[dim]7.[/dim] Clone [cyan]{_OPS_REPO}[/cyan] → [bold]{ops_dest}[/bold]",
            f"[dim]8.[/dim] Render + rename ops files (boilerworks → {manifest.project})",
            f"[dim]9.[/dim] Write [cyan]{manifest.cloud}/config.env[/cyan] (project, region, domain)",
        ]
        if manifest.topology == "omni":
            steps.append("[dim]10.[/dim] Recommit app repo to include ops/")
        else:
            steps.append(f"[dim]10.[/dim] git init ops repo in [bold]{ops_dest}[/bold]")

    if manifest.mobile:
        steps.append(f"[dim]{len(steps) + 1}.[/dim] Clone mobile template")

    for step in steps:
        console.print(f"  {step}")
    console.print(f"\n[dim]Output directory:[/dim] {project_dir}")


def generate_from_manifest(
    manifest_path: str | None,
    output_dir: str = ".",
    dry_run: bool = False,
) -> None:
    """Entry point called from the CLI."""
    manifest_file = Path(manifest_path) if manifest_path else Path("boilerworks.yaml")

    if not manifest_file.exists():
        print_error(f"Manifest not found: {manifest_file}")
        print_info("Run [bold]boilerworks setup[/bold] first to create boilerworks.yaml")
        sys.exit(1)

    try:
        manifest = BoilerworksManifest.from_file(manifest_file)
    except Exception as exc:
        print_error(f"Invalid manifest: {exc}")
        sys.exit(1)

    out = Path(output_dir).resolve()

    if dry_run:
        _dry_run_plan(manifest, out)
        return

    _generate(manifest, out)


def _generate(manifest: BoilerworksManifest, output_dir: Path) -> None:
    registry = Registry()
    template = registry.get_by_name(manifest.family)
    if template is None:
        print_error(f"Unknown template family: {manifest.family}")
        sys.exit(1)

    project_dir = output_dir / manifest.project

    if project_dir.exists():
        print_error(f"Directory already exists: {project_dir}")
        print_info("Delete it first or choose a different output directory.")
        sys.exit(1)

    replacements = build_replacements(manifest.project)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        # ── App template ──────────────────────────────────────────────────────
        task = progress.add_task(f"Cloning {template.repo}…", total=None)
        try:
            _clone_repo(template.repo, project_dir)
        except RuntimeError as exc:
            progress.stop()
            print_error(str(exc))
            sys.exit(1)
        progress.remove_task(task)

        task = progress.add_task("Removing .git/…", total=None)
        _remove_git_dir(project_dir)
        progress.remove_task(task)

        task = progress.add_task("Applying template substitutions…", total=None)
        render_directory(project_dir, replacements)
        progress.remove_task(task)

        task = progress.add_task("Renaming paths…", total=None)
        rename_boilerworks_paths(project_dir, manifest.project)
        progress.remove_task(task)

        # ── Ops (infra-as-code) ───────────────────────────────────────────────
        ops_dir: Path | None = None
        if manifest.ops and manifest.cloud:
            if manifest.topology == "omni":
                # Ops lives inside the app repo
                ops_dir = project_dir / "ops"
                _clone_and_render_ops(
                    manifest.project, manifest.cloud, manifest.region, manifest.domain, ops_dir, progress
                )
                # git init + commit includes ops/
                task = progress.add_task("Initialising git repository (app + ops)…", total=None)
                _git_init(project_dir, manifest.family)
                progress.remove_task(task)
            else:
                # Standard: app and ops are sibling repos
                task = progress.add_task("Initialising app git repository…", total=None)
                _git_init(project_dir, manifest.family)
                progress.remove_task(task)

                ops_dir = output_dir / f"{manifest.project}-ops"
                if ops_dir.exists():
                    print_error(f"Ops directory already exists: {ops_dir}")
                    print_info("Delete it first or choose a different output directory.")
                    sys.exit(1)
                _clone_and_render_ops(
                    manifest.project, manifest.cloud, manifest.region, manifest.domain, ops_dir, progress
                )
                task = progress.add_task("Initialising ops git repository…", total=None)
                _git_init(ops_dir, "opscode")
                progress.remove_task(task)
        else:
            # No ops — just init app
            task = progress.add_task("Initialising git repository…", total=None)
            _git_init(project_dir, manifest.family)
            progress.remove_task(task)

    print_success(f"Project [bold]{manifest.project}[/bold] created at [bold]{project_dir}[/bold]")

    from rich.panel import Panel

    next_steps = _NEXT_STEPS_TEMPLATE.format(project=manifest.project, project_dir=project_dir)

    if manifest.ops and manifest.cloud and ops_dir is not None:
        if manifest.topology == "omni":
            next_steps += _NEXT_STEPS_OPS_OMNI.format(
                project=manifest.project,
                cloud=manifest.cloud,
            )
        else:
            next_steps += _NEXT_STEPS_OPS_STANDARD.format(
                ops_dir=ops_dir,
                ops_name=f"{manifest.project}-ops",
                cloud=manifest.cloud,
            )

    console.print(
        Panel(
            next_steps.strip(),
            title="[bold green]Done![/bold green]",
            border_style="green",
        )
    )
