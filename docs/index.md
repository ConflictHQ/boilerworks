# Boilerworks

**Stop vibe-coding scaffolding. Pick a template. Ship.**

Boilerworks is a catalogue of opinionated, production-ready full-stack templates. One command gets you from zero to a running app with auth, database, background jobs, Docker, and CI — all pre-wired.

---

## Install

```bash
pip install boilerworks
```

## Quick Start

```bash
# See all templates
boilerworks list

# Run the setup wizard
boilerworks setup

# Generate your project
boilerworks init
```

That's it. `boilerworks init` clones the template, renames everything from `boilerworks` to your project name, and hands you a working repo with a clean git history.

---

## The Catalogue

26 templates across 10 stacks. Three sizes.

| Size | When to use |
|------|-------------|
| **Full** | Apps with users — login, permissions, org management |
| **Micro** | API-key services, microservices, workers |
| **Edge** | Cloudflare Workers / Pages, globally distributed |

=== "Full"

    | Template | Stack |
    |----------|-------|
    | `django-nextjs` | Django 5 + Next.js 16 (GraphQL) |
    | `rails-nextjs` | Rails 8 + Next.js 16 (GraphQL) |
    | `rails-hotwire` | Rails 8 + Hotwire + Tailwind |
    | `nestjs-nextjs` | NestJS + Next.js 16 (GraphQL) |
    | `laravel-vue` | Laravel 12 + Vue 3 (Inertia) |
    | `spring-angular` | Spring Boot + Angular 19 |
    | `go-nextjs` | Go + Next.js 16 (GraphQL) |
    | `remix-full` | Remix (full-stack) |
    | `sveltekit-full` | SvelteKit (full-stack) |
    | `phoenix-liveview` | Phoenix + LiveView |

=== "Micro"

    | Template | Stack |
    |----------|-------|
    | `django-micro` | Django 5 REST API |
    | `fastapi-micro` | FastAPI + async |
    | `nestjs-micro` | NestJS REST API |
    | `rails-micro` | Rails 8 API mode |
    | `laravel-micro` | Laravel 12 API |
    | `spring-micro` | Spring Boot REST |
    | `go-micro` | Go REST API |
    | `express-micro` | Express + TypeScript |
    | `phoenix-micro` | Phoenix API |
    | `rust-micro` | Axum REST API |

=== "Edge"

    | Template | Stack |
    |----------|-------|
    | `sveltekit-edge` | SvelteKit on Cloudflare Pages |
    | `remix-edge` | Remix on Cloudflare Pages |
    | `nextjs-edge` | Next.js on Cloudflare Pages |
    | `astro-edge` | Astro on Cloudflare Pages |
    | `hono-edge` | Hono on Cloudflare Workers |
    | `worker-edge` | Cloudflare Worker (bare) |

---

## How It Works

```
boilerworks setup   →  answer 13 questions  →  writes boilerworks.yaml
boilerworks init    →  reads boilerworks.yaml  →  clones + renames + git init
```

The renderer does case-variant string replacement across every text file:

- `boilerworks` → `myproject`
- `Boilerworks` → `Myproject`
- `BOILERWORKS` → `MYPROJECT`

No Jinja2, no magic. Templates are real repos that boot as-is.

---

## Infrastructure (optional)

If you select a cloud provider during setup, `boilerworks init` also clones [boilerworks-opscode](https://github.com/ConflictHQ/boilerworks-opscode) — a Terraform repo with full AWS infrastructure (ECS Fargate, RDS, Redis, ALB, Route53, ACM) and GCP/Azure stubs.

Two topology options:

- **Standard** — app and ops land in sibling directories
- **Omni** — ops lives inside the app repo as `ops/`

---

## License

MIT — Copyright &copy; 2026 CONFLICT LLC
