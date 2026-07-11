# Boilerworks CherryPy Micro -- Primer

> Pure Python microservice with CherryPy's built-in HTTP server. Object-oriented
> URL dispatch -- classes map to URL paths. Fun, simple, Pythonic. Choose this for
> lightweight internal services where CherryPy's simplicity and zero-WSGI-overhead
> architecture fits perfectly.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-cherrypy-micro`
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

- Lightweight internal services where CherryPy's simplicity is the feature --
  object-oriented URL dispatch, built-in HTTP server, no external WSGI server
  needed, batteries-included for the basics.
- Teams that value Pythonic elegance and want a framework where a class is a
  URL tree and a method is an endpoint. No decorators, no magic -- just Python.
- Services that need to serve both an API and a simple UI from the same
  process -- CherryPy serves static files and Jinja2 templates natively.

### Not Ideal For

- High-concurrency async workloads. CherryPy uses thread-based concurrency,
  not async/await. Choose [fastapi-micro](../fastapi-micro/PRIMER.md) for async.
- Projects where a large ecosystem of middleware and third-party packages
  matters. CherryPy's ecosystem is small but focused.
- Teams unfamiliar with CherryPy who would need to learn its (admittedly
  small) API. FastAPI or Django have more community resources.

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
CherryPy (built-in HTTP server, threaded)
  |-- SQLAlchemy or raw SQL (Postgres)
  |-- Optional: Jinja2 templates for lightweight UI
  +-- Health check at /health
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | CherryPy 18+ (Python 3.12+) | Built-in HTTP server, OO dispatch, Pythonic |
| API | REST (CherryPy exposed methods) | `@cherrypy.expose` + `@cherrypy.tools.json_out()` |
| ORM/Query | SQLAlchemy or raw SQL | SQLAlchemy for structure; raw SQL for minimalism |
| Database | Postgres 16 | Standard across all stacks |
| Auth | CherryPy tools (API-key) | `cherrypy.tools.api_key` custom tool |
| UI | Jinja2 (optional) | CherryPy serves templates and static files natively |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | SQLAlchemy model or raw SQL | `created_at`, `updated_at` |
| Soft deletes | `deleted_at` field | Filter in queries |
| External IDs (no integer PKs) | UUID primary keys | Standard |
| API contract | CherryPy exposed methods | JSON in, JSON out |
| MutationResult pattern | Dict response | `{"ok": True, "message": "..."}` |
| Auth | CherryPy tool (API-key) | Custom tool on the request pipeline |
| Permissions | Key-level scopes | Tool checks scopes |
| Background jobs | None (or threading) | Keep it simple |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars | Simple checks |
| Admin panel | Optional Jinja2 dashboard | CherryPy serves it |
| Testing framework | pytest | Integration tests |
| Linter/Formatter | Ruff | Standard |
| Package manager | uv or pip | `pyproject.toml` |
| Migrations | Alembic or raw SQL | Versioned scripts |

---

## Pattern: Models & ORM

SQLAlchemy for structured projects, or raw SQL via `psycopg` for absolute
minimalism. CherryPy does not include an ORM -- bring your own.

```python
# SQLAlchemy approach:
class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    scopes = Column(ARRAY(String), default=list)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
```

CherryPy's thread-local tools can manage database sessions per request via
a custom tool or plugin.

---

## Pattern: API Layer

CherryPy's object-oriented dispatch: classes map to URL paths, methods map to
endpoints. `@cherrypy.expose` marks methods as URL-accessible.
`@cherrypy.tools.json_out()` serializes return values as JSON.

```python
class WebhookApi:
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.api_key()
    def index(self):
        """POST /webhooks/"""
        if cherrypy.request.method != "POST":
            raise cherrypy.HTTPError(405)

        payload = cherrypy.request.json
        # Process webhook...
        return {"ok": True, "message": "Processed"}


class HealthApi:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"status": "ok"}


# Mount:
# /webhooks/ -> WebhookApi
# /health/   -> HealthApi
root = Root()
root.webhooks = WebhookApi()
root.health = HealthApi()
cherrypy.tree.mount(root, "/")
```

This is CherryPy's signature pattern: the URL tree mirrors the object tree.
`/webhooks/` calls `root.webhooks.index()`. Clean, Pythonic, no routing DSL.

---

## Pattern: Auth

CherryPy tool for API-key authentication. Tools hook into CherryPy's request
pipeline -- they run before the handler, similar to middleware.

```python
def api_key_tool():
    """CherryPy tool: validate API key from X-API-Key header."""
    key = cherrypy.request.headers.get("X-API-Key")
    if not key:
        raise cherrypy.HTTPError(401, "API key required")

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = get_db_session()
    api_key = db.query(ApiKey).filter_by(key_hash=key_hash, is_active=True).first()
    if not api_key:
        raise cherrypy.HTTPError(401, "Invalid API key")

    api_key.last_used_at = datetime.utcnow()
    db.commit()
    cherrypy.request.api_key = api_key


cherrypy.tools.api_key = cherrypy.Tool("before_handler", api_key_tool)
```

Usage: `@cherrypy.tools.api_key()` on any exposed method. CherryPy tools
are composable and can be applied globally, per-controller, or per-method.

---

## Pattern: Permissions

Optional per-key scopes via another CherryPy tool.

```python
def require_scope_tool(scope):
    api_key = getattr(cherrypy.request, "api_key", None)
    if not api_key:
        raise cherrypy.HTTPError(401)
    if scope not in api_key.scopes and "*" not in api_key.scopes:
        raise cherrypy.HTTPError(403, f"Missing scope: {scope}")


cherrypy.tools.require_scope = cherrypy.Tool("before_handler", require_scope_tool, priority=60)

# Usage:
@cherrypy.expose
@cherrypy.tools.api_key()
@cherrypy.tools.require_scope(scope="data.write")
def import_data(self):
    ...
```

---

## Pattern: Background Jobs

Not included by default. CherryPy has a built-in plugin system for background
tasks. For simple periodic work, use a CherryPy plugin.

```python
from cherrypy.process.plugins import Monitor

class CleanupPlugin(Monitor):
    def __init__(self, bus, frequency=3600):
        super().__init__(bus, self.cleanup, frequency=frequency)

    def cleanup(self):
        # Periodic cleanup task
        pass

CleanupPlugin(cherrypy.engine).subscribe()
```

For durable async jobs, add Celery or a Redis queue.

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Simple env var checks.

```python
import os

FEATURE_ADMIN_UI = os.getenv("FEATURE_ADMIN_UI", "false") == "true"

if FEATURE_ADMIN_UI:
    root.admin = AdminDashboard()
```

---

## Pattern: Admin

Optional Jinja2 dashboard served by CherryPy. CherryPy natively serves
static files and can render Jinja2 templates.

```python
class AdminDashboard:
    @cherrypy.expose
    @cherrypy.tools.api_key()
    def index(self):
        db = get_db_session()
        keys = db.query(ApiKey).order_by(ApiKey.last_used_at.desc()).all()
        template = jinja_env.get_template("admin/dashboard.html")
        return template.render(api_keys=keys)
```

CherryPy serves the admin UI, static assets, and the API all from the same
process. No separate web server needed.

---

## Pattern: Testing

pytest with real Postgres. CherryPy's `cherrypy.test.helper` provides a
test client, or use `requests` against a test server.

```python
import pytest
import cherrypy
from cherrypy.test import helper


class TestWebhookApi(helper.CPWebCase):
    @staticmethod
    def setup_server():
        cherrypy.tree.mount(Root(), "/")

    def test_webhook(self):
        raw_key = "test-key"
        create_test_api_key(raw_key, scopes=["*"])

        self.getPage(
            "/webhooks/",
            method="POST",
            headers=[
                ("Content-Type", "application/json"),
                ("X-API-Key", raw_key),
            ],
            body=b'{"event":"order.created","data":{"id":"123"}}',
        )
        self.assertStatus("200 OK")
        self.assertHeader("Content-Type", "application/json")
        body = json.loads(self.body)
        assert body["ok"] is True

    def test_webhook_no_key(self):
        self.getPage(
            "/webhooks/",
            method="POST",
            headers=[("Content-Type", "application/json")],
            body=b'{"event":"test","data":{}}',
        )
        self.assertStatus("401 Unauthorized")
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
| API | `api` (CherryPy, no external server) | 8080 | `GET /health/` |
| Postgres | postgres:16 | 5432 | pg_isready |

Minimal. CherryPy's built-in HTTP server is production-ready for moderate
traffic. No Gunicorn, no nginx, no WSGI layer. Just Python.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Ruff
- **Build job:** Docker build
- **Test job:** pytest with Postgres service
- **Audit job:** `pip-audit`

---

## Pattern: Security

**API key hashing:** SHA256 before storage. Never store plaintext.

**Rate limiting:** Custom CherryPy tool or `cherrypy-ratelimit` plugin.

**Input validation:** Manual validation or Pydantic models for structured
input. CherryPy does not include built-in validation.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default. CherryPy tool for CORS headers if needed.

**CherryPy-specific:** CherryPy's built-in session, caching, and logging
tools are available but not used in the micro template (no sessions needed).

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

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres)
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Shared Concepts (reusable patterns)

- API-key auth pattern (same as other micro templates)
- SQLAlchemy models (if used, same as fastapi-micro)
- Alembic migrations (if used)
- pytest test patterns

### Needs Building (new for this stack)

- CherryPy application structure (object tree dispatch)
- CherryPy tools for auth, scope checking, CORS
- CherryPy plugin for database session management
- CherryPy-specific test setup (`CPWebCase`)
- Optional Jinja2 admin UI served by CherryPy

---

## Build Order

### Phase 0: Scaffolding
- [ ] CherryPy application with object tree mount
- [ ] SQLAlchemy or raw SQL database setup
- [ ] Docker Compose (api, postgres)
- [ ] Health check endpoint, Ruff config

### Phase 1: Auth
- [ ] ApiKey model
- [ ] `cherrypy.tools.api_key` custom tool
- [ ] Key creation script
- [ ] Optional scope tool

### Phase 2: Core API
- [ ] Exposed methods with `json_in`/`json_out`
- [ ] Response wrapper pattern
- [ ] Input validation
- [ ] CherryPy database session plugin

### Phase 3: Infrastructure + Polish
- [ ] Optional Jinja2 admin dashboard
- [ ] Rate limiting tool
- [ ] CI pipeline (lint, test, audit)
- [ ] README, CLAUDE.md
