"""Bootstrap command — infrastructure layer orchestration (v2 stub)."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

from boilerworks.console import console, print_info, print_warning

_LAYERS = [
    ("1", "Foundation", "VPC, subnets, security groups, IAM roles"),
    ("2", "Data", "RDS (Postgres), ElastiCache (Redis), S3 buckets"),
    ("3", "Compute", "ECS/GKE cluster, service definitions, autoscaling"),
    ("4", "Delivery", "Load balancer, TLS certificates, CDN, DNS"),
    ("5", "Observability", "Metrics, logs, alerts, dashboards"),
]

_V2_NOTICE = (
    "Infrastructure bootstrapping is coming in v2.\n"
    "For now, follow the ops template README to provision infrastructure manually.\n\n"
    "Ops template: [bold]https://github.com/ConflictHQ/boilerworks-opscode[/bold]"
)


def run_bootstrap(ops_dir: str | None = None, dry_run: bool = True) -> None:
    """Show the infrastructure bootstrap execution plan."""
    if ops_dir:
        ops_path = Path(ops_dir)
        if not ops_path.exists():
            print_warning(f"Ops directory not found: {ops_path}")
    else:
        print_info("No --ops-dir specified; showing generic plan")

    # Build the plan panel
    plan_lines = ["[bold]Execution plan — 5 layers[/bold]\n"]
    for layer_num, layer_name, layer_desc in _LAYERS:
        plan_lines.append(f"  [cyan]{layer_num}.[/cyan] [bold]{layer_name}[/bold]")
        plan_lines.append(f"     {layer_desc}")
        plan_lines.append("")

    console.print(Panel("\n".join(plan_lines).rstrip(), title="[bold]Bootstrap Plan[/bold]", border_style="cyan"))
    console.print(Panel(_V2_NOTICE, title="[bold yellow]v1 — Stub[/bold yellow]", border_style="yellow"))
