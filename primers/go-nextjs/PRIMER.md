# Boilerworks Go + Next.js -- Primer

> Go backend with a rich Next.js 16 frontend. API-first Go for teams that want
> Go's performance and simplicity on the backend with React's interactivity on
> the frontend. Choose this over go-htmx when you need a full SPA.

**Status:** Planned (Tier 4)
**Repo:** `ConflictHQ/boilerworks-go-nextjs`
**Sibling variant:** [go-htmx](../go-htmx/PRIMER.md)

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

- High-performance API services that need a rich, interactive frontend --
  Go handles thousands of concurrent connections with minimal resource usage.
- Teams with Go backend expertise who want the shared Boilerworks Next.js
  frontend (Apollo Client, shared components, i18n, form/workflow builders).
- API-first architectures where the Go backend serves multiple clients
  (web, mobile, third-party) via GraphQL or REST.

### Not Ideal For

- Simple CRUD apps or internal tools where server-rendered HTML is sufficient.
  Choose [go-htmx](../go-htmx/PRIMER.md) -- one fewer service to deploy.
- Teams without Go experience where the learning curve outweighs the
  performance benefits. Consider [fastapi-nextjs](../fastapi-nextjs/PRIMER.md).
- Projects that need a large ecosystem of prebuilt backend middleware.

### vs go-htmx

Choose go-nextjs when you need rich client-side interactivity: complex
dashboards, drag-and-drop builders, form wizards, real-time collaboration,
or anything that benefits from React's component model.

Choose go-htmx when server-rendered simplicity wins: CRUD apps, admin tools,
monitoring dashboards where HTMX covers all dynamic behavior.

Both share the same Go backend patterns. The difference is the frontend.

---

## Architecture

```
Browser
  +-- Next.js 16 (shared frontend -- see NEXTJS_FRONTEND.md)
        +-- Apollo Client -> GraphQL API (or REST)
              |
              v
        Go (Chi or Echo router)
              |-- gqlgen (GraphQL) or REST handlers
              |-- Asynq (Redis-backed async jobs)
              |-- Postgres 16 (via sqlc or GORM)
              |-- Redis 7 (cache, sessions, job broker)
              +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Go 1.22+ (Chi or Echo) | Fast, simple, single binary |
| Frontend | Next.js 16 | Shared frontend -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) |
| API | GraphQL (gqlgen) or REST | gqlgen for consistency with Next.js stacks; REST is valid |
| ORM/Query | sqlc or GORM | sqlc preferred for type-safe SQL |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Asynq (Redis-backed) | Go-native, simple |
| Auth | Custom session middleware | httpOnly cookies, SHA256 hashing |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Struct embedding (`AuditFields`) | `CreatedAt/By`, `UpdatedAt/By` |
| Soft deletes | `DeletedAt`/`DeletedBy` fields | `WHERE deleted_at IS NULL` |
| External IDs (no integer PKs) | UUID primary keys | `google/uuid` |
| API contract | GraphQL (gqlgen) or REST | JSON over HTTP |
| MutationResult pattern | `MutationResult` GraphQL type | `{ok, errors}` |
| Auth (session-based) | Custom middleware | httpOnly cookies |
| Permissions (group-based) | Custom RBAC | Middleware + resolver checks |
| Background jobs | Asynq | Redis-backed tasks |
| Forms engine | Phase 2 | JSON Schema, Go validation |
| Workflow engine | Phase 2 | State machine, Go implementation |
| Feature toggles | Env vars + init-time gating | Conditional route/resolver registration |
| Admin panel | Minimal (custom or skip) | Keep it lean |
| Testing framework | Go testing + testify | `httptest` for API tests |
| Linter/Formatter | gofmt + golangci-lint | Standard Go tooling |
| Package manager | Go modules | `go.mod` |
| Migrations | goose or golang-migrate | Versioned SQL files |

---

## Pattern: Models & ORM

Identical to go-htmx. sqlc preferred, GORM as alternative. UUID primary keys.
Struct embedding for audit fields.

```go
type Product struct {
    ID    uuid.UUID       `db:"id"`
    Name  string          `db:"name"`
    Slug  string          `db:"slug"`
    Price decimal.Decimal `db:"price"`
    AuditFields
}
```

---

## Pattern: API Layer

GraphQL via gqlgen is recommended for consistency with the shared Next.js
frontend (Apollo Client). REST is a valid alternative.

**gqlgen schema:**

```graphql
type Product {
    id: ID!
    name: String!
    slug: String!
    price: String!
}

type MutationResult {
    ok: Boolean!
    errors: [FieldError!]
}

type Query {
    products(search: String): [Product!]!
}

type Mutation {
    createProduct(name: String!, price: String!): MutationResult!
}
```

**Resolver:**

```go
func (r *queryResolver) Products(ctx context.Context, search *string) ([]*model.Product, error) {
    user := auth.UserFromContext(ctx)
    if user == nil {
        return nil, fmt.Errorf("authentication required")
    }
    if err := r.perms.Require(user, "product.view"); err != nil {
        return nil, err
    }
    return r.queries.ListProducts(ctx, search)
}
```

Auth check at the top of every resolver. No exceptions.

---

## Pattern: Auth

Identical to go-htmx. Custom session middleware, SHA256-hashed tokens,
httpOnly cookies. Server-side revocation.

Frontend: Next.js auth gate -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Permissions

Identical to go-htmx. Custom RBAC with group-based permissions. Checked in
resolvers and middleware.

Frontend: permission guards via shared Next.js hooks.

---

## Pattern: Background Jobs

Identical to go-htmx. Asynq with Redis backend. Task handlers in
`internal/jobs/`.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Go backend implementation, Next.js
DynamicForm + FormBuilder from shared frontend.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Go backend, Asynq for async actions.
Next.js WorkflowBuilder (ReactFlow) from shared frontend.

---

## Pattern: Feature Toggles

Identical to go-htmx. Environment variables checked at startup. Conditional
route and resolver registration.

---

## Pattern: Admin

Minimal. Custom admin endpoints behind permission checks, or manage via the
Next.js frontend admin views.

---

## Pattern: Testing

Identical to go-htmx. Go testing + testify + `httptest`. Real Postgres via
testcontainers-go. Test via GraphQL or REST endpoints.

```go
func TestCreateProduct(t *testing.T) {
    srv := setupTestServer(t)
    query := `mutation { createProduct(name: "Widget", price: "9.99") { ok errors { field messages } } }`
    resp := srv.PostGraphQL(query, withAuthUser(testUser))

    assert.True(t, resp.Data.CreateProduct.Ok)
    product, _ := srv.DB.GetProductBySlug(context.Background(), "widget")
    assert.Equal(t, "Widget", product.Name)
}
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via API layer, not isolated function tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `api` (Go binary, scratch or alpine) | 8080 | `GET /health` |
| Frontend | `ui` (Next.js) | 3000 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Asynq Worker | Same binary, different entrypoint | -- | -- |
| Asynqmon | hibiken/asynqmon | 8081 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** golangci-lint (backend), ESLint + Prettier (frontend)
- **Build job:** `go build` + Docker build (multi-stage)
- **Test job:** `go test ./...` + Postgres + Redis services
- **Audit job:** `govulncheck` (backend), npm audit (frontend)

---

## Pattern: Security

Identical to go-htmx for the backend. Session hardening, permission checks,
struct validation, SSRF protection, file upload validation.

GraphQL-specific: query depth limiting via gqlgen middleware, introspection
disabled in prod, masked error messages.

CORS restricted to explicit origin whitelist for the Next.js frontend.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | gofmt | Standard |
| Linting | golangci-lint | `.golangci.yml` |
| Frontend formatting | Prettier | `.prettierrc` |
| Frontend linting | ESLint | `eslint.config.js` |

---

## What Carries Over

### Frontend (shared across all Next.js stacks)

The Next.js frontend is backend-agnostic. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md). Carries over as-is from other
Next.js stacks.

### From go-htmx (reusable as-is)

All Go backend code carries over unchanged:
- Models, sqlc queries, audit field patterns
- Session auth middleware, permission system
- Asynq job definitions and handlers
- Migration files, feature toggles
- Docker infrastructure (except adding the frontend service)

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new implementation)

- gqlgen GraphQL schema and resolvers (replaces HTMX handlers if using GraphQL)
- Go-to-Next.js session handoff (cookie configuration, CORS)
- GraphQL context with auth + permissions

---

## Build Order

### Phase 0: Scaffolding
- [ ] Go module, Chi or Echo router, project layout
- [ ] sqlc or GORM setup, goose migrations
- [ ] gqlgen GraphQL setup (or REST routers)
- [ ] Next.js 16 frontend (copy from shared template)
- [ ] Docker Compose (api, ui, postgres, redis, minio, mailpit)
- [ ] Health check, golangci-lint + ESLint config

### Phase 1: Auth + Permissions
- [ ] Session auth middleware, httpOnly cookies
- [ ] User, Group, Permission tables + seed data
- [ ] Permission checking in resolvers
- [ ] Frontend auth gate (shared from NEXTJS_FRONTEND)

### Phase 2: Core API
- [ ] GraphQL schema with gqlgen (or REST endpoints)
- [ ] MutationResult pattern
- [ ] Audit logging via context
- [ ] Soft delete pattern

### Phase 3: Forms Engine
- [ ] FormDefinition model, field types, validation (Go)
- [ ] GraphQL CRUD
- [ ] Frontend DynamicForm + FormBuilder (shared)

### Phase 4: Workflow Engine
- [ ] Workflow models, state machine service (Go)
- [ ] Asynq action handlers
- [ ] Frontend WorkflowBuilder (shared)

### Phase 5: Infrastructure + Polish
- [ ] File uploads, email, notifications
- [ ] Feature toggles, Asynq monitoring
- [ ] Seed data, CI pipeline, README, CLAUDE.md
