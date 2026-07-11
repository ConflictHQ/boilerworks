# Boilerworks {Backend} + {Frontend} — Primer

> {One-line summary: what this stack is for and when to choose it.}

**Status:** {Done | Building | Planned}
**Repo:** `ConflictHQ/boilerworks-{backend}-{frontend}`
**Sibling variant:** {Link to sibling primer if this backend has two frontend options, or "None"}

---

## Table of Contents

1. [When to Choose This Stack](#when-to-choose-this-stack)
2. [Architecture](#architecture)
3. [Stack Mapping](#stack-mapping)
4. [Pattern: Models & ORM](#pattern-models--orm)
5. [Pattern: API Layer](#pattern-api-layer)
6. [Pattern: Auth](#pattern-auth)
7. [Pattern: Permissions](#pattern-permissions)
8. [Pattern: Background Jobs](#pattern-background-jobs)
9. [Pattern: Forms Engine](#pattern-forms-engine)
10. [Pattern: Workflow Engine](#pattern-workflow-engine)
11. [Pattern: Feature Toggles](#pattern-feature-toggles)
12. [Pattern: Admin](#pattern-admin)
13. [Pattern: Testing](#pattern-testing)
14. [Pattern: Docker Infrastructure](#pattern-docker-infrastructure)
15. [Pattern: CI/CD](#pattern-cicd)
16. [Pattern: Security](#pattern-security)
17. [Code Style & Enforcement](#code-style--enforcement)
18. [What Carries Over](#what-carries-over)
19. [Build Order](#build-order)

---

## When to Choose This Stack

### Ideal For

{2-3 bullet points describing the project types, domains, and team profiles where this stack excels.}

### Not Ideal For

{2-3 bullet points describing when to choose a different stack instead.}

### vs {Sibling Variant}

{For backends with two frontend options: when to pick THIS variant over the sibling. E.g., "Choose Django+Next.js for dashboards and SPAs that need rich client-side interactivity. Choose Django+HTMX for content-heavy CRUD apps where server-rendered simplicity wins." Omit this section if there's no sibling.}

---

## Architecture

```
{Stack diagram — Browser → Frontend → API contract → Backend → Services}
{Show all infrastructure: DB, cache, job queue, search, storage, email}
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | {framework} | {reason} |
| Frontend | {framework} | {reason} |
| API | {GraphQL/REST/HTMX/LiveView} | {reason} |
| ORM | {orm} | {reason} |
| Database | Postgres 16 | {standard across all stacks} |
| Cache/Broker | Redis 7 | {standard across all stacks} |
| Job Queue | {celery/bullmq/sidekiq/etc.} | {reason} |
| Auth | Session-based (httpOnly cookies) | {standard across all stacks} |
| Storage | MinIO (S3-compatible) | {standard across all stacks} |
| Email | Mailpit (dev) | {standard across all stacks} |

---

## Stack Mapping

How universal Boilerworks patterns map to this stack's implementation:

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | {implementation} | |
| Soft deletes | {implementation} | |
| External IDs (no integer PKs) | {implementation} | |
| API contract | {implementation} | |
| MutationResult pattern | {implementation} | |
| Auth (session-based) | {implementation} | |
| Permissions (group-based) | {implementation} | |
| Background jobs | {implementation} | |
| Forms engine | {implementation or "Phase 2"} | |
| Workflow engine | {implementation or "Phase 2"} | |
| Feature toggles | {implementation} | |
| Admin panel | {implementation} | |
| Testing framework | {implementation} | |
| Linter/Formatter | {implementation} | |
| Package manager | {implementation} | |
| Migrations | {implementation} | |

---

## Pattern: Models & ORM

{Code examples showing:}
- Base model / mixin with audit fields (created_at/by, updated_at/by)
- Soft delete implementation (deleted_at/by, never .delete())
- External ID strategy (UUID/cuid — never expose integer PKs)
- Example business model inheriting from base

```{language}
{code example}
```

---

## Pattern: API Layer

{GraphQL, REST+HTMX, LiveView channels — whatever this stack uses.}

{Code examples showing:}
- Type/serializer definition (mapped from ORM model)
- Query/endpoint implementation
- Mutation/action returning MutationResult {ok, errors}
- Context object (user, session, permissions)
- Auth check at top of every resolver/endpoint

```{language}
{code example}
```

---

## Pattern: Auth

{Code examples showing:}
- Session creation (httpOnly cookie, server-side storage)
- Session validation middleware/guard
- Login/logout flow
- Session token hashing (SHA256 before storage)

```{language}
{code example}
```

---

## Pattern: Permissions

{Code examples showing:}
- Group-based permission model (never user-based)
- Permission definition
- Permission check in resolver/endpoint
- Frontend permission guard (if applicable)

```{language}
{code example}
```

---

## Pattern: Background Jobs

{Code examples showing:}
- Job queue setup
- Job/task definition with retry logic
- Dispatching from business logic
- Monitoring dashboard

```{language}
{code example}
```

---

## Pattern: Forms Engine

{If applicable for v1. Some stacks may defer this to Phase 2.}

- JSON Schema definitions (versioned: draft → published → archived)
- Field types (21+ built-in)
- Validation (JSON Schema / Ajv or equivalent)
- Conditional logic (show/hide/require/calculate)
- Visual builder (if the frontend supports it)

---

## Pattern: Workflow Engine

{If applicable for v1. Some stacks may defer this to Phase 2.}

- State machine model (states, transitions, conditions, actions)
- Condition types: user_has_role, field_equals, field_in, is_authenticated
- Action types: notify_user, send_email, call_webhook, update_field
- Transition logging (immutable audit trail)
- Async execution via job queue

---

## Pattern: Feature Toggles

{Code example showing env-based feature flags:}
- Definition
- Checking
- Gating module/app registration
- Tying to Docker Compose profiles

```{language}
{code example}
```

---

## Pattern: Admin

{Code example showing:}
- Admin panel setup (Django Admin / Prisma Studio / ActiveAdmin / Nova / etc.)
- Model registration
- Custom widgets (if applicable)
- Auth-gating admin endpoints

---

## Pattern: Testing

{Code examples showing:}
- Test setup (real database, not mocks)
- API/GraphQL integration test
- Permission test (allowed + denied cases)
- Assertion against database state (not hardcoded strings)

```{language}
{code example}
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via API layer, not isolated model tests
- Real database — never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | {dockerfile} | {port} | {check} |
| Frontend | {dockerfile or "same container"} | 3000 | {check} |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Job Worker | {same as backend, different entrypoint} | — | — |
| Job Monitor | {flower/bull-board/etc.} | {port} | — |
| Storage | minio/minio | 9000/9001 | — |
| Email | axllent/mailpit | 8025/1025 | — |
| Search | {opensearch/meilisearch/none} | {port} | — |

---

## Pattern: CI/CD

{GitHub Actions pipeline:}
- Lint job
- Build job
- Test job (with Postgres + Redis services)
- Audit job (dependency vulnerabilities)

---

## Pattern: Security

{Stack-specific security measures. All stacks must implement:}

- Session token hashing (SHA256 before storage)
- API key hashing (never stored plaintext)
- SSRF protection (block private IPs, non-HTTP schemes on outgoing requests)
- CORS restricted to explicit origin whitelist
- Input validation at API boundaries
- File upload validation (MIME whitelist, size limits, filename sanitization)
- Ownership checks on mutations (verify record belongs to current user)
- {API-specific:} Query depth limiting, introspection disabled in prod, masked errors

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | {prettier/black/gofmt/etc.} | {config file} |
| Linting | {eslint/flake8/rubocop/etc.} | {config file} |
| Max line length | {length} | |
| Import sorting | {tool} | |
| Pre-commit hooks | {yes/no, tool} | |

---

## What Carries Over

### From Existing Templates (reusable as-is)

{List components, config, patterns that can be copied directly from existing Boilerworks templates.}

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Porting (same concept, new implementation)

{List patterns that need to be reimplemented in this stack's language/framework.}

---

## Build Order

### Phase 0: Scaffolding
- [ ] Project structure ({monorepo/monolith/etc.})
- [ ] {Backend framework} app with {ORM}, {API layer}
- [ ] {Frontend} app
- [ ] Docker Compose
- [ ] Health check, basic config

### Phase 1: Auth + Permissions
- [ ] Session auth (login, logout)
- [ ] Auth middleware/guard
- [ ] User, Group, Permission models + seed
- [ ] Permission checking
- [ ] Frontend auth gate

### Phase 2: Core API
- [ ] {API layer} setup with {ORM} integration
- [ ] Context (user, session, permissions)
- [ ] MutationResult pattern
- [ ] Audit logging

### Phase 3: Forms Engine
- [ ] Form models (definition, submission)
- [ ] Field types + validation
- [ ] Logic engine (conditions, calculations)
- [ ] API CRUD
- [ ] Frontend form renderer + builder

### Phase 4: Workflow Engine
- [ ] Workflow models (definition, instance, transition log)
- [ ] State machine service
- [ ] Job queue processors for actions
- [ ] API CRUD + transition mutations
- [ ] Frontend workflow builder

### Phase 5: Infrastructure & Polish
- [ ] File uploads (S3/MinIO)
- [ ] Email service
- [ ] Notifications (in-app)
- [ ] Feature toggles
- [ ] Seed data + examples
- [ ] README, CLAUDE.md, bootstrap.md
- [ ] CI pipeline
