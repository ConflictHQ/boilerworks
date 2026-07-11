# Boilerworks Rust Micro -- Primer

> Axum microservice with API-key auth. Compile-time safety, zero-cost
> abstractions, and blazing async I/O via tokio. Choose this for
> performance-critical services and systems-adjacent work where Rust's
> safety guarantees matter.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-rust-micro`
**Sibling variant:** None

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

- Performance-critical internal services where latency budgets are tight
  and memory usage matters -- Rust's zero-cost abstractions and no GC
  mean predictable, low-latency behavior.
- Systems-adjacent work: data pipeline endpoints, file processors,
  protocol bridges, anything touching hardware or OS-level concerns.
- Services where correctness is paramount -- Rust's type system and
  borrow checker catch entire categories of bugs at compile time.

### Not Ideal For

- Rapid prototyping where iteration speed matters more than runtime
  performance. Rust's compile times and strictness slow the feedback loop.
- Teams without Rust experience. The learning curve is steep and the
  ecosystem is less batteries-included than Python or Node.
- Applications that will grow into user-facing products. Start with a
  full-stack template instead.

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
Axum (tokio async runtime)
  |-- SQLx (compile-time checked SQL) or SeaORM (Postgres)
  |-- Redis (optional, via deadpool-redis)
  +-- Health check at /health
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Axum + tokio | Ergonomic async web framework, tower middleware ecosystem |
| API | REST (JSON) | serde for fast serialization/deserialization |
| Query | SQLx or SeaORM | SQLx for compile-time checked SQL; SeaORM for active-record style |
| Database | Postgres 16 | Standard across all stacks |
| Cache | Redis (optional) | Only if caching is needed |
| Auth | API-key middleware | SHA256-hashed keys |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Struct with `created_at`/`updated_at` | No user references |
| Soft deletes | `deleted_at` field | `WHERE deleted_at IS NULL` |
| External IDs (no integer PKs) | UUID primary keys | `uuid` crate |
| API contract | REST (JSON) | Axum extractors + serde |
| MutationResult pattern | `ApiResponse<T>` | `{ok, message, errors, data}` |
| Auth | API-key middleware | SHA256 hashing via `sha2` crate |
| Permissions | Key-level scopes | Tower middleware |
| Background jobs | None (or tokio::spawn) | Keep it simple |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars | `std::env::var()` |
| Admin panel | None | Keep it lean |
| Testing framework | cargo test + reqwest | Integration tests via HTTP |
| Linter/Formatter | rustfmt + clippy | Standard |
| Package manager | Cargo | `Cargo.toml` |
| Migrations | SQLx migrations or SeaORM migration | Versioned SQL |

---

## Pattern: Models & ORM

SQLx for compile-time verified SQL, or SeaORM for an active-record style
ORM. Both support async Postgres.

```sql
-- migrations/001_create_api_keys.sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    scopes TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

```rust
#[derive(sqlx::FromRow, Serialize)]
struct ApiKey {
    id: Uuid,
    name: String,
    key_hash: String,
    scopes: Vec<String>,
    is_active: bool,
    last_used_at: Option<DateTime<Utc>>,
    created_at: DateTime<Utc>,
}
```

SQLx verifies all queries against the database schema at compile time.
No runtime surprises.

---

## Pattern: API Layer

Axum handlers with typed extractors. serde for JSON serialization.

```rust
#[derive(Serialize)]
struct ApiResponse<T: Serialize> {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<T>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    errors: Vec<ApiError>,
}

async fn receive_webhook(
    State(pool): State<PgPool>,
    ApiKeyAuth(api_key): ApiKeyAuth,
    Json(payload): Json<WebhookPayload>,
) -> impl IntoResponse {
    // Process...
    Json(ApiResponse { ok: true, message: Some("Processed".into()), data: None::<()>, errors: vec![] })
}
```

---

## Pattern: Auth

API-key middleware using Axum extractors. Keys are SHA256-hashed before
storage.

```rust
struct ApiKeyAuth(ApiKey);

#[async_trait]
impl<S> FromRequestParts<S> for ApiKeyAuth
where
    S: Send + Sync,
    PgPool: FromRef<S>,
{
    type Rejection = (StatusCode, Json<ApiResponse<()>>);

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let key = parts.headers.get("X-API-Key")
            .and_then(|v| v.to_str().ok())
            .ok_or_else(|| reject("API key required"))?;

        let key_hash = sha256_hex(key);
        let pool = PgPool::from_ref(state);
        let api_key = sqlx::query_as::<_, ApiKey>(
            "SELECT * FROM api_keys WHERE key_hash = $1 AND is_active = TRUE"
        )
        .bind(&key_hash)
        .fetch_optional(&pool)
        .await
        .map_err(|_| reject("Internal error"))?
        .ok_or_else(|| reject("Invalid API key"))?;

        Ok(ApiKeyAuth(api_key))
    }
}
```

---

## Pattern: Permissions

Optional per-key scopes checked inline or via middleware.

```rust
fn require_scope(api_key: &ApiKey, scope: &str) -> Result<(), (StatusCode, Json<ApiResponse<()>>)> {
    if api_key.scopes.iter().any(|s| s == "*" || s == scope) {
        Ok(())
    } else {
        Err(reject("Missing required scope"))
    }
}
```

---

## Pattern: Background Jobs

Not included by default. For simple async work, use `tokio::spawn`.

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Simple env var checks at startup.

```rust
if std::env::var("FEATURE_MONITORING").as_deref() == Ok("true") {
    router = router.nest("/monitoring", monitoring_router());
}
```

---

## Pattern: Admin

None. Rust micro stays lean. Manage API keys via CLI tool or seed script.

---

## Pattern: Testing

`cargo test` with reqwest for integration tests. Real Postgres via
testcontainers or Docker Compose.

```rust
#[tokio::test]
async fn test_webhook_valid_key() {
    let (addr, pool) = spawn_test_server().await;
    let raw_key = create_test_api_key(&pool, vec!["*"]).await;

    let resp = reqwest::Client::new()
        .post(format!("http://{addr}/webhooks"))
        .header("X-API-Key", &raw_key)
        .json(&json!({"event": "order.created", "data": {"id": "123"}}))
        .send().await.unwrap();

    assert_eq!(resp.status(), 200);
    let body: ApiResponse<()> = resp.json().await.unwrap();
    assert!(body.ok);
}

#[tokio::test]
async fn test_webhook_no_key() {
    let (addr, _pool) = spawn_test_server().await;

    let resp = reqwest::Client::new()
        .post(format!("http://{addr}/webhooks"))
        .json(&json!({"event": "test"}))
        .send().await.unwrap();

    assert_eq!(resp.status(), 401);
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
| API | `api` (Rust binary, debian-slim or scratch) | 8080 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |

Multi-stage Docker build: build with `rust:1-bookworm`, run on
`debian:bookworm-slim` or `scratch`. Final image can be under 20MB.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** `cargo clippy -- -D warnings` + `cargo fmt --check`
- **Build job:** `cargo build --release` + Docker build (multi-stage)
- **Test job:** `cargo test` with Postgres service
- **Audit job:** `cargo audit`

---

## Pattern: Security

**API key hashing:** SHA256 via `sha2` crate before storage. Never store plaintext.

**Rate limiting:** Tower middleware or custom Axum layer.

**Input validation:** serde deserialization + custom validators.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default. `tower-http::cors` when needed.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | rustfmt | `rustfmt.toml` |
| Linting | clippy | `clippy.toml` / `Cargo.toml` |

`cargo fmt` and `cargo clippy` are non-negotiable.

---

## What Carries Over

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres)
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for rust-micro)

- Axum project scaffold with tower middleware
- API-key extractor and auth middleware
- SQLx or SeaORM setup with migrations
- ApiResponse pattern
- Multi-stage Dockerfile (build + scratch/slim)
- CI pipeline with clippy, fmt, test, audit

---

## Build Order

### Phase 0: Scaffolding
- [ ] Cargo project, Axum router, tokio runtime
- [ ] SQLx or SeaORM setup, migrations
- [ ] Docker Compose (api, postgres)
- [ ] Health check, rustfmt + clippy config

### Phase 1: Auth
- [ ] ApiKey table + queries
- [ ] API-key extractor middleware
- [ ] Key creation CLI tool or seed script
- [ ] Optional scope checking

### Phase 2: Core API
- [ ] REST handlers with serde JSON
- [ ] `ApiResponse<T>` wrapper
- [ ] Input validation

### Phase 3: Infrastructure + Polish
- [ ] Rate limiting
- [ ] CI pipeline (clippy, fmt, test, audit)
- [ ] README, CLAUDE.md
