# Boilerworks Go + HTMX -- Primer

> Lightweight Go backend with HTMX + Templ for server-rendered HTML. Choose this
> for performance-critical services, CLI-adjacent tools, infrastructure dashboards,
> and teams that value simplicity, fast compile times, and minimal dependencies.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-go-htmx`
**Sibling variant:** [go-nextjs](../go-nextjs/PRIMER.md)

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

- Performance-critical services -- Go compiles to a single binary with minimal
  memory footprint, sub-millisecond startup, no runtime overhead.
- Infrastructure dashboards, internal tooling, and DevOps platforms where
  server-rendered HTML is the natural fit and the team values Go's simplicity.
- Teams that want a lean, dependency-minimal stack -- no ORM magic, no
  framework opinions, just standard library patterns with a thin router.

### Not Ideal For

- Apps needing rich client-side interactivity -- drag-and-drop, complex
  dashboards, real-time collaboration. Choose [go-nextjs](../go-nextjs/PRIMER.md).
- Projects that need a large ecosystem of prebuilt middleware and plugins.
  Go's web ecosystem is intentionally minimal.
- Teams without Go experience who would lose more time learning Go idioms than
  they save on runtime performance.

### vs go-nextjs

Choose go-htmx when server-rendered simplicity wins: CRUD apps, admin tools,
monitoring dashboards, internal platforms where HTMX handles all dynamic
behavior and a full SPA is unnecessary overhead.

Choose go-nextjs when you need rich client-side interactivity: complex
dashboards, drag-and-drop builders, form wizards, or anything that benefits
from React's component model.

Both share the same Go backend patterns. The difference is the frontend
delivery model.

---

## Architecture

```
Browser
  +-- Templ templates + HTMX + Tailwind CSS
        |
        v (standard HTTP requests + HTMX partial responses)
        |
  Go (Chi or Echo router)
        |-- Asynq (Redis-backed async jobs)
        |-- Postgres 16 (via sqlc or GORM)
        |-- Redis 7 (cache, sessions, job broker)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Go 1.22+ (Chi or Echo) | Fast, simple, single binary, minimal dependencies |
| Frontend | Templ + HTMX + Tailwind CSS | Type-safe Go templates, progressive enhancement, no build step for JS |
| API | Server-rendered HTML + HTMX partials | No separate API -- handlers return HTML fragments |
| ORM/Query | sqlc (generated type-safe SQL) or GORM | sqlc preferred: write SQL, get Go; GORM for rapid prototyping |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Asynq (Redis-backed) | Simple, Go-native, Redis-backed task queue |
| Auth | Custom session middleware | httpOnly cookies, server-side sessions |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Struct embedding (`AuditFields`) | `CreatedAt/By`, `UpdatedAt/By` in every model |
| Soft deletes | `DeletedAt`/`DeletedBy` fields | `WHERE deleted_at IS NULL` in all queries |
| External IDs (no integer PKs) | UUID primary keys | `google/uuid` package |
| API contract | HTTP handlers returning HTML | Full pages or HTMX partials |
| MutationResult pattern | Form validation errors | Errors rendered inline via HTMX swap |
| Auth (session-based) | Custom middleware | httpOnly cookies, SHA256 token hashing |
| Permissions (group-based) | Custom RBAC middleware | `RequirePermission("product.view")` |
| Background jobs | Asynq (Redis-backed) | Task handlers in `internal/jobs/` |
| Forms engine | Phase 2 | JSON Schema, Go validation |
| Workflow engine | Phase 2 | State machine, Go implementation |
| Feature toggles | Env vars + init-time gating | Conditional route registration |
| Admin panel | Minimal (custom handlers) | Or skip -- keep it lean |
| Testing framework | Go testing + testify | `httptest` for handler tests |
| Linter/Formatter | gofmt + golangci-lint | Standard Go tooling |
| Package manager | Go modules | `go.mod` + `go.sum` |
| Migrations | goose or golang-migrate | Versioned SQL files |

---

## Pattern: Models & ORM

sqlc is preferred: write SQL, get type-safe Go code. GORM is an alternative
for teams that prefer an ORM.

**sqlc approach -- write SQL, generate Go:**

```sql
-- queries/products.sql
-- name: GetProduct :one
SELECT * FROM products WHERE id = $1 AND deleted_at IS NULL;

-- name: ListProducts :many
SELECT * FROM products WHERE deleted_at IS NULL ORDER BY created_at DESC;

-- name: CreateProduct :one
INSERT INTO products (id, name, slug, price, created_by, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
RETURNING *;
```

sqlc generates type-safe Go structs and query methods. No reflection, no
runtime overhead.

**Shared audit fields (struct embedding):**

```go
type AuditFields struct {
    CreatedAt time.Time  `db:"created_at"`
    CreatedBy *uuid.UUID `db:"created_by"`
    UpdatedAt time.Time  `db:"updated_at"`
    UpdatedBy *uuid.UUID `db:"updated_by"`
    DeletedAt *time.Time `db:"deleted_at"`
    DeletedBy *uuid.UUID `db:"deleted_by"`
}

type Product struct {
    ID    uuid.UUID      `db:"id"`
    Name  string         `db:"name"`
    Slug  string         `db:"slug"`
    Price decimal.Decimal `db:"price"`
    AuditFields
}
```

---

## Pattern: API Layer

No separate API. HTTP handlers return HTML -- full pages for initial loads,
HTMX partials for dynamic updates. Templ provides type-safe, compiled templates.

```go
func (h *ProductHandler) List(w http.ResponseWriter, r *http.Request) {
    user := auth.UserFromContext(r.Context())
    if err := h.perms.Require(user, "product.view"); err != nil {
        http.Error(w, "Forbidden", http.StatusForbidden)
        return
    }

    search := r.URL.Query().Get("search")
    products, err := h.queries.ListProducts(r.Context(), search)
    if err != nil {
        http.Error(w, "Internal error", http.StatusInternalServerError)
        return
    }

    // HTMX request -- return partial
    if r.Header.Get("HX-Request") == "true" {
        component := views.ProductTable(products)
        component.Render(r.Context(), w)
        return
    }

    // Full page
    component := views.ProductListPage(products, search)
    component.Render(r.Context(), w)
}
```

**Templ template (type-safe, compiled):**

```go
// views/products.templ
templ ProductTable(products []db.Product) {
    <div id="product-table">
        <table class="min-w-full divide-y divide-gray-200">
            for _, p := range products {
                <tr>
                    <td class="px-6 py-4">{ p.Name }</td>
                    <td class="px-6 py-4">{ p.Price.String() }</td>
                </tr>
            }
        </table>
    </div>
}
```

---

## Pattern: Auth

Custom session middleware. Sessions stored in Postgres or Redis. Token
delivered as httpOnly cookie. SHA256-hashed before storage.

```go
func (m *AuthMiddleware) Handler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        cookie, err := r.Cookie("session")
        if err != nil {
            http.Redirect(w, r, "/login", http.StatusSeeOther)
            return
        }
        tokenHash := sha256Hex(cookie.Value)
        session, err := m.queries.GetSessionByHash(r.Context(), tokenHash)
        if err != nil || session.ExpiresAt.Before(time.Now()) {
            http.Redirect(w, r, "/login", http.StatusSeeOther)
            return
        }
        ctx := auth.WithUser(r.Context(), session.User)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

Server-side revocation: delete the session row. Instant.

---

## Pattern: Permissions

Custom RBAC. Users belong to groups. Groups have permissions. Middleware
checks permissions before handler execution.

```go
func (p *PermissionService) Require(user *User, slug string) error {
    has, err := p.queries.UserHasPermission(context.Background(), user.ID, slug)
    if err != nil || !has {
        return ErrForbidden
    }
    return nil
}

// Middleware for route-level checks
func RequirePermission(perms *PermissionService, slug string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            user := auth.UserFromContext(r.Context())
            if err := perms.Require(user, slug); err != nil {
                http.Error(w, "Forbidden", http.StatusForbidden)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

---

## Pattern: Background Jobs

Asynq -- simple, Redis-backed, Go-native task queue.

```go
// Task definition
const TypeProcessInvoice = "invoice:process"

func NewProcessInvoiceTask(invoiceID uuid.UUID) (*asynq.Task, error) {
    payload, _ := json.Marshal(map[string]string{"invoice_id": invoiceID.String()})
    return asynq.NewTask(TypeProcessInvoice, payload, asynq.MaxRetry(3)), nil
}

// Task handler
func HandleProcessInvoice(ctx context.Context, t *asynq.Task) error {
    var p struct{ InvoiceID string `json:"invoice_id"` }
    json.Unmarshal(t.Payload(), &p)
    // process invoice...
    return nil
}

// Dispatch
task, _ := NewProcessInvoiceTask(invoice.ID)
client.Enqueue(task)
```

Asynq provides a built-in web UI (`asynqmon`) for monitoring at port 8080.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Go implementation of validation and logic
engine. Templ partials render form fields from JSON Schema definitions.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Go implementation with Asynq tasks for
async action execution. Transition logging via database.

---

## Pattern: Feature Toggles

Environment variables checked at startup. Conditional route registration.

```go
type Features struct {
    Forms     bool
    Workflows bool
}

func LoadFeatures() Features {
    return Features{
        Forms:     os.Getenv("FEATURE_FORMS") == "true",
        Workflows: os.Getenv("FEATURE_WORKFLOWS") == "true",
    }
}

// In router setup:
if features.Forms {
    r.Mount("/forms", formsRouter)
}
```

When disabled, routes are not registered and templates do not render
navigation links. Tied to Docker Compose profiles.

---

## Pattern: Admin

Minimal. Custom admin handlers behind permission checks, or skip entirely
and manage data via the main application UI. Go stacks stay lean.

---

## Pattern: Testing

Go testing with testify assertions. `httptest` for handler integration tests.
Real Postgres via testcontainers-go.

```go
func TestCreateProduct(t *testing.T) {
    db := setupTestDB(t)
    handler := NewProductHandler(db)

    body := `{"name":"Widget","price":"9.99"}`
    req := httptest.NewRequest("POST", "/products", strings.NewReader(body))
    req = req.WithContext(auth.WithUser(req.Context(), testUser))
    w := httptest.NewRecorder()

    handler.Create(w, req)

    assert.Equal(t, http.StatusOK, w.Code)

    product, err := db.GetProductBySlug(context.Background(), "widget")
    assert.NoError(t, err)
    assert.Equal(t, "Widget", product.Name)
}

func TestCreateProductDenied(t *testing.T) {
    db := setupTestDB(t)
    handler := NewProductHandler(db)

    req := httptest.NewRequest("POST", "/products", nil)
    // No user in context
    w := httptest.NewRecorder()

    handler.Create(w, req)

    assert.Equal(t, http.StatusForbidden, w.Code)
}
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via HTTP handlers, not isolated function tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `api` (Go binary, scratch or alpine) | 8080 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Asynq Worker | Same binary, different entrypoint | -- | -- |
| Asynqmon | hibiken/asynqmon | 8081 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No separate frontend container. Go serves templates, static files (Tailwind
via standalone CLI), and HTMX partials. Single binary -- tiny Docker image.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** golangci-lint
- **Build job:** `go build` + Docker build (multi-stage, scratch base)
- **Test job:** `go test ./...` with Postgres + Redis services
- **Audit job:** `govulncheck`

CI must pass before merge.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens, httpOnly cookies, secure in prod,
sameSite lax. Server-side revocation is instant.

**Authorization:** Permission check at the top of every handler. Ownership
checks on mutations.

**Input validation:** Struct validation (go-playground/validator or manual).
No framework-level validation -- explicit checks in handlers.

**SSRF protection:** URL validator on outgoing HTTP requests. Block private IPs,
localhost, non-HTTP schemes.

**CSRF protection:** Custom CSRF token middleware for form submissions. HTMX
requests include CSRF token via `hx-headers`.

**File uploads:** MIME whitelist, size limits via `http.MaxBytesReader`,
filename sanitization.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | gofmt | Standard (no config) |
| Linting | golangci-lint | `.golangci.yml` |
| Max line length | No hard limit (gofmt handles) | -- |
| Import sorting | goimports | Built into golangci-lint |
| CSS | Tailwind CSS | `tailwind.config.js` (standalone CLI) |

`gofmt` is non-negotiable. `golangci-lint` with a strict config. No tabs vs
spaces debate -- Go settled that.

---

## What Carries Over

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- CI pipeline structure (lint, test, audit jobs)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Shared Concepts (same mental model, Go implementation)

- Permission model (group-based, custom RBAC maps to Boilerworks pattern)
- Forms engine (JSON Schema, same field types, same lifecycle)
- Workflow engine (same state machine, same condition/action types)
- Audit trail (`created_by`/`updated_by` via context)
- Soft deletes (`deleted_at` filter in all queries)

### Needs Building (new implementation)

- sqlc queries and Go models with audit fields
- goose/golang-migrate migration setup
- Custom session auth middleware
- Custom RBAC permission system
- Asynq job queue setup
- Templ templates with HTMX patterns
- Tailwind CSS build via standalone CLI

---

## Build Order

### Phase 0: Scaffolding
- [ ] Go module, Chi or Echo router, project layout (`cmd/`, `internal/`)
- [ ] sqlc or GORM setup, database connection
- [ ] Templ templates + HTMX + Tailwind CSS (standalone CLI)
- [ ] goose or golang-migrate for migrations
- [ ] Docker Compose (api, postgres, redis, minio, mailpit)
- [ ] Health check, golangci-lint config

### Phase 1: Auth + Permissions
- [ ] Session model, token hashing, auth middleware
- [ ] Login/logout handlers with Templ templates
- [ ] User, Group, Permission tables + seed data
- [ ] Permission checking middleware
- [ ] Template permission guards

### Phase 2: Core Handlers
- [ ] CRUD handlers with HTMX partial responses
- [ ] Templ layouts (sidebar, nav, content area)
- [ ] Form validation + inline error rendering
- [ ] CSRF token middleware for HTMX

### Phase 3: Forms Engine
- [ ] FormDefinition model, field types, validation
- [ ] Logic engine (Go implementation)
- [ ] Templ partials for dynamic form rendering

### Phase 4: Workflow Engine
- [ ] Workflow models (definition, instance, transition log)
- [ ] State machine service
- [ ] Asynq task handlers for actions

### Phase 5: Infrastructure + Polish
- [ ] File uploads (MinIO via AWS SDK for Go)
- [ ] Email, notifications
- [ ] Feature toggles, Asynq monitoring
- [ ] Seed data, CI pipeline, README, CLAUDE.md
