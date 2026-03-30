# Template Catalogue

26 production-ready templates across 10 stacks. All ship with real code — no stubs, no TODOs.

## Full Templates

Apps with user auth, group permissions, and full admin interface.

| Template | Backend | Frontend | Auth | Jobs |
|----------|---------|----------|------|------|
| `django-nextjs` | Django 5 | Next.js 16 (GraphQL/Apollo) | Session | Celery |
| `rails-nextjs` | Rails 8 | Next.js 16 (GraphQL/Apollo) | Session | Solid Queue |
| `rails-hotwire` | Rails 8 | Hotwire + Tailwind | Session | Solid Queue |
| `nestjs-nextjs` | NestJS | Next.js 16 (GraphQL/Apollo) | Session | Bull |
| `laravel-vue` | Laravel 12 | Vue 3 (Inertia) | Session | Horizon |
| `spring-angular` | Spring Boot | Angular 19 | Session | Spring Scheduler |
| `go-nextjs` | Go | Next.js 16 (GraphQL) | Session | — |
| `remix-full` | Remix | — | Session | — |
| `sveltekit-full` | SvelteKit | — | Session | — |
| `phoenix-liveview` | Phoenix | LiveView | Session | Oban |

### What's in every Full template

- **User model** with `has_secure_password` / bcrypt
- **Group-based permissions** — Pundit / CanCan / custom
- **Concerns/mixins**: Auditable, SoftDeletable, ExternalId (UUID), Versionable
- **Business models**: Items, Categories, FormDefinitions, FormSubmissions, WorkflowDefinitions, WorkflowInstances
- **Admin dashboard** with CRUD for all models
- **PostgreSQL 16** (primary) + **Redis 7** (cache + jobs)
- **Mailpit** (dev email catcher)
- **Docker Compose** (dev) + **Dockerfile** (prod, multi-stage)
- **Health check** at `/up` or `/health/`
- Tests with real database — never mocked

---

## Micro Templates

API-key auth only. No user management, no frontend. Lean, fast, deployable.

| Template | Stack | Auth |
|----------|-------|------|
| `django-micro` | Django 5 REST | API key |
| `fastapi-micro` | FastAPI + async | API key |
| `nestjs-micro` | NestJS REST | API key |
| `rails-micro` | Rails 8 API | API key |
| `laravel-micro` | Laravel 12 API | API key |
| `spring-micro` | Spring Boot | API key |
| `go-micro` | Go + Chi | API key |
| `express-micro` | Express + TypeScript | API key |
| `phoenix-micro` | Phoenix API | API key |
| `rust-micro` | Axum | API key |

### What's in every Micro template

- API key auth middleware
- Items CRUD endpoint
- Health check
- PostgreSQL 16 + Redis 7
- Docker Compose + Dockerfile
- OpenAPI / Swagger docs (where framework supports it)

---

## Edge Templates

Cloudflare-native. No servers, no Docker — deploys to the global edge.

| Template | Platform | Runtime |
|----------|----------|---------|
| `sveltekit-edge` | Cloudflare Pages | SvelteKit + adapter-cloudflare |
| `remix-edge` | Cloudflare Pages | Remix + adapter-cloudflare |
| `nextjs-edge` | Cloudflare Pages | Next.js + @cloudflare/next-on-pages |
| `astro-edge` | Cloudflare Pages | Astro + adapter-cloudflare |
| `hono-edge` | Cloudflare Workers | Hono |
| `worker-edge` | Cloudflare Workers | bare Worker API |

### What's in every Edge template

- Cloudflare Workers / Pages deploy config (`wrangler.toml`)
- D1 (SQLite) or KV bindings
- Local dev with `wrangler dev`
- GitHub Actions deploy workflow

---

## Ports

All templates use standardised ports to avoid collisions when running multiple projects:

| Service | Port |
|---------|------|
| App | 3000 (frontend) / 8000 (backend API) |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Mailpit (SMTP) | 1025 |
| Mailpit (UI) | 8025 |
| MinIO (S3) | 9001 |
