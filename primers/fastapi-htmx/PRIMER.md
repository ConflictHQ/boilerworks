# Boilerworks FastAPI + HTMX -- Primer

> Lightweight async Python backend with HTMX, Alpine.js, and Jinja2 templates.
> Choose this for server-rendered Python apps that need FastAPI's performance
> without Django's weight. Lean, explicit, fast.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-fastapi-htmx`
**Sibling variant:** [fastapi-nextjs](../fastapi-nextjs/PRIMER.md)

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

- Python teams that want async-native performance with server-rendered
  simplicity -- no separate frontend build, no React, no GraphQL, just
  Jinja2 templates returning HTML.
- Internal tools, admin dashboards, and CRUD apps where HTMX provides all
  the dynamic behavior needed and a full SPA is overhead.
- Lightweight APIs that also serve a simple UI -- FastAPI's auto-generated
  OpenAPI docs plus a Jinja2 dashboard in the same app.

### Not Ideal For

- Apps needing rich client-side interactivity -- drag-and-drop, complex
  dashboards with charts, multi-step wizards. Choose
  [fastapi-nextjs](../fastapi-nextjs/PRIMER.md) instead.
- Projects that need batteries-included admin and ORM migrations out of the
  box. Choose [django-htmx](../django-htmx/PRIMER.md) instead.
- Teams that prefer Django's conventions over FastAPI's explicit wiring.

### vs fastapi-nextjs

Choose fastapi-htmx when server-rendered simplicity wins: CRUD apps, internal
tools, admin-facing dashboards where HTMX handles dynamic behavior and a full
SPA is overhead. No separate frontend build, no React, no Apollo.

Choose fastapi-nextjs when you need rich client-side interactivity: dashboards
with charts, drag-and-drop builders, form wizards, or anything that benefits
from React's component model.

Both share the same FastAPI backend patterns (SQLAlchemy 2.0, Pydantic,
async sessions, custom auth). The difference is the frontend delivery model.

---

## Architecture

```
Browser
  +-- Jinja2 templates + HTMX + Alpine.js + Tailwind CSS
        |
        v (standard HTTP requests + HTMX partial responses)
        |
  FastAPI (async Python, Pydantic validation)
        |-- Celery or ARQ (async jobs)
        |-- Postgres 16 (via SQLAlchemy 2.0 async)
        |-- Redis 7 (cache, sessions, broker)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI (Python 3.12+) | Async-native, Pydantic validation, explicit |
| Frontend | Jinja2 + HTMX + Alpine.js + Tailwind CSS | Server-rendered with progressive enhancement |
| API | HTMX partial responses | Views return HTML fragments for dynamic updates |
| ORM | SQLAlchemy 2.0 (async) | Same as fastapi-nextjs |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Celery + Redis (or ARQ) | Same as fastapi-nextjs |
| Auth | Custom session middleware | httpOnly cookies, SHA256 hashing |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `AuditBase` mapped superclass | Same as fastapi-nextjs |
| Soft deletes | `SoftDeleteMixin` | Same as fastapi-nextjs |
| External IDs (no integer PKs) | UUID primary keys | Same as fastapi-nextjs |
| API contract | FastAPI routes returning HTML | Full pages or HTMX partials |
| MutationResult pattern | Form validation errors | Rendered inline via HTMX swap |
| Auth (session-based) | Custom middleware | Same as fastapi-nextjs |
| Permissions (group-based) | Custom Group/Permission + `Depends()` | Same as fastapi-nextjs |
| Background jobs | Celery + Redis (or ARQ) | Same as fastapi-nextjs |
| Forms engine | Phase 2 | JSON Schema, Jinja2 rendering |
| Workflow engine | Phase 2 | State machine, same concept |
| Feature toggles | `app/core/features.py` | Same as fastapi-nextjs |
| Admin panel | SQLAdmin (optional) | Same as fastapi-nextjs |
| Testing framework | pytest + httpx | Integration tests |
| Linter/Formatter | Ruff | Same as fastapi-nextjs |
| Package manager | uv (or pip) | `pyproject.toml` |
| Migrations | Alembic | Same as fastapi-nextjs |

---

## Pattern: Models & ORM

Identical to fastapi-nextjs. SQLAlchemy 2.0 with `Mapped` column syntax,
`AuditBase` superclass, `SoftDeleteMixin`. UUID primary keys.

```python
class Product(AuditBase, SoftDeleteMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
```

---

## Pattern: API Layer

No GraphQL. No REST serializers. FastAPI routes return HTML via Jinja2 --
full pages for initial loads, HTMX partials for dynamic updates.

```python
from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


@router.get("/products", response_class=HTMLResponse)
async def product_list(
    request: Request,
    search: str = "",
    user: User = Depends(require_auth),
    _: None = Depends(require_permission("product.view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.active())
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    result = await db.execute(stmt)
    products = result.scalars().all()

    # HTMX request -- return partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "products/partials/product_table.html",
            {"request": request, "products": products},
        )

    return templates.TemplateResponse(
        "products/product_list.html",
        {"request": request, "products": products, "search": search},
    )
```

**Jinja2 template with HTMX:**

```html
<!-- templates/products/product_list.html -->
{% extends "base.html" %}
{% block content %}
<div class="max-w-6xl mx-auto px-4 py-8">
  <input type="search" name="search" value="{{ search }}"
         placeholder="Search..."
         hx-get="/products" hx-trigger="input changed delay:300ms"
         hx-target="#product-table" hx-swap="outerHTML" />

  <div id="product-table">
    {% include "products/partials/product_table.html" %}
  </div>
</div>
{% endblock %}
```

**Alpine.js for client-side state** (dropdowns, modals, toggles) -- same
patterns as django-htmx.

---

## Pattern: Auth

Identical to fastapi-nextjs. Custom session model, SHA256-hashed tokens,
httpOnly cookies, auth middleware populating `request.state.user`.

Frontend: `require_auth` dependency redirects to login page for HTML routes.

---

## Pattern: Permissions

Identical to fastapi-nextjs. Group-based RBAC with `require_permission()`
FastAPI dependency.

**Template guards:**

```html
{% if user_can("product.create") %}
  <a href="/products/new">New Product</a>
{% endif %}
```

Custom Jinja2 global function for permission checks in templates.

---

## Pattern: Background Jobs

Identical to fastapi-nextjs. Celery + Redis (or ARQ). Tasks in `app/tasks/`.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Jinja2 template macros render form fields
from JSON Schema definitions. HTMX handles form submission and inline error
rendering.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. SQLAlchemy models, Celery/ARQ for async
actions. Jinja2 templates display workflow state with HTMX for transitions.

---

## Pattern: Feature Toggles

Identical to fastapi-nextjs. `app/core/features.py` with env vars.
Conditional router inclusion.

---

## Pattern: Admin

SQLAdmin mounted on the FastAPI app. Same as fastapi-nextjs. Or skip it
and manage data via the application UI.

---

## Pattern: Testing

pytest with httpx client. Test against HTML responses and database state.
Real Postgres.

```python
@pytest.mark.asyncio
async def test_product_list(auth_client):
    # Create test data
    async with async_session() as db:
        db.add(Product(name="Widget", slug="widget", price=Decimal("9.99")))
        await db.commit()

    response = await auth_client.get("/products")
    assert response.status_code == 200
    assert "Widget" in response.text


@pytest.mark.asyncio
async def test_product_list_htmx(auth_client):
    response = await auth_client.get(
        "/products", headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    # Verify it returns partial, not full page
    assert "<html" not in response.text


@pytest.mark.asyncio
async def test_product_list_denied(client):
    response = await client.get("/products")
    assert response.status_code in (302, 401)  # Redirect to login or 401
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via HTTP endpoints, not isolated function tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `app` (FastAPI + uvicorn) | 8000 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Celery Worker | Same image, different entrypoint | -- | -- |
| Flower | mher/flower | 5555 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No separate frontend container. FastAPI serves templates, static files
(Tailwind via standalone CLI), and HTMX partials. One fewer service than
fastapi-nextjs.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Ruff (lint + format check)
- **Build job:** Docker build
- **Test job:** pytest with Postgres + Redis services
- **Audit job:** `pip-audit`

CI must pass before merge.

---

## Pattern: Security

Identical to fastapi-nextjs for the backend. Session hardening, permission
checks, Pydantic validation, SSRF protection.

**CSRF protection:** Custom CSRF middleware for form submissions. HTMX
requests include CSRF token via `hx-headers` or `htmx:configRequest`.

**Same-origin advantage:** Since frontend and backend are the same service,
CORS is not needed.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml` |
| Linting | Ruff (lint) | `pyproject.toml` |
| Max line length | 120 characters | `pyproject.toml` |
| Import sorting | Ruff (isort rules) | Built into Ruff |
| CSS | Tailwind CSS | `tailwind.config.js` (standalone CLI) |
| Pre-commit hooks | Ruff | `.pre-commit-config.yaml` |

---

## What Carries Over

### From fastapi-nextjs (reusable as-is)

All FastAPI backend code carries over unchanged:
- SQLAlchemy 2.0 models (`AuditBase`, `SoftDeleteMixin`)
- Custom session auth middleware
- Permission system (`require_auth`, `require_permission`)
- Celery/ARQ task patterns
- Alembic migrations
- Feature toggle configuration
- Ruff configuration

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new implementation)

- Jinja2 templates with Tailwind CSS (replace React components)
- HTMX partial response pattern (replace GraphQL/REST API)
- Alpine.js patterns for client-side interactivity
- CSRF middleware for form submissions
- Jinja2 template macros for forms engine
- Tailwind CSS build via standalone CLI

---

## Build Order

### Phase 0: Scaffolding
- [ ] FastAPI app with uvicorn, Jinja2 templates
- [ ] SQLAlchemy 2.0 async (from fastapi-nextjs), Alembic
- [ ] Tailwind CSS (standalone CLI), HTMX + Alpine.js
- [ ] Docker Compose (app, postgres, redis, minio, mailpit)
- [ ] Health check, Ruff config

### Phase 1: Auth + Permissions
- [ ] Session auth middleware (from fastapi-nextjs)
- [ ] Login/logout views with Jinja2 templates
- [ ] Permission system (from fastapi-nextjs)
- [ ] Template permission guards (Jinja2 globals)

### Phase 2: Core Views
- [ ] CRUD routes returning HTML (list, detail, create, edit)
- [ ] HTMX partial response pattern
- [ ] Base templates with Tailwind layout
- [ ] Form validation + inline error rendering
- [ ] CSRF middleware, Alpine.js patterns

### Phase 3: Forms Engine
- [ ] FormDefinition model (from fastapi-nextjs)
- [ ] Jinja2 macros for dynamic form rendering
- [ ] HTMX form submission + validation

### Phase 4: Workflow Engine
- [ ] Workflow models (from fastapi-nextjs)
- [ ] State machine service, Celery/ARQ actions
- [ ] Jinja2 workflow display + HTMX transitions

### Phase 5: Infrastructure + Polish
- [ ] File uploads (MinIO), email
- [ ] Feature toggles, SQLAdmin (optional)
- [ ] Seed data, CI pipeline, README, CLAUDE.md
