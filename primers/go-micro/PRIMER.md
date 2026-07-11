# Boilerworks Go Micro -- Primer

> Minimal Go microservice with API-key auth. Single binary, minimal dependencies,
> fast startup. Choose this for performance-critical internal APIs, webhook
> processors, and infrastructure services.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-go-micro`
**Sibling variant:** None

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

- High-performance internal APIs where every millisecond and megabyte counts --
  single binary, sub-millisecond startup, minimal memory footprint.
- Infrastructure services, sidecar processes, webhook processors, and data
  pipeline endpoints where Go's concurrency model shines.
- Teams that want maximum simplicity -- no framework opinions, no ORM magic,
  just Go standard library patterns with a thin router and raw SQL.

### Not Ideal For

- Services that need a rich query builder or migration system out of the box.
  Go's ecosystem is more manual than Django or Rails.
- Teams without Go experience. The minimal abstraction means more boilerplate
  for common patterns.
- Applications that will grow into a full user-facing product. Start with
  [go-htmx](../go-htmx/PRIMER.md) or [go-nextjs](../go-nextjs/PRIMER.md).

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
Go (Chi or Echo router)
  |-- sqlc or raw SQL (Postgres)
  |-- Redis (optional, for caching)
  +-- Health check at /health
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Go 1.22+ (Chi or Echo) | Single binary, fast, minimal dependencies |
| API | REST (JSON) | Standard HTTP handlers |
| Query | sqlc or raw SQL | sqlc for type safety; raw SQL for zero dependencies |
| Database | Postgres 16 | Standard across all stacks |
| Cache | Redis (optional) | Only if caching is needed |
| Auth | API-key middleware | SHA256-hashed keys |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Struct with `CreatedAt`/`UpdatedAt` | No user references |
| Soft deletes | `DeletedAt` field | `WHERE deleted_at IS NULL` |
| External IDs (no integer PKs) | UUID primary keys | `google/uuid` |
| API contract | REST (JSON) | Standard HTTP handlers |
| MutationResult pattern | `ApiResponse` struct | `{Ok, Message, Errors}` |
| Auth | API-key middleware | SHA256 hashing |
| Permissions | Key-level scopes | Middleware checks |
| Background jobs | None (or goroutines) | Keep it simple |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars | `os.Getenv()` |
| Admin panel | None | Keep it lean |
| Testing framework | Go testing + testify | `httptest` |
| Linter/Formatter | gofmt + golangci-lint | Standard |
| Package manager | Go modules | `go.mod` |
| Migrations | goose or golang-migrate | Versioned SQL |

---

## Pattern: Models & ORM

sqlc for type-safe SQL queries with zero runtime overhead, or raw SQL with
`database/sql` and `pgx` for absolute minimalism.

```sql
-- schema.sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    scopes TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- queries/api_keys.sql
-- name: GetApiKeyByHash :one
SELECT * FROM api_keys WHERE key_hash = $1 AND is_active = TRUE;

-- name: UpdateLastUsed :exec
UPDATE api_keys SET last_used_at = NOW() WHERE id = $1;
```

sqlc generates Go structs and query methods at build time. No reflection, no
runtime cost.

---

## Pattern: API Layer

Standard Go HTTP handlers. JSON request/response via `encoding/json`.

```go
type ApiResponse struct {
    Ok      bool        `json:"ok"`
    Message string      `json:"message,omitempty"`
    Data    interface{} `json:"data,omitempty"`
    Errors  []ApiError  `json:"errors,omitempty"`
}

type WebhookPayload struct {
    Event string          `json:"event"`
    Data  json.RawMessage `json:"data"`
}

func (h *WebhookHandler) Receive(w http.ResponseWriter, r *http.Request) {
    var payload WebhookPayload
    if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
        writeJSON(w, http.StatusBadRequest, ApiResponse{Ok: false, Message: "Invalid JSON"})
        return
    }
    // Process...
    writeJSON(w, http.StatusOK, ApiResponse{Ok: true, Message: "Processed"})
}
```

---

## Pattern: Auth

API-key middleware. Keys are SHA256-hashed before storage.

```go
func ApiKeyMiddleware(queries *db.Queries) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            key := r.Header.Get("X-API-Key")
            if key == "" {
                writeJSON(w, http.StatusUnauthorized, ApiResponse{Ok: false, Message: "API key required"})
                return
            }

            keyHash := sha256Hex(key)
            apiKey, err := queries.GetApiKeyByHash(r.Context(), keyHash)
            if err != nil {
                writeJSON(w, http.StatusUnauthorized, ApiResponse{Ok: false, Message: "Invalid API key"})
                return
            }

            queries.UpdateLastUsed(r.Context(), apiKey.ID)
            ctx := context.WithValue(r.Context(), apiKeyContextKey, &apiKey)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

---

## Pattern: Permissions

Optional per-key scopes checked via middleware or inline.

```go
func RequireScope(scope string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            apiKey := ApiKeyFromContext(r.Context())
            if !hasScope(apiKey.Scopes, scope) {
                writeJSON(w, http.StatusForbidden, ApiResponse{Ok: false, Message: "Missing scope"})
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

---

## Pattern: Background Jobs

Not included by default. For simple async work, use goroutines with context
cancellation. For durable jobs, add Asynq.

```go
// Simple background processing:
go func() {
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    processWebhook(ctx, payload)
}()
```

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Simple env var checks at startup.

```go
monitoringEnabled := os.Getenv("FEATURE_MONITORING") == "true"
if monitoringEnabled {
    r.Mount("/monitoring", monitoringRouter)
}
```

---

## Pattern: Admin

None. Go micro stays lean. Manage API keys via CLI tool or seed script.

---

## Pattern: Testing

Go testing with testify. `httptest` for handler tests. Real Postgres via
testcontainers-go.

```go
func TestWebhookHandler(t *testing.T) {
    db := setupTestDB(t)
    rawKey := "test-key"
    createTestApiKey(t, db, rawKey, []string{"*"})

    handler := NewWebhookHandler(db)
    router := setupRouter(handler, db)

    body := `{"event":"order.created","data":{"id":"123"}}`
    req := httptest.NewRequest("POST", "/webhooks", strings.NewReader(body))
    req.Header.Set("X-API-Key", rawKey)
    req.Header.Set("Content-Type", "application/json")
    w := httptest.NewRecorder()

    router.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
    var resp ApiResponse
    json.Unmarshal(w.Body.Bytes(), &resp)
    assert.True(t, resp.Ok)
}

func TestWebhookHandlerNoKey(t *testing.T) {
    db := setupTestDB(t)
    handler := NewWebhookHandler(db)
    router := setupRouter(handler, db)

    req := httptest.NewRequest("POST", "/webhooks", strings.NewReader(`{}`))
    w := httptest.NewRecorder()

    router.ServeHTTP(w, req)

    assert.Equal(t, http.StatusUnauthorized, w.Code)
}
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both valid and invalid API key cases
- Integration tests via HTTP handlers
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| API | `api` (Go binary, scratch or alpine) | 8080 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |

Minimal. Possibly the smallest Docker image of any Boilerworks stack -- Go
binary on scratch can be under 15MB.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** golangci-lint
- **Build job:** `go build` + Docker build (multi-stage, scratch base)
- **Test job:** `go test ./...` with Postgres service
- **Audit job:** `govulncheck`

---

## Pattern: Security

**API key hashing:** SHA256 before storage. Never store plaintext.

**Rate limiting:** Custom middleware or `golang.org/x/time/rate`.

**Input validation:** Manual struct validation or `go-playground/validator`.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | gofmt | Standard |
| Linting | golangci-lint | `.golangci.yml` |

`gofmt` is non-negotiable. Keep it simple.

---

## What Carries Over

### From go-htmx (subset, reusable patterns)

- sqlc query patterns, migration setup
- Middleware patterns (auth, logging)
- Docker Compose (Postgres)
- Go test setup with testcontainers-go

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for micro)

- API-key middleware (replaces session auth)
- ApiKey model and seed script
- Per-key scope system
- Minimal project structure (no frontend, no templates)

---

## Build Order

### Phase 0: Scaffolding
- [ ] Go module, Chi or Echo router
- [ ] sqlc or raw SQL setup, goose migrations
- [ ] Docker Compose (api, postgres)
- [ ] Health check, golangci-lint config

### Phase 1: Auth
- [ ] ApiKey table + sqlc queries
- [ ] API-key middleware
- [ ] Key creation CLI tool or seed script
- [ ] Optional scope checking

### Phase 2: Core API
- [ ] REST handlers with JSON encoding
- [ ] `ApiResponse` wrapper
- [ ] Input validation

### Phase 3: Infrastructure + Polish
- [ ] Rate limiting
- [ ] CI pipeline (lint, test, audit)
- [ ] README, CLAUDE.md
