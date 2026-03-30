# Boilerworks

**Production-ready project templates — assembled in seconds.**

Boilerworks is a CLI that clones and configures any of 26 opinionated, best-of-breed project templates. Stop re-solving auth, permissions, Docker, CI, and admin panels from scratch. Pick a stack, run `boilerworks init`, and get straight to your business logic.

```bash
pip install boilerworks
boilerworks setup    # interactive wizard → writes boilerworks.yaml
boilerworks init     # clone + configure the template
cd my-project
docker compose up -d # full stack running in seconds
```

---

## Installation

```bash
pip install boilerworks
# or with uv:
uv tool install boilerworks
```

Requires Python 3.12+.

---

## Quick Start

### 1. Run the setup wizard

```bash
boilerworks setup
```

Answer 13 questions about your project (name, template, cloud, compliance, etc.) and a `boilerworks.yaml` manifest is written to the current directory.

### 2. Generate the project

```bash
boilerworks init
```

Boilerworks clones the selected template, replaces all `boilerworks` references with your project name, and runs `git init` to give you a clean starting commit.

### 3. Start developing

```bash
cd my-project
docker compose up -d
# Visit http://localhost:3000
```

One command. Full stack. No manual setup.

---

## Template Catalogue

26 templates across three sizes:

| Size | Description | Auth | Deploy Target |
|------|-------------|------|---------------|
| **Full** | Apps with users | Session auth, permissions, org management | VPS, containers, Kubernetes |
| **Micro** | API services | API-key auth | VPS, containers |
| **Edge** | Serverless apps | Flexible | Cloudflare Workers / Pages |

### Full Templates (15)

| Name | Backend | Frontend |
|------|---------|----------|
| [django-nextjs](https://github.com/ConflictHQ/boilerworks-django-nextjs) | Django 5 | Next.js 16 |
| [nestjs-nextjs](https://github.com/ConflictHQ/boilerworks-nestjs-nextjs) | NestJS 11 | Next.js 16 |
| [rails-hotwire](https://github.com/ConflictHQ/boilerworks-rails-hotwire) | Rails 8 | Hotwire + Tailwind |
| [rails-nextjs](https://github.com/ConflictHQ/boilerworks-rails-nextjs) | Rails 8 | Next.js 16 |
| [spring-angular](https://github.com/ConflictHQ/boilerworks-spring-angular) | Spring Boot 3 | Angular 19 |
| [go-nextjs](https://github.com/ConflictHQ/boilerworks-go-nextjs) | Go + Chi | Next.js 16 |
| [phoenix-liveview](https://github.com/ConflictHQ/boilerworks-phoenix-liveview) | Phoenix 1.7 | LiveView |
| [laravel-vue](https://github.com/ConflictHQ/boilerworks-laravel-vue) | Laravel 12 | Inertia + Vue 3 |
| [django-htmx](https://github.com/ConflictHQ/boilerworks-django-htmx) | Django 5 | HTMX + Alpine.js |
| [fastapi-nextjs](https://github.com/ConflictHQ/boilerworks-fastapi-nextjs) | FastAPI | Next.js 16 |
| [spring-nextjs](https://github.com/ConflictHQ/boilerworks-spring-nextjs) | Spring Boot 3 | Next.js 16 |
| [laravel-livewire](https://github.com/ConflictHQ/boilerworks-laravel-livewire) | Laravel 12 | Livewire 3 |
| [go-htmx](https://github.com/ConflictHQ/boilerworks-go-htmx) | Go + Chi | HTMX + Templ |
| [fastapi-htmx](https://github.com/ConflictHQ/boilerworks-fastapi-htmx) | FastAPI | HTMX + Alpine.js |
| [saleor-nextjs](https://github.com/ConflictHQ/boilerworks-saleor-nextjs) | Saleor (Django) | Next.js 16 |

### Micro Templates (6)

| Name | Backend |
|------|---------|
| [django-micro](https://github.com/ConflictHQ/boilerworks-django-micro) | Django 5 (DRF/Ninja) |
| [fastapi-micro](https://github.com/ConflictHQ/boilerworks-fastapi-micro) | FastAPI |
| [nestjs-micro](https://github.com/ConflictHQ/boilerworks-nestjs-micro) | NestJS 11 |
| [go-micro](https://github.com/ConflictHQ/boilerworks-go-micro) | Go + Chi |
| [rust-micro](https://github.com/ConflictHQ/boilerworks-rust-micro) | Axum (Rust) |
| [cherrypy-micro](https://github.com/ConflictHQ/boilerworks-cherrypy-micro) | CherryPy |

### Edge Templates (5)

| Name | Framework |
|------|-----------|
| [sveltekit-full](https://github.com/ConflictHQ/boilerworks-sveltekit-full) | SvelteKit |
| [remix-full](https://github.com/ConflictHQ/boilerworks-remix-full) | Remix |
| [hono-micro](https://github.com/ConflictHQ/boilerworks-hono-micro) | Hono (Cloudflare Workers) |
| [nuxt-full](https://github.com/ConflictHQ/boilerworks-nuxt-full) | Nuxt 4 |
| [astro-site](https://github.com/ConflictHQ/boilerworks-astro-site) | Astro |

---

## Commands

```bash
boilerworks --help              # show all commands
boilerworks list                # show all 26 templates
boilerworks list --size micro   # filter by size
boilerworks list --language python  # filter by language
boilerworks setup               # interactive wizard
boilerworks init                # generate project from boilerworks.yaml
boilerworks init --dry-run      # preview what would happen
boilerworks init --manifest ./path/to/boilerworks.yaml
boilerworks init --output /path/to/output
```

---

## boilerworks.yaml

The manifest file describes your project. Generated by `boilerworks setup`, editable by hand.

```yaml
project: my-app
family: django-nextjs
size: full
topology: standard
cloud: aws
ops: true
region: us-east-1
domain: myapp.com
mobile: false
web_presence: false
compliance:
  - soc2
services:
  email: ses
  cache: redis
data:
  database: postgres
  migrations: true
  seed_data: true
testing:
  e2e: playwright
  unit: true
  integration: true
```

See [`boilerworks.yaml.example`](boilerworks.yaml.example) for a fully annotated version.

---

## What Every Template Includes

Every Boilerworks Full template ships with:

- **Auth** — session-based (httpOnly cookies), bcrypt passwords
- **Permissions** — group-based, per-operation, checked at every endpoint
- **Background jobs** — Redis-backed queue, retries, dead-letter handling
- **Email** — provider-agnostic (SES, SendGrid, Mailgun, Mailpit locally)
- **Admin** — authenticated management interface with CRUD for all models
- **Docker Compose** — one command to boot the full stack
- **CI/CD** — GitHub Actions: lint, test, build, audit
- **AI agent shims** — CLAUDE.md, AGENTS.md, bootstrap.md

---

## Infrastructure

Pair any template with [boilerworks-opscode](https://github.com/ConflictHQ/boilerworks-opscode) for production Terraform:

- **AWS** — ECS Fargate, RDS Postgres 16, ElastiCache Redis, ALB, Route53, ACM, S3, Secrets Manager
- **GCP / Azure** — structured stubs ready for expansion

Select a cloud in `boilerworks setup` and `boilerworks init` will clone and configure the ops repo alongside your app.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development process.

Issues and PRs welcome at [github.com/ConflictHQ/boilerworks](https://github.com/ConflictHQ/boilerworks).

---

## Links

- Documentation: [boilerworks.dev](https://boilerworks.dev)
- Product: [boilerworks.ai](https://boilerworks.ai)
- Templates: [github.com/ConflictHQ](https://github.com/ConflictHQ)

---

Boilerworks is a [Conflict](https://weareconflict.com) brand. CONFLICT is a registered trademark of Conflict LLC.
