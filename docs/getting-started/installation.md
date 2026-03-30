# Installation

## Requirements

- Python 3.12+
- Git
- SSH key or `gh auth login` for GitHub access (templates are cloned from ConflictHQ)

## Install

=== "pip"

    ```bash
    pip install boilerworks
    ```

=== "pipx (recommended)"

    ```bash
    pipx install boilerworks
    ```

=== "uv"

    ```bash
    uv tool install boilerworks
    ```

## Verify

```bash
boilerworks --help
```

```
Usage: boilerworks [OPTIONS] COMMAND [ARGS]...

  Boilerworks CLI — project scaffolding from the boilerworks.ai catalogue.

Commands:
  setup      Run the interactive setup wizard → writes boilerworks.yaml
  init       Generate a project from boilerworks.yaml
  list       List all available templates
  bootstrap  Run Terraform infrastructure layers (requires cloud setup)
```

## GitHub Access

Templates are cloned from `github.com/ConflictHQ`. The CLI tries SSH first, then HTTPS.

**SSH (recommended):**
```bash
# Add your key to GitHub if you haven't already
ssh-add ~/.ssh/id_ed25519
ssh -T git@github.com  # should say "Hi <username>"
```

**HTTPS via gh CLI:**
```bash
gh auth login
```
