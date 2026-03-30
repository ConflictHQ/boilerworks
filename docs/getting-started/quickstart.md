# Quick Start

Get a working project in under 5 minutes.

## 1. Install

```bash
pip install boilerworks
```

## 2. Pick a template

```bash
boilerworks list
```

This shows all 26 templates with size, language, and description.

```bash
boilerworks list --size full      # only Full templates
boilerworks list --language python  # only Python templates
```

## 3. Run the wizard

```bash
boilerworks setup
```

The wizard asks 13 questions:

1. **Project name** — slug format (e.g. `my-app`)
2. **Template size** — Full / Micro / Edge
3. **Template family** — filtered list based on size
4. **Topology** — standard (separate repos) or omni (monorepo)
5. **Cloud provider** — aws / gcp / azure / none
6. **Infrastructure** — include boilerworks-opscode? (yes/no, if cloud selected)
7. **Region** — e.g. `us-east-1`
8. **Domain** — e.g. `myapp.com`
9. **Mobile** — include mobile template? (Full only)
10. **Web presence** — include marketing site? (Full only)
11. **Compliance** — SOC2 / HIPAA / PCI-DSS / GDPR
12. **Email provider** — SES / SendGrid / Mailgun
13. **E2E testing** — Playwright / Cypress

Writes `boilerworks.yaml` to the current directory.

## 4. Generate

```bash
boilerworks init
```

This:

1. Clones the template from `ConflictHQ/boilerworks-{family}`
2. Removes `.git/`
3. Replaces all `boilerworks` strings with your project name (case-variant)
4. Renames any files/directories containing `boilerworks`
5. If cloud + ops selected: clones `boilerworks-opscode` and configures it
6. Runs `git init` + initial commit

## 5. Boot it

```bash
cd my-app
docker compose up -d
```

Visit `http://localhost:3000`. Your app is running with your project name everywhere.

## What you get

Every Full template ships with:

- User auth (login, logout, session management)
- Group-based permissions
- Items + Categories CRUD
- Form definitions + submissions
- Workflow definitions + instances
- Admin dashboard
- Background jobs
- PostgreSQL 16 + Redis 7
- Docker Compose (dev) + Dockerfile (prod)
- Health check endpoint
- RSpec / pytest tests
- CI pipeline

!!! tip "Dry run first"
    Not sure what will happen? Run `boilerworks init --dry-run` to see the full plan without touching the filesystem.
