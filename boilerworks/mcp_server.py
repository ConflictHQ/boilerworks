"""Boilerworks MCP server — exposes the CLI as tools for AI agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "boilerworks",
    instructions=(
        "Boilerworks provides 26 production-ready project templates structured for AI-assisted development. "
        "Use list_templates to explore options, create_manifest to build a boilerworks.yaml, "
        "and init_project to scaffold the project on disk."
    ),
)


# ── Templates ─────────────────────────────────────────────────────────────────


@mcp.tool()
def list_templates(
    size: Annotated[str | None, "Filter by size: full | micro | edge"] = None,
    language: Annotated[str | None, "Filter by language: python | typescript | ruby | php | java | go | elixir | rust | svelte"] = None,
    status: Annotated[str | None, "Filter by status: done | building | planned"] = None,
) -> str:
    """List all available Boilerworks templates, optionally filtered."""
    from boilerworks.registry import Registry

    registry = Registry()
    templates = registry.list_all()

    if size:
        templates = [t for t in templates if t.size == size]
    if language:
        templates = [t for t in templates if t.language == language]
    if status:
        templates = [t for t in templates if t.status == status]

    rows = [
        {
            "name": t.name,
            "size": t.size,
            "language": t.language,
            "backend": t.backend,
            "frontend": t.frontend,
            "status": t.status,
            "best_for": t.best_for,
        }
        for t in templates
    ]
    return json.dumps(rows, indent=2)


@mcp.tool()
def get_template(
    name: Annotated[str, "Template name, e.g. django-nextjs"],
) -> str:
    """Get full details for a specific Boilerworks template."""
    from boilerworks.registry import Registry

    registry = Registry()
    template = registry.get_by_name(name)

    if template is None:
        valid = ", ".join(sorted(registry.names()))
        return f"Template '{name}' not found. Available: {valid}"

    return json.dumps(template.model_dump(), indent=2)


@mcp.tool()
def search_templates(
    query: Annotated[str, "Search query matched against name, description, and best_for"],
) -> str:
    """Search templates by keyword."""
    from boilerworks.registry import Registry

    registry = Registry()
    results = registry.search(query)

    if not results:
        return f"No templates matched '{query}'."

    rows = [{"name": t.name, "size": t.size, "backend": t.backend, "frontend": t.frontend, "best_for": t.best_for} for t in results]
    return json.dumps(rows, indent=2)


# ── Manifest ──────────────────────────────────────────────────────────────────


@mcp.tool()
def create_manifest(
    project: Annotated[str, "Project slug (lowercase, letters/digits/hyphens)"],
    family: Annotated[str, "Template family name, e.g. django-nextjs"],
    size: Annotated[str, "Template size: full | micro | edge"],
    cloud: Annotated[str | None, "Cloud provider: aws | gcp | azure"] = None,
    region: Annotated[str | None, "Cloud region, e.g. us-east-1"] = None,
    topology: Annotated[str, "standard | api-only | omni"] = "standard",
    domain: Annotated[str | None, "Production domain, e.g. myapp.com"] = None,
    ops: Annotated[bool, "Include Terraform infrastructure repo"] = False,
    mobile: Annotated[bool, "Include mobile app template (Full only)"] = False,
    web_presence: Annotated[bool, "Include marketing site template (Full only)"] = False,
    compliance: Annotated[list[str] | None, "Compliance requirements: soc2 | hipaa | pci-dss | gdpr"] = None,
    email: Annotated[str | None, "Email service: ses | sendgrid | mailgun"] = None,
    storage: Annotated[str | None, "File storage: s3 | gcs | azure-blob"] = None,
    search: Annotated[str | None, "Search engine: opensearch | meilisearch"] = None,
    cache: Annotated[str, "Cache: redis | memcached"] = "redis",
    database: Annotated[str, "Database: postgres | mysql | sqlite"] = "postgres",
    e2e: Annotated[str | None, "E2E framework: playwright | cypress"] = None,
) -> str:
    """Build and validate a boilerworks.yaml manifest. Returns the YAML content ready to write to disk."""
    from boilerworks.manifest import BoilerworksManifest, DataConfig, ServicesConfig, TestingConfig

    try:
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
            compliance=compliance or [],
            services=ServicesConfig(
                email=email,
                storage=storage,
                search=search,
                cache=cache,
            ),
            data=DataConfig(database=database),
            testing=TestingConfig(e2e=e2e),
        )
    except Exception as exc:
        return f"Invalid manifest: {exc}"

    return manifest.to_yaml()


@mcp.tool()
def validate_manifest(
    yaml_content: Annotated[str, "Contents of a boilerworks.yaml file to validate"],
) -> str:
    """Validate a boilerworks.yaml manifest. Returns 'valid' or a description of the errors."""
    from boilerworks.manifest import BoilerworksManifest

    try:
        BoilerworksManifest.from_yaml(yaml_content)
        return "valid"
    except Exception as exc:
        return f"invalid: {exc}"


# ── Project generation ─────────────────────────────────────────────────────────


def _run_cli(args: list[str], manifest_yaml: str) -> str:
    """Write manifest to a temp file, run the boilerworks CLI, return combined output."""
    import subprocess
    import sys
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(manifest_yaml)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "boilerworks.cli"] + args + ["--manifest", tmp_path],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        return output or ("OK" if result.returncode == 0 else "Command failed with no output.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@mcp.tool()
def dry_run(
    manifest_yaml: Annotated[str, "Contents of a boilerworks.yaml manifest"],
    output_dir: Annotated[str, "Directory where the project would be created"] = ".",
) -> str:
    """Preview what boilerworks init would do without writing any files."""
    return _run_cli(["init", "--dry-run", "--output", output_dir], manifest_yaml)


@mcp.tool()
def init_project(
    manifest_yaml: Annotated[str, "Contents of a boilerworks.yaml manifest"],
    output_dir: Annotated[str, "Directory to generate the project in"] = ".",
) -> str:
    """
    Scaffold a new project from a boilerworks.yaml manifest.
    Clones the template, applies substitutions, and runs git init.
    Requires network access (GitHub). This may take 10-30 seconds.
    """
    return _run_cli(["init", "--output", output_dir], manifest_yaml)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
