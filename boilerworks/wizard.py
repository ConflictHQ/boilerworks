"""Interactive setup wizard — collects answers, writes boilerworks.yaml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import questionary
from rich.panel import Panel

from boilerworks.console import console, print_success
from boilerworks.manifest import BoilerworksManifest, DataConfig, ServicesConfig, TestingConfig
from boilerworks.registry import Registry, TemplateInfo

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")

_SELECTION_GUIDE = """[bold]How to pick a template size:[/bold]

  [cyan]Full[/cyan]   — Apps with users (login, permissions, org management)
  [magenta]Micro[/magenta]  — API-key services, microservices, workers
  [blue]Edge[/blue]   — Cloudflare Workers / Pages, globally distributed

[bold]When to choose Full vs Micro:[/bold]
  If it has users logging in       → Full
  If it's a service with API keys  → Micro
  If it needs global edge scale    → Edge
"""


def _validate_slug(text: str) -> bool | str:
    if not text:
        return "Project name is required"
    if not _SLUG_RE.match(text):
        return "Must be lowercase, start with a letter, letters/digits/hyphens only (e.g. my-project)"
    return True


def _template_choices(templates: list[TemplateInfo]) -> list[questionary.Choice]:
    choices = []
    current_lang = None
    for t in templates:
        if t.language != current_lang:
            current_lang = t.language
            choices.append(questionary.Separator(f"── {t.language} ──"))
        status_icon = {"done": "●", "building": "◐", "planned": "○"}.get(t.status, "?")
        label = f"{status_icon} {t.name:<24} {t.description}"
        choices.append(questionary.Choice(title=label, value=t.name))
    return choices


def run_wizard(output_path: str | Path = "boilerworks.yaml") -> None:
    """Walk through the 13-step wizard and write boilerworks.yaml."""
    registry = Registry()
    console.print(
        Panel(
            "[bold cyan]Boilerworks Setup Wizard[/bold cyan]\nAnswers are saved to [bold]boilerworks.yaml[/bold]",
            border_style="cyan",
        )
    )

    # ── Step 1: Project name ─────────────────────────────────────────────────
    project = questionary.text(
        "Project name (slug format, e.g. my-app):",
        validate=_validate_slug,
    ).ask()
    if project is None:
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    # ── Step 2: Template size ─────────────────────────────────────────────────
    console.print(Panel(_SELECTION_GUIDE, title="Template Guide", border_style="dim"))
    size = questionary.select(
        "Template size:",
        choices=["full", "micro", "edge"],
    ).ask()
    if size is None:
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    # ── Step 3: Template family ───────────────────────────────────────────────
    filtered = registry.filter_by_size(size)
    family = questionary.select(
        "Template family:",
        choices=_template_choices(filtered),
    ).ask()
    if family is None:
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    template = registry.get_by_name(family)

    # ── Step 4: Topology ──────────────────────────────────────────────────────
    available_topologies = template.topologies if template else ["standard"]
    if len(available_topologies) > 1:
        topology = questionary.select(
            "Deployment topology:",
            choices=available_topologies,
        ).ask()
    else:
        topology = available_topologies[0]
        console.print(f"  [dim]Topology: {topology} (only option for this template)[/dim]")
    if topology is None:
        topology = "standard"

    # ── Step 5: Cloud provider ────────────────────────────────────────────────
    cloud_answer = questionary.select(
        "Cloud provider:",
        choices=["aws", "gcp", "azure", "none"],
    ).ask()
    cloud = cloud_answer if cloud_answer != "none" else None

    # ── Step 5b: Ops (infra-as-code) ─────────────────────────────────────────
    ops = False
    if cloud:
        ops = (
            questionary.confirm(
                "Include infrastructure-as-code (boilerworks-opscode)?",
                default=True,
            ).ask()
            or False
        )

    # ── Step 6: Region ────────────────────────────────────────────────────────
    region: str | None = None
    if cloud:
        region = questionary.text(
            f"Region (e.g. {'us-east-1' if cloud == 'aws' else 'us-central1' if cloud == 'gcp' else 'eastus'}):",
        ).ask()
        if not region:
            region = None

    # ── Step 7: Domain ────────────────────────────────────────────────────────
    domain_answer = questionary.text("Domain (optional, e.g. myapp.com):").ask()
    domain = domain_answer.strip() if domain_answer and domain_answer.strip() else None

    # ── Step 8 & 9: Mobile / Web presence (Full only) ────────────────────────
    mobile = False
    web_presence = False
    if size == "full":
        mobile = questionary.confirm("Include mobile app template?", default=False).ask() or False
        web_presence = questionary.confirm("Include web presence / marketing site?", default=False).ask() or False

    # ── Step 10: Compliance ───────────────────────────────────────────────────
    compliance_answer = questionary.checkbox(
        "Compliance requirements:",
        choices=["soc2", "hipaa", "pci-dss", "gdpr", "none"],
    ).ask()
    compliance = [c for c in (compliance_answer or []) if c != "none"]

    # ── Step 11: Email provider ───────────────────────────────────────────────
    email_answer = questionary.select(
        "Email provider:",
        choices=["ses", "sendgrid", "mailgun", "none"],
    ).ask()
    email = email_answer if email_answer != "none" else None

    # ── Step 12: E2E testing ──────────────────────────────────────────────────
    e2e_answer = questionary.select(
        "End-to-end testing framework:",
        choices=["playwright", "cypress", "none"],
    ).ask()
    e2e = e2e_answer if e2e_answer != "none" else None

    # ── Step 13: Summary + confirm ────────────────────────────────────────────
    summary_lines = [
        f"  [bold]Project:[/bold]    {project}",
        f"  [bold]Template:[/bold]   {family} ({size})",
        f"  [bold]Topology:[/bold]   {topology}",
        f"  [bold]Cloud:[/bold]      {cloud or 'none'}",
        f"  [bold]Ops:[/bold]        {'yes' if ops else 'no'}",
        f"  [bold]Region:[/bold]     {region or '—'}",
        f"  [bold]Domain:[/bold]     {domain or '—'}",
    ]
    if size == "full":
        summary_lines += [
            f"  [bold]Mobile:[/bold]     {'yes' if mobile else 'no'}",
            f"  [bold]Web:[/bold]        {'yes' if web_presence else 'no'}",
        ]
    summary_lines += [
        f"  [bold]Compliance:[/bold] {', '.join(compliance) if compliance else 'none'}",
        f"  [bold]Email:[/bold]      {email or 'none'}",
        f"  [bold]E2E:[/bold]        {e2e or 'none'}",
    ]
    console.print(Panel("\n".join(summary_lines), title="[bold]Summary[/bold]", border_style="green"))

    confirmed = questionary.confirm("Write boilerworks.yaml?", default=True).ask()
    if not confirmed:
        console.print("[yellow]Cancelled — nothing written.[/yellow]")
        sys.exit(0)

    manifest = BoilerworksManifest(
        project=project,
        family=family,
        size=size,
        topology=topology,
        cloud=cloud,
        ops=ops,
        region=region,
        domain=domain,
        mobile=mobile,
        web_presence=web_presence,
        compliance=compliance,
        services=ServicesConfig(email=email),
        data=DataConfig(),
        testing=TestingConfig(e2e=e2e),
    )

    out = Path(output_path)
    manifest.to_file(out)
    print_success(f"Written to [bold]{out}[/bold]")
    console.print("\n[dim]Next:[/dim]  [bold]boilerworks init[/bold]")
