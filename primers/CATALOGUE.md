# Boilerworks -- Catalogue & Architecture Primer

Boilerworks is a catalogue of opinionated, best-of-breed templates that get you from zero to working application fast. Stop spending time scaffolding auth, permissions, Docker, CI, admin panels, and background jobs from scratch every time -- that work should be done once, correctly, and reused. Each template is a proven combination pre-solved for the hard infrastructure problems that every serious application needs. Pick a stack, run the bootstrap, and get straight to business logic.

This document covers what Boilerworks is and why it makes the decisions it does. Stack-specific code examples, architecture diagrams, and build recipes live in the per-stack primers.

---

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [Architecture Decisions](#architecture-decisions)
3. [The Template Catalogue](#the-template-catalogue)
4. [The Bootstrap System](#the-bootstrap-system)
5. [The Agent Shim Pattern](#the-agent-shim-pattern)
6. [The Memory System](#the-memory-system)
7. [Development Process](#development-process) (see also: [PROCESS.md](PROCESS.md) — the full non-negotiable mandate)
8. [Universal Patterns](#universal-patterns)
9. [Anti-Patterns](#anti-patterns)
10. [Extending Boilerworks](#extending-boilerworks)

---

## Core Philosophy

**Build infrastructure, not features.** Boilerworks is a starting point, not a product. Every component answers "how do we do X in this stack?" with a working, tested example. Domain-specific features (CRM pipeline, invoice generator) don't belong in the boilerplate.

**Convention over configuration.** Every pattern has one way to do it. An engineer -- or an AI agent -- should be able to look at one example and replicate it for their domain without asking.

**Ship the hard parts pre-solved.** Auth, permissions, file uploads, form engines, workflow engines, background jobs, real-time updates -- these are the same across every enterprise app. Solve them once, correctly.

**Agent-native.** The codebase is designed to be worked on by AI coding agents as a first-class concern. Conventions are documented, patterns are consistent, and every project ships with agent shims (BOOTSTRAP.md + agent configuration files).

**v0 = scaffolding, zero business logic.** A freshly created Boilerworks project contains working infrastructure and example data to demonstrate patterns. It contains no business logic. The project team adds domain logic on top.

**Everything has Docker.** Every template ships with a single `docker compose up` that boots the entire stack. No "install 7 things first" instructions.

**Open-source quality bar.** Every template is written as if it will be open-sourced. Clean code, proper documentation, no secrets, no shortcuts.

**Compounding.** Every engagement improves the templates. Patterns validated in production feed back into the catalogue. The templates get better over time, not stale.

---

## Architecture Decisions

### Why backend + frontend separation (not monolith rendering)?

Backend and frontend are separate services with a typed contract between them. This is true even for server-rendered stacks (HTMX, Hotwire, LiveView), where the separation is logical rather than physical.

- Independent deploys -- backend ships without waiting for frontend and vice versa
- Teams can specialize -- backend engineers and frontend engineers work in their strongest language
- API-first -- the same backend serves web, mobile, and third-party integrations
- Testable in isolation -- backend tests don't need a browser, frontend tests don't need a real database

### Why a typed API contract?

Every stack has a typed contract between backend and frontend. For SPA frontends, this is GraphQL. For server-rendered stacks, the contract is the template context or LiveView assigns.

- Introspectable -- auto-generated documentation and client types
- Versionable -- schema changes are explicit and reviewable
- No over-fetching -- clients request exactly what they need (GraphQL) or the server renders exactly what's needed (server-rendered)
- Self-documenting -- the schema is the documentation

### Why session auth over JWT?

All Boilerworks templates use session-based authentication with httpOnly cookies.

- httpOnly cookies are immune to XSS token theft -- JavaScript cannot access the session token
- Server-side session storage enables instant revocation -- no waiting for JWT expiry
- Session tokens are hashed (SHA256) before database storage -- a database breach does not compromise active sessions
- Mature, battle-tested pattern with well-understood security properties
- JWT is used only as a transport mechanism in specific inter-service scenarios, never as the primary auth mechanism

### Why background job queues?

Every template ships with an async job queue for fire-and-forget work.

- Email delivery should not block the HTTP response
- Webhook dispatch needs retries, backoff, and timeout handling
- File processing (thumbnails, conversions, imports) is inherently slow
- Workflow action execution may involve external services
- Search reindexing should happen asynchronously after data changes
- Any operation that takes more than a few hundred milliseconds belongs in a queue

### Why Postgres?

Every template uses Postgres as the primary database. No exceptions.

- Proven at every scale from prototype to planet-scale
- Extensible -- JSON/JSONB for semi-structured data, full-text search, PostGIS for geospatial
- Strong consistency guarantees and ACID transactions
- Excellent tooling, monitoring, and operational knowledge across every ecosystem
- Every major framework has first-class Postgres support

### Why Docker everything?

Every template ships with Docker Compose that boots the full stack in one command.

- No "install Postgres, then Redis, then MinIO, then..." instructions
- Reproducible environments -- same versions, same configuration, every machine
- New team members (human or AI) are productive in minutes, not hours
- Infrastructure dependencies (search, email, storage) are always available locally
- Parity between local development and production deployment

---

## The Template Catalogue

### Template Sizes

Not every project needs a full-stack app with user auth and org management. Templates come in three sizes:

| Size | Auth model | Infrastructure | Deploy target | When to use |
|------|-----------|----------------|---------------|-------------|
| **Full** | User auth, permissions, org management | Docker Compose (Postgres, Redis, MinIO, Mailpit, workers) | VPS, containers, Kubernetes | Apps with users — SaaS, enterprise, internal tools, anything that needs login |
| **Micro** | API-key auth (service-to-service), no user auth | Docker Compose (lighter) | VPS, containers | Microservices, workers, lightweight APIs, small tools with or without a UI |
| **Edge** | Flexible (platform auth, API-key, or custom) | Cloudflare stack (D1, R2, KV, Queues) — no Docker in production | Cloudflare Workers / Pages | Low-latency, globally distributed, serverless — APIs, sites, real-time apps |

**How to pick:**
- If it has users logging in → **Full**
- If it's a service with API-key auth (with or without a UI) → **Micro**
- If it needs to run at the edge, globally, with serverless scale → **Edge**

Everything is feature-flagged, so agents can always disable features they don't need from a Full template or extend a Micro/Edge template as requirements evolve.

### Edge Infrastructure

Edge templates use a fundamentally different infrastructure stack — no self-hosted servers, no Docker in production.

| Layer | Edge (Cloudflare) | Replaces (Full/Micro) |
|-------|-------------------|----------------------|
| Runtime | Cloudflare Workers | Node / Python / Ruby / Go server |
| Database | D1 (SQLite at edge), Turso (distributed SQLite), or Neon (Postgres via HTTP) | Self-hosted Postgres |
| Storage | Cloudflare R2 (S3-compatible) | MinIO / S3 |
| Key-Value | Cloudflare KV | Redis |
| Queues | Cloudflare Queues | Celery / BullMQ / Sidekiq |
| Cron | Cron Triggers | celery-beat / cron |
| Auth | Cloudflare Access, custom, or API-key | Session middleware |
| CDN/SSR | Cloudflare Pages | Next.js / Vite dev server |

Edge templates still include Docker Compose for **local development** — they just don't use Docker in production.

---

### Full Templates

| Stack | Backend | Frontend | Status | Best For |
|-------|---------|----------|--------|----------|
| django-nextjs | Django 5 | Next.js 16 | Done | Data-heavy backends, admin-rich, rapid prototyping |
| nestjs-nextjs | NestJS 11 | Next.js 16 | Done | Full TypeScript, enterprise-ish |
| django-htmx | Django 5 | HTMX + Alpine.js | Tier 2 | Server-rendered CRUD, content-heavy, less JS |
| saleor-nextjs | Saleor (Django) | Next.js 16 | Tier 2 | E-commerce |
| rails-hotwire | Rails 8 | Hotwire (Turbo + Stimulus) | Tier 2 | Marketplace, social, content, CMS |
| laravel-vue | Laravel 11 | Inertia + Vue 3 | Tier 2 | Laravel ecosystem, SPA-like |
| fastapi-nextjs | FastAPI | Next.js 16 | Tier 2 | Modern Python API, async-first |
| fastapi-htmx | FastAPI | HTMX + Alpine.js | Tier 3 | Lightweight Python, server-rendered |
| spring-angular | Spring Boot 3 | Angular 19 | Tier 3 | Enterprise, banking, fintech |
| go-htmx | Go + Chi/Echo | HTMX + Templ | Tier 3 | Lightweight, performance-critical |
| rails-nextjs | Rails 8 | Next.js 16 | Tier 3 | Rails backend, richer frontend than Hotwire |
| phoenix-liveview | Phoenix 1.7 | LiveView | Tier 3 | Real-time, collaborative |
| spring-nextjs | Spring Boot 3 | Next.js 16 | Tier 3 | Modern enterprise, non-Angular |
| go-nextjs | Go + Chi/Echo | Next.js 16 | Tier 4 | API-first Go, rich frontend |
| laravel-livewire | Laravel 11 | Livewire 3 | Tier 4 | Server-rendered reactive PHP |

### Micro Templates

| Stack | Backend | Size | Status | Best For |
|-------|---------|------|--------|----------|
| django-micro | Django 5 (DRF or Ninja) | Micro | Tier 3 | API-only Python service |
| fastapi-micro | FastAPI | Micro | Tier 2 | Lightweight async Python API |
| nestjs-micro | NestJS 11 | Micro | Tier 3 | API-only TypeScript service |
| go-micro | Go + Chi/Echo | Micro | Tier 3 | Lightweight Go service |
| cherrypy-micro | CherryPy | Micro | Tier 3 | Pure Python microservice, no WSGI overhead, fun |
| rust-micro | Axum (Rust) | Micro | Tier 3 | High-performance Rust microservice |

### Edge Templates

| Stack | Framework | Frontend | Status | Best For |
|-------|-----------|----------|--------|----------|
| hono-micro | Hono | None (API-only) | Tier 3 | Edge API, Cloudflare Workers |
| sveltekit-full | SvelteKit | Svelte (built-in) | Tier 3 | Full-stack edge app, simplest DX |
| nuxt-full | Nuxt 4 | Vue (built-in) | Tier 4 | Full-stack edge app, Vue ecosystem |
| remix-full | Remix | React (built-in) | Tier 4 | Server-first React at the edge |
| astro-site | Astro | Islands (multi-framework) | Tier 3 | Content sites, blogs, docs, marketing |

**Status definitions:**
- **Done** -- Reference implementation, production-tested, fully documented
- **Tier 2** -- Next priority, high demand, architecture defined
- **Tier 3** -- Planned, architecture sketched, not yet built
- **Tier 4** -- On the roadmap, will be built when demand justifies

---

### Stack Selection Guide

When you know the domain and requirements, this is how to pick the right template.

#### By Domain

| Domain | Recommended Stack(s) |
|--------|---------------------|
| Banking / fintech / enterprise compliance | spring-angular |
| E-commerce | saleor-nextjs |
| Content / CMS / blog platform | rails-hotwire or django-htmx |
| Dashboard / analytics / SPA | django-nextjs or nestjs-nextjs |
| Marketplace / social | rails-hotwire |
| Simple CRUD / recipe app | django-htmx or laravel-livewire |
| Real-time / collaborative | phoenix-liveview |
| Performance-critical / lightweight | go-htmx |
| Async-first Python API | fastapi-nextjs or fastapi-micro |
| Full TypeScript team | nestjs-nextjs |
| Microservice / worker | fastapi-micro, go-micro, nestjs-micro, or django-micro |
| Edge API / serverless | hono-micro |
| Content site / blog / docs | astro-site |
| Full-stack edge app (Svelte) | sveltekit-full |
| Full-stack edge app (Vue) | nuxt-full |
| Full-stack edge app (React) | remix-full |

#### By Team Profile

| Team's Primary Language | Recommended Stack(s) |
|------------------------|---------------------|
| Python | django-nextjs, django-htmx, fastapi-nextjs, or fastapi-micro |
| Ruby | rails-hotwire or rails-nextjs |
| PHP | laravel-vue or laravel-livewire |
| Java / JVM | spring-angular or spring-nextjs |
| TypeScript | nestjs-nextjs or nestjs-micro |
| Go | go-htmx, go-nextjs, or go-micro |
| Elixir | phoenix-liveview |
| Rust | rust-micro |
| Svelte | sveltekit-full |
| Edge / serverless | hono-micro, sveltekit-full, nuxt-full, remix-full, astro-site |

#### Two-Template Decisions

When a backend has two frontend options, this table resolves the choice.

| Backend | Variant A | Variant B | Choose A when... | Choose B when... |
|---------|-----------|-----------|------------------|------------------|
| Django | django-nextjs | django-htmx | Rich interactivity, dashboards, SPAs, complex forms | Content-heavy CRUD, admin-centric, less JS, faster to ship |
| Rails | rails-hotwire | rails-nextjs | Rails-native DX, marketplace, social, content | Frontend needs exceed what Hotwire handles gracefully |
| Spring | spring-angular | spring-nextjs | Enterprise Angular culture, banking, corporate | Modern enterprise, startup culture, non-Angular teams |
| Laravel | laravel-vue | laravel-livewire | SPA-like experience, complex client state | Server-rendered simplicity, rapid prototyping, less JS |
| Go | go-htmx | go-nextjs | Lightweight, server-rendered, performance-first | API-first with rich client-side frontend |

**Python has two frameworks** (Django vs FastAPI): Django is batteries-included -- ORM, admin, migrations, permissions all built in. FastAPI is lean and async-first -- bring your own ORM, no admin, no opinions beyond the API layer. Choose Django when you want the full infrastructure; choose FastAPI when you want a lightweight, high-performance API.

NestJS has only one answer (nestjs-nextjs) -- the whole point is full TypeScript.

Phoenix has only one answer (phoenix-liveview) -- LiveView is the reason to choose Elixir.

---

### Per-Stack Primer Index

Each stack has a detailed primer with code examples, architecture diagrams, and build recipes. All stack-specific implementation details live in these primers, not in this document.

| Stack | Primer | Notes |
|-------|--------|-------|
| django-nextjs | [PRIMER.md](django-nextjs/PRIMER.md) | Reference implementation |
| nestjs-nextjs | [PRIMER.md](nestjs-nextjs/PRIMER.md) | Second reference implementation |
| django-htmx | [PRIMER.md](django-htmx/PRIMER.md) | Shares Django backend patterns |
| saleor-nextjs | [PRIMER.md](saleor-nextjs/PRIMER.md) | E-commerce focus |
| rails-hotwire | [PRIMER.md](rails-hotwire/PRIMER.md) | |
| rails-nextjs | [PRIMER.md](rails-nextjs/PRIMER.md) | Shares Rails backend patterns |
| spring-angular | [PRIMER.md](spring-angular/PRIMER.md) | |
| spring-nextjs | [PRIMER.md](spring-nextjs/PRIMER.md) | Shares Spring backend patterns |
| laravel-vue | [PRIMER.md](laravel-vue/PRIMER.md) | |
| laravel-livewire | [PRIMER.md](laravel-livewire/PRIMER.md) | Shares Laravel backend patterns |
| go-htmx | [PRIMER.md](go-htmx/PRIMER.md) | |
| go-nextjs | [PRIMER.md](go-nextjs/PRIMER.md) | Shares Go backend patterns |
| phoenix-liveview | [PRIMER.md](phoenix-liveview/PRIMER.md) | |
| fastapi-nextjs | [PRIMER.md](fastapi-nextjs/PRIMER.md) | |
| fastapi-htmx | [PRIMER.md](fastapi-htmx/PRIMER.md) | Shares FastAPI backend patterns |
| fastapi-micro | [PRIMER.md](fastapi-micro/PRIMER.md) | Micro template |
| django-micro | [PRIMER.md](django-micro/PRIMER.md) | Micro template |
| nestjs-micro | [PRIMER.md](nestjs-micro/PRIMER.md) | Micro template |
| go-micro | [PRIMER.md](go-micro/PRIMER.md) | Micro template |
| cherrypy-micro | [PRIMER.md](cherrypy-micro/PRIMER.md) | Micro template |
| rust-micro | [PRIMER.md](rust-micro/PRIMER.md) | Micro template |
| hono-micro | [PRIMER.md](hono-micro/PRIMER.md) | Edge micro template |
| sveltekit-full | [PRIMER.md](sveltekit-full/PRIMER.md) | Edge full-stack template |
| nuxt-full | [PRIMER.md](nuxt-full/PRIMER.md) | Edge full-stack template |
| remix-full | [PRIMER.md](remix-full/PRIMER.md) | Edge full-stack template |
| astro-site | [PRIMER.md](astro-site/PRIMER.md) | Edge content site template |

Stacks using Next.js as the frontend also reference the shared [NEXTJS_FRONTEND.md](NEXTJS_FRONTEND.md) primer, which covers the common Next.js patterns, components, and conventions that apply across all Next.js-based templates.

---

## The Bootstrap System

Every Boilerworks project has a single source of truth for conventions: `bootstrap.md`.

This file is the primary conventions document. An agent given this document and a business requirement should be able to generate correct, idiomatic code without exploring the codebase.

`bootstrap.md` covers:

- What's already built (every layer with tech choices)
- App structure (every module/app with its purpose)
- Model conventions (base classes, soft deletes, audit trails)
- API conventions (types, queries, mutations, context)
- Permission system (definition, checking, assignment)
- Admin conventions
- Background job patterns
- Test patterns
- Code style (formatting, linting, enforcement)
- Adding a new module (step-by-step)
- All local URLs and common commands

**The bootstrap file is the canonical reference.** Agent shims, primers, and all other documentation defer to it. When there is a conflict between any document and `bootstrap.md`, the bootstrap file wins.

Each stack's `bootstrap.md` is written in the idiom of that stack. A Django project's bootstrap reads like a Django guide. A Rails project's bootstrap reads like a Rails guide. The structure is the same; the content is stack-native.

---

## The Agent Shim Pattern

Each Boilerworks project ships with shim files for multiple AI coding agents. All shims point to `bootstrap.md` as the conventions source.

```
CLAUDE.md       # Claude Code / Claude agent
AGENTS.md       # Cursor, Windsurf, generic agents
bootstrap.md    # The actual conventions (all shims point here)
```

### What goes in a shim

A shim file is short. It contains:

1. **Pointer to bootstrap.md** -- "Read `bootstrap.md` before writing any code"
2. **Agent-specific instructions** -- tool preferences, behavior rules, output format
3. **Stack summary** -- framework, API layer, schema location, context pattern
4. **Testing notes** -- test runner, assertion style, what to avoid
5. **Pointer to memory** -- if the agent supports persistent memory

### Why shims matter

An AI agent's first action when opening a project is reading its configuration file. If that file says "here's a conventions document, read it first", the agent follows it. Without shims, agents guess -- and they guess differently every time.

The shim pattern ensures:

- **Consistency** -- every agent follows the same conventions
- **No codebase exploration needed** -- the agent can write correct code from the shim alone
- **Stack-specific guidance** -- each agent gets instructions in its own format
- **Multi-agent safety** -- when multiple agents work on the same project, they all follow the same rules

---

## The Memory System

Claude Code has a persistent, file-based memory system. Boilerworks uses it to maintain context across conversations.

### Memory types

| Type | What it stores | Example |
|------|---------------|---------|
| `user` | Role, preferences, knowledge level | "Deep Go expertise, new to React frontend" |
| `feedback` | Corrections and confirmed approaches | "No co-authorship in commits, ever" |
| `project` | Ongoing work, goals, deadlines | "Auth middleware rewrite driven by compliance" |
| `reference` | Pointers to external systems | "Bugs tracked in Linear project INGEST" |

### Memory structure

```
~/.claude/projects/<project-path>/memory/
  MEMORY.md                    # Index file (always loaded, links to memory files)
  feedback_no_coauthorship.md  # Individual memory files
  feedback_workflow.md
  project_docker_stack.md
  ...
```

Each memory file has frontmatter with name, description, and type. The index file links to all memory files and is always loaded at conversation start.

### What NOT to save in memory

- Code patterns or architecture (derivable from reading the code)
- Git history (use `git log`)
- Fix recipes (the fix is in the code, context is in the commit)
- Anything already in CLAUDE.md or bootstrap.md
- Ephemeral task state

### Memory in the development process

Memory accumulates organically through conversations:

- User says "don't mock the database" -- save as feedback memory
- User confirms a non-obvious approach worked -- save the validated pattern
- New project context emerges -- save as project memory
- Memory becomes stale -- verify against current code, update or remove

---

## Development Process

Every task follows a strict workflow. This is enforced by memory, not just documentation.

### The Issue Workflow

```
1.  Pick a task from the issue board
2.  Comment on the issue with plan/approach BEFORE starting
3.  Create branch from main
4.  Do the work
5.  Write meaningful tests
6.  Run lint + tests, fix issues
7.  Comment on issue with learnings DURING work
8.  Create PR with clear description
9.  Code review the diff
10. Merge (no rebases -- new commits only)
11. Comment on issue with summary AFTER completion
12. Move to next task
```

### Rules

- **No rebases.** Ever. New commits only.
- **No co-authorship messages.** No AI attribution in commits, ever.
- **No local docs.** Plans and specs go on GitHub issues/PRs, not local markdown files.
- **Push back freely.** If something doesn't make sense, say so directly. Don't agree for the sake of agreeing.
- **Submodule push order.** Always push submodules before parent repo.
- **Issue hygiene.** Move to in-progress when starting, update as you go, close the loop when done.
- **One PR per issue.** Don't batch unrelated changes unless trivially related.

### Agent Collaboration

When working with AI agents on Boilerworks:

**Parallel workstreams:** Kick off independent work in parallel when possible. Backend mutations and frontend wiring touch different files and can proceed simultaneously.

**Task tracking:** Use structured task tracking for multi-step work. Each step gets a status (pending, in progress, completed) and the overall progress is visible.

**Browser testing:** Use browser automation to test the running local dev server -- fill forms, click buttons, verify rendering, check console errors.

---

## Universal Patterns

These patterns apply to every Boilerworks template regardless of stack. Per-stack primers provide the implementation details and code examples.

---

### Models & Base Classes

All business models must support:

**Audit trails.** Every record tracks `created_at`/`created_by` and `updated_at`/`updated_by`. These fields are auto-populated by the framework -- developers never set them manually.

**Soft deletes.** Business objects are never hard-deleted. Instead, `deleted_at` and `deleted_by` are set, and queries filter out soft-deleted records by default. Hard deletes are reserved for infrastructure cleanup (expired sessions, temporary files).

**External identifiers.** Integer primary keys are never exposed in APIs. Every record that appears in an API response uses a UUID, cuid, or equivalent opaque identifier. Internal integer PKs exist for database performance but stay internal.

**Versioning.** Business models include an auto-incrementing version field for optimistic concurrency control. When a mutation updates a record, it checks that the version matches what the client last read. This prevents silent overwrites when two users edit the same record.

---

### API Layer

Every stack has a typed contract between backend and frontend.

**For SPA frontends (Next.js, Angular, Vue):** GraphQL provides the contract. The schema is introspectable, queries are typed, and clients request exactly the fields they need.

**For server-rendered frontends (HTMX, Hotwire, LiveView, Livewire):** The contract is the template context or socket assigns. The server renders exactly what's needed -- no client-side query language.

**Consistent result shape.** Mutations and actions return a consistent shape: success/failure flag plus structured errors. This allows the frontend to handle all mutations with a single pattern.

**Auth at the boundary.** Every resolver, endpoint, controller action, or LiveView mount checks authentication before doing anything else. No exceptions. The auth check is the first line of every handler.

**Context object.** The request context carries: authenticated user, session, permissions, and any shared resources (dataloaders, database connections, service instances). Resolvers and handlers receive this context automatically.

---

### Auth

Session-based authentication across all stacks.

**httpOnly cookies.** The session token lives in an httpOnly cookie. JavaScript cannot access it. This makes the token immune to XSS attacks -- even if an attacker injects script into the page, they cannot steal the session.

**Server-side session storage.** Sessions are stored server-side (database or Redis). This enables instant revocation -- log out means the session is destroyed immediately. No waiting for a token to expire.

**Session token hashing.** The raw session token goes to the client cookie. Before storing in the database, the token is hashed with SHA256. A database breach exposes only hashes, not usable tokens.

**Session expiry.** 30 days by default. Configurable per stack.

**CORS.** Restricted to an explicit origin whitelist loaded from environment variables. No wildcards in production.

---

### Permissions

Group-based. Never user-based. No exceptions.

**Permissions are defined as slugs** (e.g., "products.view", "products.edit", "orders.create"). Each permission represents a single capability.

**Permissions are assigned to groups.** Groups are assigned to users. A user's effective permissions are the union of all permissions from all their groups.

**Checked before business logic.** Every resolver, endpoint, and action checks permissions before executing any business logic. The check happens after authentication and before any database queries.

**Frontend permission guards.** The frontend receives the current user's permissions and provides guard components or helpers that show/hide UI elements based on permissions. The guards are cosmetic -- they improve UX but are never a substitute for server-side checks.

**Superuser bypass.** Superusers bypass all permission checks. This is the only exception to the permission system.

---

### Background Jobs

Every stack has an async job queue.

**What goes in the queue:**
- Email delivery
- Webhook dispatch (with HMAC signing and retry logic)
- Workflow action execution
- File processing (thumbnails, format conversion, imports)
- Search reindexing
- Any operation that takes more than a few hundred milliseconds

**Job infrastructure:**
- Backed by Redis as the message broker
- Retries with exponential backoff for transient failures
- Dead letter handling for permanently failed jobs
- Monitoring dashboard (auth-gated, requires staff/superuser)
- Same application image as the main backend, different entrypoint

---

### Forms Engine

JSON Schema definitions rendered at runtime. No code changes needed to add a new form.

**FormDefinition model.** Stores a versioned JSON Schema with lifecycle states: draft, published, archived. Each version is immutable once published.

**21+ built-in field types.** Text, number, date, select, multi-select, checkbox, radio, file upload, rich text, and more. Each field type has validation rules, display configuration, and conditional logic support.

**Logic engine.** Conditional rules evaluated at runtime: show/hide fields based on other field values, require fields conditionally, calculate values from other fields.

**Validation.** JSON Schema validation on both frontend (immediate feedback) and backend (authoritative).

**Visual builder.** Frontend component for drag-and-drop form construction with live preview, per-field configuration panels, and JSON toggle for power users.

---

### Workflow Engine

JSON-defined state machines attachable to any model.

**States.** Each state has: name, label, is_initial flag, is_final flag, display color, optional form slug (require form submission on entry), and optional assigned role.

**Transitions.** Each transition has: from_state, to_state, label, conditions (array), and actions (array).

**Condition types:**
- `user_has_role` -- the current user must belong to a specific role/group
- `field_equals` -- a field on the target model must equal a specific value
- `field_in` -- a field must be one of a set of values
- `is_authenticated` -- the user must be logged in
- `is_superuser` -- the user must be a superuser

**Action types:**
- `notify_user` -- send an in-app notification
- `send_email` -- send an email via the email service
- `call_webhook` -- POST to an external URL with HMAC signing
- `update_field` -- set a field value on the target model

**Transition logging.** Every state transition is logged in an immutable audit trail: who, when, from_state, to_state, and any form data submitted.

**Async execution.** Actions are dispatched to the job queue. The transition itself is synchronous (state change + log entry), but side effects (email, webhooks) happen asynchronously.

---

### Feature Toggles

Environment-based feature flags.

**Defined in a central config file.** Each stack has a features configuration file that lists all toggleable features.

**Enabled via environment variables.** A feature is enabled by setting its env var to true (e.g., `FEATURE_FORMS=true`). Disabled by default unless explicitly enabled.

**Gate module registration at startup.** When a feature is disabled, its module/app is not registered with the framework. The code exists but is never loaded, never routed, never exposed.

**Tied to Docker Compose profiles.** Infrastructure dependencies (search engine, temporal server) are in Docker Compose profiles. Enabling a feature in the env also activates the corresponding infrastructure profile.

---

### Admin

Every stack provides a way to manage data.

**Built-in admin interface.** Each stack uses its ecosystem's admin tool. Some are full-featured (Django Admin, ActiveAdmin, Nova), some are dev-only (Prisma Studio). The admin is always auth-gated -- it requires a valid session plus staff or superuser status.

**Not a public-facing feature.** The admin is for internal use by the development team and authorized staff. It is not a customer-facing dashboard.

**Custom widgets where needed.** Stacks with rich admin interfaces ship custom widgets for JSON editing, form building, and workflow editing. Stacks with minimal admin interfaces keep them minimal -- the boilerplate stays lean.

---

### Testing

Integration tests against real infrastructure.

**Real database.** Tests run against Postgres. Never mock the database. The database is the source of truth and mocking it hides real bugs.

**Assert against database state.** After a mutation, query the database and verify the record exists with the correct values. Don't assert against hardcoded response strings -- those break when formatting changes.

**Test both allowed AND denied cases.** Every permission-gated operation needs at least two tests: one where the user has permission (succeeds) and one where they don't (fails with appropriate error).

**No empty test bodies.** Every test function contains assertions. A test with no assertions is worse than no test -- it gives false confidence.

**Seed data.** Before the test suite runs, seed data is loaded: admin user, default groups, default permissions. Tests build on this foundation rather than creating everything from scratch.

---

### Docker Infrastructure

Every stack ships with Docker Compose that boots the full development environment.

**Core services (every stack):**

| Service | Purpose |
|---------|---------|
| Backend | The framework-specific application server |
| Frontend | The frontend dev server (if separate process) |
| Postgres 16 | Primary database |
| Redis 7 | Cache, session store, job queue broker |
| MinIO | S3-compatible file storage for local development |
| Mailpit | Local email testing (catches all outgoing email) |
| Job worker | Same image as backend, different entrypoint |
| Job monitor | Web UI for inspecting job queues (auth-gated) |

**Optional services (feature-gated):**

| Service | Purpose |
|---------|---------|
| Search engine | Full-text search (OpenSearch, MeiliSearch, or equivalent) |
| Metrics exporters | Postgres and Redis metrics for monitoring |

**Health checks on all services.** Docker Compose health checks ensure services are actually ready, not just running. Dependent services wait for their dependencies to be healthy.

**One command.** `docker compose up` and everything runs. No manual steps, no "run this migration first", no "install this CLI tool". The compose file handles startup order, health checks, and initial setup.

---

### CI/CD

GitHub Actions with at minimum four jobs.

**Lint job.** Runs formatting checks and linters. Catches style violations before they reach review.

**Build job.** Compiles the application, generates any derived artifacts (types, migrations), and verifies the build succeeds. Runs with real Postgres and Redis services.

**Test job.** Runs the full test suite with real Postgres and Redis services. Seed data is loaded before tests run.

**Audit job.** Scans dependencies for known vulnerabilities. Blocks on critical vulnerabilities.

**CI must pass before merge.** No exceptions. Branch protection rules enforce this.

---

### Security

Every stack implements these security measures.

**Session and credential hardening:**
- Session tokens hashed with SHA256 before database storage
- API keys hashed before storage (never stored in plaintext)
- httpOnly cookies with secure flag in production and sameSite: lax
- CORS restricted to explicit origin whitelist from environment variables

**Authorization:**
- Auth check at the top of every resolver, endpoint, and action -- no exceptions
- Ownership checks on mutations: verify the record belongs to the current user (or allow superusers)
- Never trust client-provided IDs alone -- always re-verify ownership server-side

**Input validation:**
- Validate all input at API boundaries
- JSON Schema validation for forms engine payloads
- File upload validation: MIME type whitelist, size limits (50MB default), filename sanitization (strip `..`, null bytes, path separators)

**SSRF protection:**
- All outgoing HTTP requests (webhooks, workflow actions) go through a URL validator
- Block: localhost, 127.0.0.1, ::1, 0.0.0.0, private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x)
- Block: non-HTTP(S) schemes (file://, gopher://, ftp://)

**API hardening (GraphQL stacks):**
- Query depth limiting (max 10 levels)
- Query complexity limiting
- Introspection disabled in production
- Debug endpoints disabled in production

**Error handling:**
- Masked errors in production -- no stack traces, no internal details
- Structured error responses with error codes, not raw exception messages

**Webhook security:**
- All outbound webhooks signed with HMAC
- Receiving services can verify payload integrity

**CSV and data export:**
- Proper escaping to prevent formula injection
- Streaming for large exports to avoid memory issues

---

## Anti-Patterns

1. **Don't add domain features to the boilerplate.** Domain-specific logic belongs in the project that extends Boilerworks.

2. **Don't expose integer primary keys.** Use UUID, cuid, or relay global IDs in all API responses.

3. **Don't assign permissions to users directly.** Always to groups. Groups to users.

4. **Don't call hard delete on business objects.** Soft delete: set `deleted_at` and `deleted_by`.

5. **Don't skip auth checks.** Every resolver, every endpoint, every mutation, every time.

6. **Don't hardcode configuration.** Environment variables, feature toggles, or runtime configuration.

7. **Don't create local doc files in repos.** Use GitHub issues and PRs for plans and specs.

8. **Don't rebase.** New commits only.

9. **Don't add AI attribution to commits.** No co-authorship messages, ever.

10. **Don't batch unrelated changes.** One PR per issue unless trivially related.

11. **Don't mock the database in integration tests.** Hit the real database.

12. **Don't store session tokens or API keys in plaintext.** Hash before storage.

13. **Don't fetch user-provided URLs without SSRF validation.** Always validate outgoing requests.

14. **Don't return raw error details or stack traces in production.** Mask errors.

---

## Extending Boilerworks

When starting a new project:

1. **Select the template.** Use the stack selection guide above. Match by domain first, then by team profile. Use the two-template decision table when a backend has multiple frontend options.

2. **Fork or clone.** Start from the template repository. This gives you all the infrastructure, patterns, and conventions.

3. **Rename.** Update the project name in settings, Docker Compose, package configs, and any hardcoded references.

4. **Delete example data.** Remove the example forms, workflows, and seed data. Keep the engines -- they're the infrastructure you're building on.

5. **Set up agent shims.** Create CLAUDE.md and AGENTS.md (plus CALLIOPE.md where the project uses it) pointing to `bootstrap.md`. Copy the shim structure from the template.

6. **Set up memory.** Create the memory directory for persistent AI context. Initialize MEMORY.md with project-specific context.

7. **Create your first domain module.** Follow the patterns documented in `bootstrap.md`. The per-stack primer has code examples.

8. **Follow the development process.** Issue, branch, PR, comment, test, merge. Every time.

9. **Ship.** The boilerplate gives you auth, permissions, forms, workflows, file uploads, search, background tasks, email, monitoring, and a frontend. Your job is to build the domain logic on top.
