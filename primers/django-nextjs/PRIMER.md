# Boilerworks Django + Next.js -- Primer

> The reference implementation and flagship template. Full-stack Django backend
> with a Next.js SPA frontend, connected by Strawberry GraphQL. Choose this for
> data-heavy backends, admin-rich apps, dashboards, and rapid prototyping.

**Status:** Done
**Repo:** `ConflictHQ/boilerworks-django-nextjs`
**Sibling variant:** [django-htmx](../django-htmx/PRIMER.md)

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

- Data-heavy backends where Django's ORM, admin, and migrations shine --
  multi-model domains, complex queries, reporting dashboards.
- Admin-rich applications that benefit from Django Admin with custom widgets
  (form builder, workflow editor, JSON editor) out of the box.
- SPAs that need rich client-side interactivity -- drag-and-drop builders,
  real-time form previews, ReactFlow workflow canvases.

### Not Ideal For

- Simple CRUD that does not need a full SPA -- the Next.js layer adds
  complexity that may not pay for itself.
- Projects where you want minimal JavaScript -- server-rendered HTML with
  progressive enhancement is better served by django-htmx.

### vs django-htmx

Choose django-nextjs when you need rich client-side interactivity: dashboards
with charts, drag-and-drop builders, multi-step form wizards, or any feature
that benefits from React's component model and client-side state.

Choose django-htmx when server-rendered simplicity wins: content-heavy CRUD,
admin-facing tools, internal apps where a full SPA is overhead.

Both share the same Django backend patterns. The difference is the frontend
delivery model.

---

## Architecture

```
Browser
  +-- Next.js 16 (App Router, React 19, TypeScript)
        |-- Server Components: data fetching, auth gates
        |-- Client Components: forms, builders, real-time
        +-- Apollo Client: GraphQL queries/mutations
              |
              v
        GraphQL API (Strawberry)
              |
              v
        Django 5 (ORM, Business Logic, Permissions)
              |-- Celery (async tasks)
              |-- Postgres 16 (data)
              |-- Redis 7 (cache, sessions, broker)
              |-- OpenSearch 2 (full-text search)
              +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Django 5 | Unmatched for data-heavy backends: ORM, admin, migrations, permissions |
| Frontend | Next.js 16 | Modern React with App Router, Server Components, streaming |
| API | Strawberry GraphQL | Python-native type hints and async; no over-fetching, introspectable schema |
| ORM | Django ORM | Mature, battle-tested, excellent migration system |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Celery + Redis | Fire-and-forget tasks; simple, battle-tested |
| Auth | Session-based (httpOnly cookies) | Immune to XSS token theft, instant server-side revocation |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), django-ses (prod) | Standard across all stacks |
| Search | OpenSearch 2 | Full-text search with signal-based incremental indexing |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `Tracking` abstract model | `version`, `created_at/by`, `updated_at/by`, `deleted_at/by`, `history` |
| Soft deletes | `deleted_at`/`deleted_by` on `Tracking` | Never call `.delete()` |
| External IDs | `guid` UUID on `BaseCoreModel` | Never expose integer PKs |
| API contract | Strawberry GraphQL | Schema in `config/schema.py` |
| MutationResult | `core.schema.common.MutationResult` | `ok` + `errors [{field, messages}]` |
| Auth (session-based) | `auth1` app | Django sessions, httpOnly cookies |
| Permissions (group-based) | `config/permissions.py` + `roles_gen.py` | `P.PERMISSION.check(user)` |
| Background jobs | Celery + Redis | Tasks in `appname/tasks.py` |
| Forms engine | `forms` app + `FormDefinition` | JSON Schema, 21+ field types |
| Workflow engine | State machine + Celery actions | JSON states/transitions, GenericForeignKey |
| Feature toggles | `config/features.py` + django-constance | Env-based + admin UI |
| Admin panel | Django Admin + `BaseCoreAdmin` | Custom widgets, import/export, dark theme |
| Testing | `schema.execute_sync()` | GraphQL integration tests |
| Linter/Formatter | Ruff (lint + format) | Replaces flake8 + isort + black |
| Package manager | uv (preferred), Pipenv as fallback | `uv.lock` or `Pipfile.lock` |
| Migrations | Django migrations | `make migrations` / `make migrate` |

---

## Pattern: Models & ORM

All business models inherit from one of two abstract base classes.

**Tracking** -- audit trails for any model:
```python
from core.models import Tracking

class Invoice(Tracking):
    amount = models.DecimalField(...)
```
Provides: `version` (auto-increments on save), `created_at/by`, `updated_at/by`,
`deleted_at/by`, `history` (simple_history).

**BaseCoreModel(Tracking)** -- named, addressable entities:
```python
from core.models import BaseCoreModel

class Product(BaseCoreModel):
    price = models.DecimalField(...)
```
Adds: `guid` (UUID external ID), `name`, `slug` (auto-generated, unique),
`description`. Use `slug` as the natural key. Never expose integer PKs --
use `guid` or the relay global ID.

**Soft deletes:** Always set `deleted_at`/`deleted_by`. Never call `.delete()`.

---

## Pattern: API Layer

Strawberry GraphQL with Django integration. Each app has
`appname/schema/{types,queries,mutations,__init__}.py`. Schema assembled in
`config/schema.py`. Endpoints: `/gql/config/` (main), `/gql/config/auth/`.

**Types** -- auto-mapped from Django models:
```python
@strawberry_django.type(Product)
class ProductType:
    @classmethod
    def get_queryset(cls, queryset, info: Info):
        return permission_filtered_queryset(queryset, info)
```

**Queries:**
```python
@strawberry.type
class Query:
    @strawberry.field
    def products(self, info: Info, search: str = '') -> list[ProductType]:
        if not info.context.user.is_authenticated:
            raise GraphQLError('Authentication required')
        qs = Product.objects.all()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs
```

**Mutations** -- always return MutationResult:
```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_product(self, info: Info, name: str, price: str) -> MutationResult:
        Product.p('model').add.check(info.context.user)
        return restricted_serializer_mutate(
            ProductSerializer, Product, info,
            data={'name': name, 'price': price},
        )
```

**Context** (`StrawberryContext` from `core/schema/context.py`):
```python
info.context.user                    # authenticated user
info.context.organization            # user's active org
info.context.request_language        # preferred language
info.context.request_timezone        # user timezone or SYSTEM_TIME_ZONE
info.context.check_permission(...)   # cached permission check
info.context.get_loader(name, fn)    # get/create dataloader
```

**Dataloaders:** Async batch loaders in `core/schema/dataloaders.py` using
`sync_to_async`. Use for all N+1 scenarios.

Auth check at the top of every resolver and mutation -- no exceptions.

---

## Pattern: Auth

Session-based authentication via the `auth1` app.

- Sessions stored server-side (database-backed), token as httpOnly cookie.
- Server-side revocation is instant (no JWT expiry wait).
- Rate limiting on auth endpoints via django-ratelimit.
- JWT used only as transport token between Next.js and Django, not as session.

Frontend: `(app)/layout.tsx` checks session. `UNAUTHENTICATED` GraphQL error
triggers Apollo error link redirect to login page.

---

## Pattern: Permissions

Group-based. Never user-based. No exceptions.

**Defining:** `config/permissions.py` with `ModelPermissions`. Generated enum
in `config/roles_gen.py` (regenerate: `make perms`).
```python
class ProductPermissions(ModelPermissions):
    model = FieldPermissions(
        view=P.PRODUCT_VIEW, add=P.PRODUCT_ADD,
        change=P.PRODUCT_CHANGE, delete=P.PRODUCT_DELETE,
    )
```

**Checking:**
```python
P.PRODUCT_VIEW.check(info.context.user)          # raises if denied
P.PRODUCT_CHANGE.check(info.context.user, False)  # returns False if denied
```

Assign to groups in admin, never directly to users.

**Frontend guards:**
```typescript
// Server Component
await requirePermission(PermissionSlug.ProductView);

// Client Component
<PermissionGuard permission={PermissionSlug.ProductView}>
  <ProductList />
</PermissionGuard>
```

---

## Pattern: Background Jobs

Celery with Redis broker. Tasks in `appname/tasks.py`. Import models inside
the function to avoid circular imports.

```python
from config.celery import app

@app.task()
def process_invoice(invoice_id):
    from invoicing.models import Invoice
    invoice = Invoice.objects.get(id=invoice_id)
    invoice.process()

@app.task(bind=True, max_retries=3)
def send_notification(self, user_id):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

Celery Beat with `DatabaseScheduler` for periodic tasks, managed via admin.
Flower at `localhost:5555` for monitoring.

---

## Pattern: Forms Engine

JSON Schema definitions rendered at runtime. No code changes to add a form.

**Backend:** `FormDefinition` model with versioned JSON Schema (draft ->
published -> archived). `field_types.py` defines 21+ built-in types. Logic
engine evaluates conditional rules (show/hide/require/calculate).

**Frontend:** `DynamicForm` + `field-registry.tsx` + React Hook Form. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) for frontend details.

**Visual builders:**
- Django admin: `FormBuilderWidget` (vanilla JS, drag-and-drop, JSON toggle)
- Next.js: `FormBuilder` (@dnd-kit, live preview, per-type config panels)

**Adding a field type:**
1. `backend/forms/field_types.py` -- add to `FIELD_TYPES` dict
2. `frontend/components/forms/field-registry.tsx` -- add widget component
3. `backend/core/static/admin/js/form_builder.js` -- add to type picker
4. `frontend/components/forms/FormBuilder.tsx` -- add config panel

---

## Pattern: Workflow Engine

JSON-defined state machines attached to any model via GenericForeignKey.

**State:** `{name, label, is_initial, is_final, color, form_slug?, assigned_role?}`
**Transition:** `{from_state, to_state, label, conditions[], actions[]}`

**Condition types:** `user_has_role`, `field_equals`, `field_in`,
`is_authenticated`, `is_superuser`
**Action types:** `notify_user`, `send_email`, `call_webhook`, `update_field`

**Visual builders:**
- Django admin: `WorkflowStatesWidget` + `WorkflowTransitionsWidget`
- Next.js: `WorkflowBuilder` (ReactFlow, conditions/actions editors, TagInput)

Celery tasks execute async actions. Transition logging provides an immutable
audit trail. Temporal integration scaffolded but not yet wired.

---

## Pattern: Feature Toggles

```python
# config/features.py
class Feature(Enum):
    FORMS = "forms"
    WORKFLOWS = "workflows"
    TEMPORAL = "temporal"

# Enabled via env: FEATURE_FORMS=true
# Usage: if Feature.FORMS.is_enabled: INSTALLED_APPS += ["forms"]
# Tied to Docker Compose profiles
```

When disabled, the app is not in `INSTALLED_APPS`, its migrations do not run,
and its GraphQL types are not registered. Runtime toggles via django-constance
admin UI.

---

## Pattern: Admin

Django Admin with custom dark theme. All admin classes inherit `BaseCoreAdmin`.

```python
@admin.register(Product)
class ProductAdmin(BaseCoreAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    formfield_overrides = {models.JSONField: {'widget': JSONEditorWidget}}
```

**BaseCoreAdmin provides:** auto `created_by`/`updated_by`/`deleted_by` as raw
ID fields, audit fields as readonly, `save_model` sets created/updated by,
`ImportExportMixin` for CSV import/export on all models.

**Custom widgets:** `JSONEditorWidget` (JSON format/validate),
`FormBuilderWidget` (visual form editor), `WorkflowStatesWidget` +
`WorkflowTransitionsWidget` (visual workflow editor).

---

## Pattern: Testing

GraphQL integration tests via `schema.execute_sync()`. Real database, not mocks.

```python
class ProductTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='TestOrg')
        self.user = User.objects.create_superuser(
            username='test', email='t@t.com', password='x')
        OrganizationMember.objects.create(
            organization=self.org, member=self.user, is_active=True)
        self.user.profile.active_organization = self.org
        self.user.profile.save()

    def _context(self):
        request = MagicMock()
        request.user = self.user
        request.session = {}
        request.headers = {}
        return StrawberryContext(request)

    def test_create_product(self):
        result = schema.execute_sync(
            'mutation { createProduct(name: "Widget", price: "9.99") '
            '{ ok errors { field messages } } }',
            context_value=self._context(),
        )
        self.assertIsNone(result.errors)
        self.assertTrue(result.data['createProduct']['ok'])
```

**Rules:** Assert against database state, not hardcoded strings. No empty test
bodies. Test both allowed and denied permission cases. Integration tests via
GraphQL, not isolated model tests. Real database -- never mock.

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `boilerworks-local` (Django + Gunicorn) | 8000 | `/health/` |
| Frontend | `ui` (Next.js) | 3000 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Celery Worker | Same image, different entrypoint | -- | -- |
| Celery Beat | Same image, different entrypoint | -- | -- |
| Flower | mher/flower | 5555 | -- |
| OpenSearch | opensearch:2 | 9200 | HTTP check |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |
| Postgres Exporter | wrouesnel/postgres_exporter | 9187 | -- |
| Redis Exporter | oliver006/redis_exporter | 9121 | -- |

See `bootstrap.md` for full local URLs and `make` commands.

---

## Pattern: CI/CD

`Makefile` targets: `make lint`, `make test`, `make build`. GitHub Actions runs
lint (Ruff via pre-commit) and test (with Postgres + Redis services).
CI must pass before merge. Tests run against a real database with seed data.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens (raw to client, hash to DB). API
keys also hashed. httpOnly cookies, secure in prod, sameSite lax. 30-day
expiry. CORS restricted to explicit origin whitelist. Rate limiting on auth
endpoints.

**Authorization:** Auth check at the top of every resolver/mutation. Ownership
checks on mutations. Never trust client-provided IDs alone.

**Input validation:** Pydantic/DRF at API boundaries. Ajv for forms payloads.
Filename sanitization. MIME whitelist + 50MB size limit for uploads.

**SSRF protection:** URL validator on all outgoing requests. Block private IPs,
localhost, non-HTTP schemes.

**GraphQL hardening:** Max 10-level depth. Introspection, GraphiQL, and stack
traces disabled in production.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml` |
| Linting | Ruff (check) | `pyproject.toml` |
| Max line length | 140 characters | `pyproject.toml` |
| Import sorting | Ruff (isort rules) | Built into Ruff |
| Pre-commit hooks | Ruff | `.pre-commit-config.yaml` |
| Package manager | uv (preferred) | `uv.lock` |

Run `make lint` before committing. Two blank lines between top-level
definitions. Docstrings only where logic is not self-evident.

---

## What Carries Over

### Frontend (shared across all Next.js stacks)

The Next.js frontend is backend-agnostic. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) for the full reference. Carries
over as-is: `components/ui/`, `components/forms/`, `components/workflows/`,
`components/data-table/`, `hooks/`, `lib/apollo/`, `graphql/`, `app/(app)/`,
`messages/` (7 languages).

### Django backend patterns (shared with sibling stacks)

Carry over to django-htmx and saleor-nextjs: `Tracking`/`BaseCoreModel` base
classes, `config/permissions.py`, `BaseCoreAdmin` + widgets, Celery patterns,
feature toggles, Docker Compose infra, health checks, CI pipeline.

### Shared infrastructure (identical across all stacks)

Docker Compose (Postgres, Redis, MinIO, Mailpit), health checks, feature
toggle pattern, `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
`LICENSE`.

### Needs porting (same concept, new implementation)

For non-Django stacks: ORM + migrations, GraphQL schema, permission middleware,
job queue, session management, admin panel.

---

## Build Order

This stack is **Done**. All phases complete.

- **Phase 0 -- Scaffolding:** Django + Strawberry, Next.js + Apollo, Docker
  Compose, health checks.
- **Phase 1 -- Auth + Permissions:** auth1 session auth, resolver middleware,
  User/Group/Permission models, `config/permissions.py`, frontend auth gate.
- **Phase 2 -- Core API:** Strawberry + Django ORM, StrawberryContext,
  MutationResult, simple_history audit logging.
- **Phase 3 -- Forms Engine:** FormDefinition model, 21+ field types, logic
  engine, GraphQL CRUD, DynamicForm + FormBuilder frontend.
- **Phase 4 -- Workflow Engine:** State machine model, Celery action
  processors, GraphQL CRUD, WorkflowBuilder (ReactFlow), admin widgets.
- **Phase 5 -- Infrastructure:** File uploads (MinIO/S3), email (ses/Mailpit),
  push notifications, feature toggles, OpenSearch, seed data, CI, agent shims.
