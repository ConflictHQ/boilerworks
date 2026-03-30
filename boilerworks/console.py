"""Rich output helpers for the Boilerworks CLI."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from boilerworks.registry import TemplateInfo

console = Console()


_STATUS_STYLE: dict[str, str] = {
    "done": "bold green",
    "building": "bold yellow",
    "planned": "dim",
}

_SIZE_STYLE: dict[str, str] = {
    "full": "cyan",
    "micro": "magenta",
    "edge": "blue",
}


def _status_badge(status: str) -> Text:
    style = _STATUS_STYLE.get(status, "")
    labels = {"done": "● done", "building": "◐ building", "planned": "○ planned"}
    return Text(labels.get(status, status), style=style)


def print_template_table(templates: list[TemplateInfo]) -> None:
    """Print a Rich table of templates."""
    if not templates:
        console.print("[yellow]No templates match your filters.[/yellow]")
        return

    table = Table(
        title=f"Boilerworks Templates ({len(templates)})",
        show_lines=False,
        header_style="bold white",
        border_style="dim",
        expand=False,
    )

    table.add_column("Name", style="bold", min_width=20)
    table.add_column("Size", min_width=6)
    table.add_column("Language", min_width=11)
    table.add_column("Backend", min_width=16)
    table.add_column("Frontend", min_width=16)
    table.add_column("Status", min_width=13)
    table.add_column("Description", min_width=30)

    for t in templates:
        size_text = Text(t.size, style=_SIZE_STYLE.get(t.size, ""))
        table.add_row(
            t.name,
            size_text,
            t.language,
            t.backend,
            t.frontend if t.frontend else "—",
            _status_badge(t.status),
            t.description,
        )

    console.print(table)


def print_template_detail(template: TemplateInfo) -> None:
    """Print a Rich panel with full template details."""
    lines = [
        f"[bold]Name:[/bold]       {template.name}",
        f"[bold]Repo:[/bold]       {template.repo}",
        f"[bold]Size:[/bold]       {template.size}",
        f"[bold]Language:[/bold]   {template.language}",
        f"[bold]Backend:[/bold]    {template.backend}",
        f"[bold]Frontend:[/bold]   {template.frontend or '—'}",
        f"[bold]Status:[/bold]     {template.status}",
        f"[bold]Topologies:[/bold] {', '.join(template.topologies)}",
        "",
        f"[bold]Best for:[/bold]   {template.best_for}",
        f"[bold]Description:[/bold] {template.description}",
    ]
    console.print(Panel("\n".join(lines), title=f"[bold cyan]{template.name}[/bold cyan]", border_style="cyan"))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]✗[/bold red] {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[dim]→[/dim] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]![/bold yellow] {message}")
