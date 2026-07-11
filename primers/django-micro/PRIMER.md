# Boilerworks Django Micro -- Primer

> Lightweight Django microservice with API-key auth. No user-facing frontend, no
> sessions, no login flows. Choose this for internal APIs and microservices that
> need Django's ORM and ecosystem without the full application scaffolding.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-django-micro`
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

- Internal APIs and microservices that need Django's ORM, migration system,
  and admin panel but authenticate via API keys rather than user sessions.
- Teams with existing Django expertise who want to build microservices that
  integrate with their Django-based infrastructure.
- Services that benefit from Django's batteries (admin, ORM, management
  commands) but do not need session auth or a user-facing frontend.

### Not Ideal For

- Applications with user accounts, login flows, or a frontend. Choose
  [django-nextjs](../django-nextjs/PRIMER.md) or
  [django-htmx](../django-htmx/PRIMER.md) instead.
- Teams that want minimal overhead. Django's startup and dependency footprint
  is heavier than FastAPI or Go. Choose
  [fastapi-micro](../fastapi-micro/PRIMER.md) for leaner Python, or
  [go-micro](../go-micro/PRIMER.md) for minimal footprint.
- Simple webhook receivers that do not need an ORM at all.

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
Django 5 (DRF or Django Ninja)
  |-- Django ORM (Postgres)
  |-- Redis 7 (cache, optional)
  +-- Django Admin (for key management)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Django 5 | ORM, migrations, admin, management commands |
| API | DRF (Django REST Framework) or Django Ninja | DRF for mature ecosystem; Ninja for Pydantic-style |
| ORM | Django ORM | Mature, migration system, admin integration |
| Database | Postgres 16 | Standard across all stacks |
| Cache | Redis 7 (optional) | Only if caching is needed |
| Auth | API-key middleware | SHA256-hashed keys, no sessions |
| Admin | Django Admin | API key management, data inspection |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `TimeStampedModel` abstract | `created_at`, `updated_at` (no `by` fields) |
| Soft deletes | `SoftDeleteMixin` | `deleted_at` field |
| External IDs (no integer PKs) | UUID `guid` field | Never expose integer PKs |
| API contract | DRF serializers or Ninja schemas | JSON REST API |
| MutationResult pattern | `ApiResponse` wrapper | `{ok, data, errors}` |
| Auth | API-key middleware | No sessions, no User model beyond service accounts |
| Permissions | Key-level scopes | Per-key permission scopes |
| Background jobs | Celery (optional) | Add only when needed |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars | Simple checks in settings |
| Admin panel | Django Admin | Built-in, for key management |
| Testing framework | pytest-django | Real database |
| Linter/Formatter | Ruff | Replaces flake8 + isort |
| Package manager | uv or Pipenv | `pyproject.toml` or `Pipfile` |
| Migrations | Django migrations | `python manage.py migrate` |

---

## Pattern: Models & ORM

Django ORM with simplified base model. No `created_by`/`updated_by` since
there are no user accounts.

```python
class TimeStampedModel(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
```

Business models inherit from `TimeStampedModel` with optional
`SoftDeleteMixin`. Use `guid` in API responses, never integer PKs.

---

## Pattern: API Layer

DRF (mature, widely known) or Django Ninja (Pydantic-style, FastAPI feel).

**DRF approach:**

```python
class WebhookSerializer(serializers.Serializer):
    event = serializers.CharField()
    data = serializers.JSONField()


class WebhookView(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request):
        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Process webhook...
        return Response({"ok": True, "message": "Processed"})
```

**Django Ninja approach:**

```python
from ninja import NinjaAPI, Schema

api = NinjaAPI()

class WebhookPayload(Schema):
    event: str
    data: dict

@api.post("/webhooks")
def receive_webhook(request, payload: WebhookPayload):
    # Process webhook...
    return {"ok": True, "message": "Processed"}
```

---

## Pattern: Auth

API-key middleware. Keys stored as SHA256 hashes. Compatible with DRF's
authentication classes or Django middleware.

```python
class ApiKey(TimeStampedModel):
    name = models.CharField(max_length=255)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.META.get("HTTP_X_API_KEY")
        if not key:
            return None

        key_hash = hashlib.sha256(key.encode()).hexdigest()
        try:
            api_key = ApiKey.objects.get(key_hash=key_hash, is_active=True)
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])
        return (api_key, None)
```

---

## Pattern: Permissions

Optional per-key scopes. DRF permission class checks scopes.

```python
class HasScope(BasePermission):
    def __init__(self, scope):
        self.scope = scope

    def has_permission(self, request, view):
        api_key = request.auth  # None if no key, ApiKey if authenticated
        if not api_key:
            return False
        return self.scope in api_key.scopes or "*" in api_key.scopes
```

---

## Pattern: Background Jobs

Not included by default. Add Celery only when async processing is needed.
For simple cases, Django management commands with cron suffice.

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Simple env var checks in `settings.py`.

```python
FEATURE_ADMIN = env.bool("FEATURE_ADMIN", default=True)

if FEATURE_ADMIN:
    INSTALLED_APPS += ["django.contrib.admin"]
```

---

## Pattern: Admin

Django Admin for API key management and data inspection. One of the main
advantages of choosing Django for a microservice.

```python
@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active",)
    readonly_fields = ("key_hash", "last_used_at", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new key
            raw_key = secrets.token_urlsafe(32)
            obj.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            super().save_model(request, obj, form, change)
            messages.info(request, f"API Key (copy now, shown once): {raw_key}")
        else:
            super().save_model(request, obj, form, change)
```

Admin is auth-gated with a separate superuser account (not an API key).

---

## Pattern: Testing

pytest-django with real Postgres. Test with API key headers.

```python
@pytest.fixture
def api_key(db):
    raw_key = "test-key-123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return ApiKey.objects.create(name="test", key_hash=key_hash, scopes=["*"])


@pytest.fixture
def api_client(api_key):
    client = APIClient()
    client.credentials(HTTP_X_API_KEY="test-key-123")
    return client


def test_webhook(api_client):
    response = api_client.post(
        "/api/webhooks/",
        {"event": "order.created", "data": {"id": "123"}},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_webhook_no_key(client):
    response = client.post(
        "/api/webhooks/",
        {"event": "order.created", "data": {"id": "123"}},
        content_type="application/json",
    )
    assert response.status_code == 401
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both valid and invalid API key cases
- Integration tests via API endpoints
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| API | `api` (Django + Gunicorn) | 8000 | `GET /health/` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine (optional) | 6379 | redis-cli ping |

Minimal. Django Admin accessible at `/admin/` on the same service.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Ruff
- **Build job:** Docker build
- **Test job:** pytest-django with Postgres service
- **Audit job:** `pip-audit`

---

## Pattern: Security

**API key hashing:** SHA256 before storage. Never store plaintext.

**Rate limiting:** django-ratelimit on endpoints.

**Input validation:** DRF serializers or Ninja schemas at API boundaries.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default. Enable only if needed.

**Admin protection:** Django Admin behind separate superuser auth. Not
exposed via API keys.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml` |
| Linting | Ruff (lint) | `pyproject.toml` |
| Max line length | 120 characters | `pyproject.toml` |
| Import sorting | Ruff (isort) | Built-in |

---

## What Carries Over

### From django-nextjs (subset, reusable patterns)

- Django ORM patterns, migration system
- Django Admin configuration
- Docker Compose pattern (Postgres, Redis)
- Health check pattern
- pytest-django test setup

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for micro)

- API-key auth middleware (replaces session auth)
- ApiKey model and admin registration
- Simplified base model (no user references)
- Per-key scope system

---

## Build Order

### Phase 0: Scaffolding
- [ ] Django 5 project with DRF or Ninja
- [ ] Docker Compose (api, postgres, redis optional)
- [ ] Health check, Ruff config

### Phase 1: Auth
- [ ] ApiKey model (hash, scopes, last_used_at)
- [ ] API-key authentication class
- [ ] Django Admin for key management
- [ ] Key creation (show raw key once)

### Phase 2: Core API
- [ ] REST endpoints with serializers/schemas
- [ ] `ApiResponse` wrapper pattern
- [ ] Input validation, error handling

### Phase 3: Infrastructure + Polish
- [ ] Rate limiting
- [ ] CI pipeline (lint, test, audit)
- [ ] README, CLAUDE.md
