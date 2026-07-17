"""Boilerworks CLI — main entry point."""

from __future__ import annotations

import json
import sys

import click

from boilerworks import __version__


@click.group()
@click.version_option(__version__, prog_name="boilerworks")
def main() -> None:
    """Boilerworks — production-ready project templates."""


@main.command()
def setup() -> None:
    """Interactive wizard → writes boilerworks.yaml."""
    from boilerworks.wizard import run_wizard

    run_wizard()


@main.command(name="init")
@click.option("--manifest", "manifest_path", default=None, help="Path to boilerworks.yaml")
@click.option("--output", "output_dir", default=".", show_default=True, help="Output directory for generated project")
@click.option("--dry-run", is_flag=True, default=False, help="Print what would happen without doing it")
def init_command(manifest_path: str | None, output_dir: str, dry_run: bool) -> None:
    """Clone a template and configure it from boilerworks.yaml."""
    from boilerworks.generator import generate_from_manifest

    generate_from_manifest(manifest_path=manifest_path, output_dir=output_dir, dry_run=dry_run)


@main.command()
@click.option("--ops-dir", default=None, help="Path to ops directory (default: ../{project}-ops)")
@click.option("--dry-run", is_flag=True, default=True, help="Show execution plan (v1 only supports dry-run)")
def bootstrap(ops_dir: str | None, dry_run: bool) -> None:
    """Show infrastructure bootstrap plan (Terraform — v2)."""
    from boilerworks.bootstrap import run_bootstrap

    run_bootstrap(ops_dir=ops_dir, dry_run=dry_run)


@main.command(name="list")
@click.option("--size", type=click.Choice(["full", "micro", "edge"]), default=None, help="Filter by template size")
@click.option(
    "--language",
    type=click.Choice(["python", "typescript", "ruby", "php", "java", "go", "elixir", "rust", "svelte"]),
    default=None,
    help="Filter by primary language",
)
@click.option("--status", type=click.Choice(["done", "building", "planned"]), default=None, help="Filter by status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output machine-readable JSON instead of a table")
def list_command(size: str | None, language: str | None, status: str | None, as_json: bool) -> None:
    """List all available templates."""
    from boilerworks.console import print_template_table
    from boilerworks.registry import Registry

    registry = Registry()
    templates = registry.list_all()

    if size:
        templates = [t for t in templates if t.size == size]
    if language:
        templates = [t for t in templates if t.language == language]
    if status:
        templates = [t for t in templates if t.status == status]

    if as_json:
        rows = [
            {
                "name": t.name,
                "repo": t.repo,
                "github_url": t.github_url,
                "size": t.size,
                "language": t.language,
                "backend": t.backend,
                "frontend": t.frontend,
                "status": t.status,
                "best_for": t.best_for,
            }
            for t in templates
        ]
        click.echo(json.dumps(rows, indent=2))
        return

    print_template_table(templates)


@main.command(name="info")
@click.argument("name")
def info_command(name: str) -> None:
    """Show full details for a single template, including its GitHub URL."""
    from boilerworks.console import print_error, print_info, print_template_detail
    from boilerworks.registry import Registry

    registry = Registry()
    template = registry.get_by_name(name)

    if template is None:
        print_error(f"Unknown template: {name}")
        suggestions = registry.search(name)
        if suggestions:
            print_info("Did you mean: " + ", ".join(t.name for t in suggestions[:5]))
        else:
            print_info("Run [bold]boilerworks list[/bold] to see all templates.")
        sys.exit(1)

    print_template_detail(template)


if __name__ == "__main__":
    main()  # pragma: no cover
