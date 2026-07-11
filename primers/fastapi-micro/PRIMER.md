# Boilerworks FastAPI Micro -- Primer

> Lightweight FastAPI microservice with API-key auth. No users, no sessions, no
> frontend. Choose this for internal APIs, webhook processors, data pipelines,
> and any service that authenticates via API keys rather than user sessions.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-fastapi-micro`
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

- Internal APIs and microservices that authenticate callers via API keys --
  no user accounts, no sessions, no login flows.
- Webhook processors, data pipeline endpoints, and service-to-service
  communication where the caller is another service, not a human.
- Teams that want Python + async with minimal overhead -- FastAPI's
  auto-generated OpenAPI docs, Pydantic validation, and type hints.

### Not Ideal For

- Applications with user accounts, login flows, or session management. Choose
  [fastapi-nextjs](../fastapi-nextjs/PRIMER.md) or
  [fastapi-htmx](../fastapi-htmx/PRIMER.md) instead.
- Services that need a rich UI. The optional Jinja2 admin/monitoring UI is
  minimal. If you need a real frontend, use a full-size template.
- Projects that will grow into a full application. Start with a full-size
  template and scale down rather than starting micro and bolting on auth later.

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
FastAPI (async Python, Pydantic validation)
  |-- SQLAlchemy 2.0 async (Postgres)
  |-- Redis 7 (cache, optional)
  +-- Optional: Jinja2 UI for admin/monitoring
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI (Python 3.12+) | Async-native, Pydantic, OpenAPI docs |
| API | REST (FastAPI native) | Auto-generated OpenAPI at `/docs` |
| ORM | SQLAlchemy 2.0 (async) | Explicit, async-native |
| Database | Postgres 16 | Standard across all stacks |
| Cache | Redis 7 (optional) | Only if caching is needed |
| Auth | API-key middleware | SHA256-hashed keys, no sessions |
| Validation | Pydantic v2 | Request/response models |
| UI | Jinja2 (optional) | Minimal admin/monitoring dashboard |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `AuditBase` mapped superclass | Simplified -- no `created_by` user |
| Soft deletes | `SoftDeleteMixin` | `deleted_at` field |
| External IDs (no integer PKs) | UUID primary keys | Standard |
| API contract | REST (Pydantic models) | OpenAPI auto-generated |
| MutationResult pattern | Pydantic `ApiResponse` model | `{ok, data, errors}` |
| Auth | API-key middleware | No sessions, no users |
| Permissions | Key-level scopes (optional) | Per-key permission scopes |
| Background jobs | None (or Celery/ARQ if needed) | Add only when needed |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars | Simple boolean checks |
| Admin panel | Optional Jinja2 dashboard | Minimal |
| Testing framework | pytest + httpx | Real database |
| Linter/Formatter | Ruff | Standard |
| Package manager | uv | `pyproject.toml` |
| Migrations | Alembic | Standard |

---

## Pattern: Models & ORM

SQLAlchemy 2.0 async. Simplified audit fields -- no `created_by`/`updated_by`
since there are no user accounts.

```python
class AuditBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

Business models inherit from `AuditBase` with optional `SoftDeleteMixin`.

---

## Pattern: API Layer

Standard FastAPI REST endpoints. Pydantic models for request/response
validation. OpenAPI docs auto-generated at `/docs`.

```python
class WebhookPayload(BaseModel):
    event: str
    data: dict

class ApiResponse(BaseModel):
    ok: bool
    message: str | None = None
    errors: list[dict] | None = None


@router.post("/webhooks", response_model=ApiResponse)
async def receive_webhook(
    payload: WebhookPayload,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    # Process webhook...
    return ApiResponse(ok=True, message="Processed")
```

---

## Pattern: Auth

API-key middleware. Keys are SHA256-hashed before storage. Raw key shown
once at creation, never again. No sessions, no cookies, no users.

```python
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)


async def require_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    key = request.headers.get("X-API-Key")
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last_used_at
    api_key.last_used_at = datetime.utcnow()
    await db.commit()
    return api_key
```

Key creation: generate random key, hash it, store the hash, return the raw
key once.

---

## Pattern: Permissions

Optional per-key scopes. Each API key has a `scopes` array. Endpoints can
require specific scopes.

```python
def require_scope(scope: str):
    async def dependency(api_key: ApiKey = Depends(require_api_key)):
        if scope not in api_key.scopes and "*" not in api_key.scopes:
            raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")
    return Depends(dependency)

@router.post("/data/import", dependencies=[require_scope("data.write")])
async def import_data(...):
    ...
```

---

## Pattern: Background Jobs

Not included by default. Add Celery or ARQ only when async processing is
needed. For simple cases, use `BackgroundTasks` built into FastAPI.

```python
from fastapi import BackgroundTasks

@router.post("/webhooks")
async def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    api_key: ApiKey = Depends(require_api_key),
):
    background_tasks.add_task(process_webhook, payload)
    return ApiResponse(ok=True)
```

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Simple env var checks. No framework needed.

```python
FEATURE_MONITORING_UI = os.getenv("FEATURE_MONITORING_UI", "false") == "true"

if FEATURE_MONITORING_UI:
    app.mount("/admin", monitoring_app)
```

---

## Pattern: Admin

Optional Jinja2 monitoring dashboard. Shows API key usage, recent requests,
health status. Auth-gated via a separate admin API key or basic auth.

```python
if FEATURE_MONITORING_UI:
    @admin_router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
        keys = await db.execute(select(ApiKey).order_by(ApiKey.last_used_at.desc()))
        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "api_keys": keys.scalars().all(),
        })
```

---

## Pattern: Testing

pytest with httpx `AsyncClient`. Real Postgres. Test with API key headers.

```python
@pytest.fixture
async def api_key_header(db):
    raw_key = "test-key-123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db.add(ApiKey(name="test", key_hash=key_hash, scopes=["*"]))
    await db.commit()
    return {"X-API-Key": raw_key}


@pytest.mark.asyncio
async def test_webhook(client, api_key_header):
    response = await client.post(
        "/webhooks",
        json={"event": "order.created", "data": {"id": "123"}},
        headers=api_key_header,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_no_key(client):
    response = await client.post(
        "/webhooks",
        json={"event": "order.created", "data": {"id": "123"}},
    )
    assert response.status_code == 401
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both valid and invalid API key cases
- Integration tests via HTTP endpoints
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| API | `api` (FastAPI + uvicorn) | 8000 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine (optional) | 6379 | redis-cli ping |

Minimal. No frontend, no job worker, no monitoring unless needed.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Ruff
- **Build job:** Docker build
- **Test job:** pytest with Postgres service
- **Audit job:** `pip-audit`

---

## Pattern: Security

**API key hashing:** SHA256 before storage. Never store plaintext keys.

**Rate limiting:** slowapi on all endpoints. Per-key rate limits if needed.

**Input validation:** Pydantic v2 at all API boundaries.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default (no browser clients). Enable only if needed.

**No session concerns:** No cookies, no CSRF, no session fixation.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml` |
| Linting | Ruff (lint) | `pyproject.toml` |
| Max line length | 120 characters | `pyproject.toml` |
| Import sorting | Ruff (isort) | Built-in |
| Pre-commit hooks | Ruff | `.pre-commit-config.yaml` |

---

## What Carries Over

### From fastapi-nextjs (subset, reusable as-is)

- SQLAlchemy 2.0 async setup, `AuditBase`, `SoftDeleteMixin`
- Alembic migration setup
- Ruff configuration
- Docker Compose patterns (Postgres, Redis)
- Health check pattern
- pytest + httpx test setup

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for micro)

- API-key auth middleware (replaces session auth)
- API-key model and management endpoints
- Per-key scope system
- Optional monitoring UI (Jinja2)

---

## Build Order

### Phase 0: Scaffolding
- [ ] FastAPI app, uvicorn, health check
- [ ] SQLAlchemy 2.0 async, Alembic
- [ ] Docker Compose (api, postgres, redis optional)
- [ ] Ruff config, `pyproject.toml`

### Phase 1: Auth
- [ ] ApiKey model (hash, scopes, last_used_at)
- [ ] `require_api_key` middleware
- [ ] Key creation endpoint (returns raw key once)
- [ ] Optional scope checking

### Phase 2: Core API
- [ ] REST endpoints with Pydantic models
- [ ] `ApiResponse` wrapper pattern
- [ ] Input validation, error handling

### Phase 3: Infrastructure + Polish
- [ ] Optional monitoring UI (Jinja2)
- [ ] Rate limiting (slowapi)
- [ ] CI pipeline (lint, test, audit)
- [ ] README, CLAUDE.md
