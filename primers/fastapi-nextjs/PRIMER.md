# Boilerworks FastAPI + Next.js -- Primer

> Async-first Python API with a rich frontend. Choose this for teams that want
> Python's ecosystem without Django's weight -- lean, explicit, fast, with type
> hints and Pydantic everywhere.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-fastapi-nextjs`
**Sibling variant:** [fastapi-htmx](../fastapi-htmx/PRIMER.md)

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

- Python teams that want async-native performance without Django's implicit
  conventions -- explicit queries, explicit middleware, explicit everything.
- High-throughput API services where FastAPI's ASGI performance matters --
  real-time dashboards, webhook processors, high-concurrency workloads.
- Modern Python shops that live on type hints and Pydantic -- teams that want
  the compiler to catch mistakes before runtime.

### Not Ideal For

- Projects that need batteries-included admin, ORM migrations, and middleware
  out of the box -- choose [django-nextjs](../django-nextjs/PRIMER.md) instead.
- Teams more comfortable with Django's conventions and where explicit wiring
  feels like overhead rather than control.
- Admin-heavy applications that lean on Django Admin's custom widgets and
  built-in CRUD.

### vs fastapi-htmx

Choose fastapi-nextjs when you need rich client-side interactivity: dashboards
with charts, drag-and-drop builders, multi-step form wizards, or anything that
benefits from React's component model and client-side state.

Choose fastapi-htmx when server-rendered simplicity wins: content-heavy CRUD,
internal tools, admin-facing apps where a full SPA is overhead.

Both share the same FastAPI backend patterns. The difference is the frontend
delivery model.

### vs django-nextjs

Django is batteries-included: ORM with migrations, admin panel, built-in auth,
mature middleware ecosystem, more convention. You trade speed and explicitness
for productivity on well-worn paths.

FastAPI is lean: async-native, explicit, faster, more control, less convention.
You trade Django's batteries for transparency and performance. No ORM magic, no
middleware magic, no admin out of the box.

Both use the same Next.js frontend and Strawberry GraphQL. The backend is the
only difference.

---

## Architecture

```
Browser
  +-- Next.js 16 (shared frontend -- see NEXTJS_FRONTEND.md)
        +-- Apollo Client -> GraphQL API
              |
              v
        FastAPI (async Python, Pydantic validation)
              |-- Strawberry GraphQL (mounted on FastAPI)
              |-- Celery / ARQ (async jobs)
              |-- Postgres 16 (via SQLAlchemy 2.0 async)
              |-- Redis 7 (cache, sessions, broker)
              +-- MinIO (S3-compatible storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI (Python 3.12+) | Async-native, Pydantic validation, OpenAPI docs for free |
| Frontend | Next.js 16 | Shared frontend -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) |
| API | Strawberry GraphQL (or FastAPI REST/OpenAPI) | GraphQL for consistency with other stacks; REST is a valid alternative |
| ORM | SQLAlchemy 2.0 (async) | Explicit queries, async-native, full control over SQL |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Celery + Redis (or ARQ) | Celery for consistency; ARQ as a lighter async-native option |
| Auth | Session-based (httpOnly cookies) | Custom implementation, no Django auth dependency |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev) | Standard across all stacks |
| Migrations | Alembic | Manual but flexible -- pairs with SQLAlchemy |

**API layer note:** This primer documents Strawberry GraphQL as the primary API
layer for consistency with other Boilerworks stacks. FastAPI's native REST with
automatic OpenAPI documentation is a valid choice for teams that prefer REST.
Both are fully supported. If you go REST, the Next.js frontend uses `fetch` or
TanStack Query instead of Apollo.

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `AuditBase` mapped superclass | `created_at/by`, `updated_at/by` |
| Soft deletes | `SoftDeleteMixin` | `deleted_at/by`, query filter |
| External IDs (no integer PKs) | UUID primary key column | Never expose integer PKs |
| API contract | Strawberry GraphQL (or REST/OpenAPI) | GraphQL recommended for cross-stack consistency |
| MutationResult pattern | `MutationResult` Strawberry type | `ok` + `errors [{field, messages}]` |
| Auth (session-based) | Custom session model + middleware | httpOnly cookies, SHA256 token hashing |
| Permissions (group-based) | Custom Group/Permission models | FastAPI `Depends()` for permission checks |
| Background jobs | Celery + Redis (or ARQ) | Tasks in `app/tasks/` |
| Forms engine | Phase 2 | Same JSON Schema pattern as django-nextjs |
| Workflow engine | Phase 2 | Same state machine pattern as django-nextjs |
| Feature toggles | `app/core/features.py` | Env-based, gates router inclusion |
| Admin panel | SQLAdmin (optional) | Or skip it -- keep it lean |
| Testing framework | pytest + httpx AsyncClient | pytest-asyncio for async tests |
| Linter/Formatter | Ruff (lint + format) | Replaces flake8 + isort + black |
| Package manager | uv (or pip + pyproject.toml) | `pyproject.toml` + lockfile |
| Migrations | Alembic | `alembic revision --autogenerate` / `alembic upgrade head` |

---

## Pattern: Models & ORM

SQLAlchemy 2.0 with the new `Mapped` column syntax. All models use `mapped_column`
and type-annotated attributes. Async sessions throughout.

**AuditBase** -- audit trails for any model:

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

**SoftDeleteMixin** -- never call `session.delete()`:

```python
class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    @classmethod
    def active(cls):
        """Use as a filter: select(Model).where(Model.active())"""
        return cls.deleted_at.is_(None)
```

**Business model example:**

```python
from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column


class Product(AuditBase, SoftDeleteMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
```

UUID primary keys on every model. Never expose integer IDs. Use `slug` as the
natural key for URLs.

---

## Pattern: API Layer

Two supported options. Strawberry GraphQL is recommended for consistency with
other Boilerworks stacks. FastAPI REST/OpenAPI is a valid alternative.

### Option A: Strawberry GraphQL (recommended)

Strawberry mounted on FastAPI. Each domain has `types.py`, `queries.py`,
`mutations.py`. Schema assembled in `app/schema.py`.

**Types** -- mapped from SQLAlchemy models:

```python
import strawberry
from app.models.product import Product as ProductModel


@strawberry.type
class ProductType:
    id: strawberry.ID
    name: str
    slug: str
    description: str | None
    price: str
    created_at: str

    @classmethod
    def from_model(cls, product: ProductModel) -> "ProductType":
        return cls(
            id=strawberry.ID(str(product.id)),
            name=product.name,
            slug=product.slug,
            description=product.description,
            price=str(product.price),
            created_at=product.created_at.isoformat(),
        )
```

**Queries:**

```python
@strawberry.type
class Query:
    @strawberry.field
    async def products(self, info: strawberry.Info, search: str = "") -> list[ProductType]:
        user = info.context["user"]
        if not user:
            raise PermissionError("Authentication required")

        async with info.context["db"]() as session:
            stmt = select(Product).where(Product.active())
            if search:
                stmt = stmt.where(Product.name.ilike(f"%{search}%"))
            result = await session.execute(stmt)
            return [ProductType.from_model(p) for p in result.scalars()]
```

**Mutations** -- always return MutationResult:

```python
@strawberry.type
class FieldError:
    field: str
    messages: list[str]


@strawberry.type
class MutationResult:
    ok: bool
    errors: list[FieldError] | None = None


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_product(
        self, info: strawberry.Info, name: str, price: str
    ) -> MutationResult:
        user = info.context["user"]
        if not user:
            raise PermissionError("Authentication required")
        await check_permission(info.context["db"], user.id, "product.add")

        async with info.context["db"]() as session:
            product = Product(
                name=name,
                slug=slugify(name),
                price=Decimal(price),
                created_by=user.id,
            )
            session.add(product)
            await session.commit()
            return MutationResult(ok=True)
```

**Context** -- provided via FastAPI dependency injection:

```python
from strawberry.fastapi import GraphQLRouter


async def get_context(
    request: Request,
    db: AsyncSessionFactory = Depends(get_db),
):
    return {
        "request": request,
        "user": request.state.user,
        "db": db,
    }


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=get_context)

app.include_router(graphql_router, prefix="/graphql")
```

Auth check at the top of every resolver and mutation -- no exceptions.

### Option B: FastAPI REST/OpenAPI

Standard FastAPI routers with Pydantic models for request/response validation.
Auto-generated OpenAPI docs at `/docs`.

```python
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    price: str


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    price: str

    model_config = {"from_attributes": True}


@router.post("/products", response_model=MutationResult)
async def create_product(
    data: ProductCreate,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("product.add")),
):
    product = Product(name=data.name, slug=slugify(data.name), price=Decimal(data.price))
    db.add(product)
    await db.commit()
    return MutationResult(ok=True)
```

---

## Pattern: Auth

Custom session implementation. No Django, no third-party auth library. Session
tokens stored as SHA256 hashes in the database, raw token sent as httpOnly
cookie.

**Session model:**

```python
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**Session creation (login):**

```python
import hashlib
import secrets


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    session = Session(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.add(session)
    await db.commit()
    return raw_token


@router.post("/auth/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    raw_token = await create_session(db, user.id)
    response.set_cookie(
        key="session",
        value=raw_token,
        httponly=True,
        secure=True,       # False in dev
        samesite="lax",
        max_age=30 * 24 * 3600,
    )
    return {"ok": True}
```

**Auth middleware** -- populates `request.state.user`:

```python
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        token = request.cookies.get("session")
        if token:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            async with get_session() as db:
                stmt = (
                    select(Session)
                    .join(User)
                    .where(Session.token_hash == token_hash)
                    .where(Session.expires_at > func.now())
                )
                result = await db.execute(stmt)
                session = result.scalar_one_or_none()
                if session:
                    request.state.user = await db.get(User, session.user_id)
        return await call_next(request)
```

**Logout:**

```python
@router.post("/auth/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("session")
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stmt = delete(Session).where(Session.token_hash == token_hash)
        await db.execute(stmt)
        await db.commit()
    response.delete_cookie("session")
    return {"ok": True}
```

Server-side revocation is instant -- delete the session row.

---

## Pattern: Permissions

Group-based. Never user-based. No exceptions. Same conceptual model as
django-nextjs, implemented with SQLAlchemy and FastAPI dependency injection.

**Models:**

```python
class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))


class Group(AuditBase):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    permissions: Mapped[list[Permission]] = relationship(secondary="group_permissions")


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), primary_key=True)
```

**Permission checking utility:**

```python
async def check_permission(
    db_factory, user_id: uuid.UUID, permission_slug: str, raise_on_fail: bool = True
) -> bool:
    async with db_factory() as db:
        stmt = (
            select(Permission)
            .join(group_permissions)
            .join(Group)
            .join(UserGroup)
            .where(UserGroup.user_id == user_id)
            .where(Permission.slug == permission_slug)
        )
        result = await db.execute(stmt)
        has_perm = result.scalar_one_or_none() is not None

    if not has_perm and raise_on_fail:
        raise PermissionError(f"Missing permission: {permission_slug}")
    return has_perm
```

**FastAPI dependency for route-level checks:**

```python
def require_permission(permission_slug: str):
    async def dependency(
        request: Request,
        db: AsyncSessionFactory = Depends(get_db),
    ):
        if not request.state.user:
            raise HTTPException(status_code=401)
        await check_permission(db, request.state.user.id, permission_slug)

    return Depends(dependency)


# Usage in routes:
@router.get("/products")
async def list_products(
    user: User = Depends(require_auth),
    _: None = Depends(require_permission("product.view")),
    db: AsyncSession = Depends(get_db),
):
    ...
```

Assign permissions to groups. Assign users to groups. Never assign permissions
directly to users.

**Frontend guards:** Same as django-nextjs -- see
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Background Jobs

Two options. Celery is recommended for consistency with other Boilerworks
stacks. ARQ is a lighter async-native alternative.

### Option A: Celery + Redis (recommended)

Same pattern as django-nextjs. Tasks in `app/tasks/`.

```python
from app.worker import celery_app


@celery_app.task()
def process_invoice(invoice_id: str):
    import asyncio
    from app.db import async_session
    from app.models.invoice import Invoice

    async def _run():
        async with async_session() as db:
            invoice = await db.get(Invoice, invoice_id)
            await invoice.process()
            await db.commit()

    asyncio.run(_run())


@celery_app.task(bind=True, max_retries=3)
def send_notification(self, user_id: str):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

Note: Celery tasks are synchronous. Wrap async code in `asyncio.run()` or use
`asgiref.sync.async_to_sync`. Celery Beat with `DatabaseScheduler` for periodic
tasks. Flower at `localhost:5555` for monitoring.

### Option B: ARQ (async-native)

Lighter, async-native Redis queue. No wrapping needed -- tasks are native async
functions.

```python
from arq import create_pool
from arq.connections import RedisSettings


async def process_invoice(ctx, invoice_id: str):
    db = ctx["db"]
    invoice = await db.get(Invoice, invoice_id)
    await invoice.process()
    await db.commit()


class WorkerSettings:
    functions = [process_invoice]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    async def on_startup(ctx):
        ctx["db"] = async_session()
```

ARQ is simpler but less battle-tested than Celery and has no built-in
monitoring dashboard. Choose Celery unless you have a strong reason not to.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern as django-nextjs: `FormDefinition` model with
versioned JSON Schema (draft -> published -> archived), 21+ field types, logic
engine for conditional rules.

Backend implementation uses SQLAlchemy models instead of Django ORM. Frontend is
identical -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern as django-nextjs: JSON-defined states and
transitions, condition/action types, transition logging, async action execution
via job queue.

Backend implementation uses SQLAlchemy models and Celery/ARQ tasks. Frontend
WorkflowBuilder (ReactFlow) is identical.

---

## Pattern: Feature Toggles

```python
# app/core/features.py
from enum import Enum
from app.core.config import settings


class Feature(Enum):
    FORMS = "forms"
    WORKFLOWS = "workflows"
    ADMIN = "admin"

    @property
    def is_enabled(self) -> bool:
        return getattr(settings, f"FEATURE_{self.value.upper()}", False)


# Usage in router registration:
if Feature.FORMS.is_enabled:
    app.include_router(forms_router, prefix="/api/forms")

# Usage in Strawberry schema assembly:
if Feature.WORKFLOWS.is_enabled:
    schema_extensions.append(workflow_types)
```

When disabled, the router is not mounted, its Alembic migrations are skipped
(via branch labels), and its GraphQL types are not registered. Tied to Docker
Compose profiles for infrastructure dependencies.

---

## Pattern: Admin

Two options depending on project needs.

### Option A: SQLAdmin (lightweight admin)

SQLAdmin is built on SQLAlchemy and served via Starlette. Mount it on the
FastAPI app.

```python
from sqladmin import Admin, ModelView
from app.db import engine
from app.models.product import Product


admin = Admin(app, engine)


class ProductAdmin(ModelView, model=Product):
    column_list = [Product.name, Product.slug, Product.created_at]
    column_searchable_list = [Product.name]
    column_sortable_list = [Product.name, Product.created_at]


admin.add_view(ProductAdmin)
```

SQLAdmin provides basic CRUD, search, and sorting. It is not Django Admin --
no custom widgets, no import/export, no inline editing. Good enough for most
cases.

### Option B: No admin

Keep it lean. Use the GraphQL API or REST endpoints for all data management.
Build admin features into the Next.js frontend as needed.

---

## Pattern: Testing

pytest with httpx `AsyncClient` for API integration tests. Real Postgres
database, never mocked.

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db import async_session, Base, engine


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_client(client):
    """Client with a valid session cookie."""
    user = await create_test_user()
    session_token = await create_session(user.id)
    client.cookies.set("session", session_token)
    return client


@pytest.mark.asyncio
async def test_create_product(auth_client):
    # GraphQL test
    response = await auth_client.post("/graphql", json={
        "query": """
            mutation {
                createProduct(name: "Widget", price: "9.99") {
                    ok
                    errors { field messages }
                }
            }
        """
    })
    data = response.json()["data"]["createProduct"]
    assert data["ok"] is True
    assert data["errors"] is None

    # Verify database state
    async with async_session() as db:
        result = await db.execute(select(Product).where(Product.name == "Widget"))
        product = result.scalar_one()
        assert product.price == Decimal("9.99")


@pytest.mark.asyncio
async def test_create_product_denied(client):
    """Unauthenticated user cannot create products."""
    response = await client.post("/graphql", json={
        "query": """
            mutation {
                createProduct(name: "Widget", price: "9.99") {
                    ok errors { field messages }
                }
            }
        """
    })
    assert response.status_code == 200
    assert response.json().get("errors") is not None
```

**Rules:** Assert against database state, not hardcoded strings. No empty test
bodies. Test both allowed and denied permission cases. Integration tests via
API layer, not isolated model tests. Real database -- never mock.

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `api` (FastAPI + uvicorn) | 8000 | `GET /health` |
| Frontend | `ui` (Next.js) | 3000 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Celery Worker | Same image, different entrypoint | -- | -- |
| Flower | mher/flower | 5555 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No OpenSearch by default (add it when you need full-text search). Celery Beat
optional -- add when you need periodic tasks.

---

## Pattern: CI/CD

GitHub Actions pipeline. No Makefile -- use Taskfile or `pyproject.toml`
scripts.

- **Lint job:** Ruff (lint + format check) + Prettier (frontend)
- **Build job:** Docker build for API and frontend
- **Test job:** pytest with Postgres + Redis services
- **Audit job:** `pip-audit` for Python, `npm audit` for frontend

CI must pass before merge. Tests run against a real database.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens (raw to client, hash to DB).
httpOnly cookies, secure in prod, sameSite lax. 30-day expiry. CORS restricted
to explicit origin whitelist.

**Authorization:** Auth check at the top of every resolver/endpoint. Ownership
checks on mutations. Never trust client-provided IDs alone.

**Input validation:** Pydantic v2 at all API boundaries. Strawberry types
validated via Pydantic integration. Filename sanitization. MIME whitelist +
50MB size limit for uploads.

**SSRF protection:** URL validator on all outgoing requests. Block private IPs,
localhost, non-HTTP schemes.

**GraphQL hardening:** Max 10-level query depth. Introspection and GraphiQL
disabled in production. Masked error messages in production (no stack traces).

**Rate limiting:** slowapi (built on limits library) on auth endpoints and
sensitive mutations.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml [tool.ruff.format]` |
| Linting | Ruff (lint) | `pyproject.toml [tool.ruff.lint]` |
| Max line length | 120 characters | `pyproject.toml` |
| Import sorting | Ruff (isort rules) | Built into Ruff |
| Frontend formatting | Prettier | `.prettierrc` |
| Frontend linting | ESLint | `eslint.config.js` |
| Pre-commit hooks | Ruff + Prettier | `.pre-commit-config.yaml` |

Ruff replaces flake8, isort, and black in a single tool. Run `ruff check .`
and `ruff format .` before committing. Two blank lines between top-level
definitions. Type hints on all function signatures.

---

## What Carries Over

### Frontend (shared across all Next.js stacks)

The Next.js frontend is backend-agnostic. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) for the full reference. Carries
over as-is: `components/ui/`, `components/forms/`, `components/workflows/`,
`components/data-table/`, `hooks/`, `lib/apollo/`, `graphql/`, `app/(app)/`,
`messages/` (7 languages).

### From django-nextjs (same concept, reusable patterns)

- Strawberry GraphQL types, queries, mutations (same library, different ORM)
- Celery task patterns (identical)
- Docker Compose infrastructure (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- CI pipeline structure (lint, build, test, audit)
- Frontend permission guards and auth gate

### Shared infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs building (new implementation for this stack)

- SQLAlchemy 2.0 models with audit base classes (replaces Django ORM)
- Alembic migration setup (replaces Django migrations)
- Custom session auth (replaces Django auth)
- Custom permission system with FastAPI Depends (replaces Django permissions)
- Auth middleware for FastAPI (replaces Django middleware)
- SQLAdmin setup (replaces Django Admin)
- Strawberry-to-SQLAlchemy integration (replaces strawberry-django)
- Ruff configuration (replaces flake8 + isort)

---

## Build Order

### Phase 0: Scaffolding

- [ ] Project structure (`pyproject.toml`, `app/` package, `alembic/`)
- [ ] FastAPI app with uvicorn, health check endpoint
- [ ] SQLAlchemy 2.0 async engine + session factory
- [ ] Alembic migration setup
- [ ] Next.js frontend (copy from shared template)
- [ ] Docker Compose (api, ui, postgres, redis, minio, mailpit)
- [ ] Ruff + Prettier config

### Phase 1: Auth + Permissions

- [ ] User model (SQLAlchemy)
- [ ] Session model + token hashing
- [ ] Login/logout endpoints
- [ ] Auth middleware (populates request.state.user)
- [ ] Group, Permission, UserGroup models + seed data
- [ ] Permission checking utility
- [ ] `require_auth` and `require_permission` FastAPI dependencies
- [ ] Frontend auth gate (shared from NEXTJS_FRONTEND)

### Phase 2: Core API

- [ ] Strawberry GraphQL mounted on FastAPI
- [ ] Context getter with user, db session
- [ ] MutationResult type
- [ ] Example domain (Product) with types, queries, mutations
- [ ] Audit logging (created_by/updated_by populated via context)

### Phase 3: Forms Engine

- [ ] FormDefinition model (SQLAlchemy)
- [ ] Field types + validation (Pydantic)
- [ ] Logic engine (conditions, calculations)
- [ ] GraphQL CRUD (or REST endpoints)
- [ ] Frontend DynamicForm + FormBuilder (shared from NEXTJS_FRONTEND)

### Phase 4: Workflow Engine

- [ ] Workflow models (definition, instance, transition log) in SQLAlchemy
- [ ] State machine service
- [ ] Celery/ARQ action processors
- [ ] GraphQL CRUD + transition mutations
- [ ] Frontend WorkflowBuilder (shared from NEXTJS_FRONTEND)

### Phase 5: Infrastructure & Polish

- [ ] File uploads (MinIO/S3 via aiobotocore)
- [ ] Email service (aiosmtplib / Mailpit in dev)
- [ ] In-app notifications
- [ ] Feature toggles wired to router registration
- [ ] SQLAdmin setup (optional)
- [ ] Seed data + examples
- [ ] CLAUDE.md, bootstrap.md
- [ ] CI pipeline (GitHub Actions)
