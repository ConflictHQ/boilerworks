# Boilerworks Django + HTMX -- Primer

> Server-rendered Django with HTMX for dynamic behavior and Alpine.js for
> lightweight client state. Choose this for content-heavy CRUD, admin-centric
> tools, and apps where server-rendered simplicity beats a full SPA.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-django-htmx`
**Sibling variant:** [django-nextjs](../django-nextjs/PRIMER.md)

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

- Content-heavy apps (blogs, CMS, knowledge bases, internal wikis) where
  server-rendered HTML is the natural delivery model.
- Admin-centric tools and back-office applications where rapid CRUD with
  minimal JavaScript complexity is the priority.
- Rapid prototyping where you want to ship fast -- no separate frontend build
  step, no API translation layer, just Django views and templates.

### Not Ideal For

- Apps needing rich client-side interactivity -- drag-and-drop builders,
  real-time collaboration, or complex multi-step wizards with client state.
- Apps where offline support or PWA capabilities matter.
- Teams that are React-focused and want to leverage their existing frontend
  expertise.

### vs django-nextjs

Choose django-htmx when server-rendered simplicity wins: content-heavy CRUD,
admin-facing tools, internal apps where a full SPA is overhead. No separate
frontend build step, no GraphQL layer, no React -- just Django views returning
HTML.

Choose django-nextjs when you need rich client-side interactivity: dashboards
with charts, drag-and-drop builders, multi-step form wizards, or any feature
that benefits from React's component model and client-side state.

Both share the same Django backend patterns. The difference is the frontend
delivery model.

---

## Architecture

```
Browser
  +-- Django Templates + HTMX + Alpine.js + Tailwind CSS
        |
        v (standard HTTP requests + HTMX partial responses)
        |
  Django 5 (Views, ORM, Business Logic, Permissions)
        |-- Celery (async tasks)
        |-- Postgres 16 (data)
        |-- Redis 7 (cache, sessions, broker)
        |-- OpenSearch 2 (full-text search, optional)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Django 5 | Unmatched for data-heavy backends: ORM, admin, migrations, permissions |
| Frontend | Django Templates + HTMX + Alpine.js | Server-rendered HTML with progressive enhancement, no build step |
| API | HTMX partial responses | No GraphQL or REST -- views return HTML fragments for dynamic updates |
| ORM | Django ORM | Mature, battle-tested, excellent migration system |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Celery + Redis | Fire-and-forget tasks; simple, battle-tested |
| Auth | Session-based (httpOnly cookies) | Immune to XSS token theft, instant server-side revocation |
| CSS | Tailwind CSS | Utility-first, no custom CSS files, consistent design system |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), django-ses (prod) | Standard across all stacks |
| Search | OpenSearch 2 | Full-text search with signal-based incremental indexing (optional) |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `Tracking` abstract model | `version`, `created_at/by`, `updated_at/by`, `deleted_at/by`, `history` |
| Soft deletes | `deleted_at`/`deleted_by` on `Tracking` | Never call `.delete()` |
| External IDs | `guid` UUID on `BaseCoreModel` | Never expose integer PKs |
| API contract | Django URL patterns + views | Views return full pages or HTMX partials |
| MutationResult | Django form validation errors | Errors rendered inline via HTMX partial swap |
| Auth (session-based) | `auth1` app | Django sessions, httpOnly cookies |
| Permissions (group-based) | `config/permissions.py` + `roles_gen.py` | `P.PERMISSION.check(user)` |
| Background jobs | Celery + Redis | Tasks in `appname/tasks.py` |
| Forms engine | `forms` app + Django template tags | JSON Schema, rendered server-side |
| Workflow engine | State machine + Celery actions | Table-based editor, no ReactFlow |
| Feature toggles | `config/features.py` + django-constance | Env-based + admin UI |
| Admin panel | Django Admin + `BaseCoreAdmin` | Custom widgets, import/export, dark theme |
| Testing | Django test client | Assert against rendered HTML + database state |
| Linter/Formatter | Ruff (lint + format) | Replaces flake8 + isort + black |
| Package manager | uv (preferred), Pipenv as fallback | `uv.lock` or `Pipfile.lock` |
| Migrations | Django migrations | `make migrations` / `make migrate` |

---

## Pattern: Models & ORM

Identical to django-nextjs. All business models inherit from one of two
abstract base classes.

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
use `guid` in URLs.

**Soft deletes:** Always set `deleted_at`/`deleted_by`. Never call `.delete()`.

---

## Pattern: API Layer

No GraphQL. No REST serializers. Views return HTML -- full pages for initial
loads, HTMX partials for dynamic updates. URL patterns define the API surface.

**URL patterns for a domain:**
```python
# products/urls.py
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('create/', views.product_create, name='create'),
    path('<slug:slug>/', views.product_detail, name='detail'),
    path('<slug:slug>/edit/', views.product_update, name='update'),
    path('<slug:slug>/delete/', views.product_delete, name='delete'),
]
```

**View returning an HTMX partial:**
```python
# products/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from config.permissions import P
from .models import Product
from .forms import ProductForm


@login_required
def product_list(request):
    P.PRODUCT_VIEW.check(request.user)
    products = Product.objects.filter(deleted_at__isnull=True)

    search = request.GET.get('search', '')
    if search:
        products = products.filter(name__icontains=search)

    # HTMX request -- return only the table fragment
    if request.headers.get('HX-Request'):
        return render(request, 'products/partials/product_table.html', {
            'products': products,
        })

    return render(request, 'products/product_list.html', {
        'products': products,
        'search': search,
    })


@login_required
def product_create(request):
    P.PRODUCT_ADD.check(request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            return redirect('products:detail', slug=product.slug)
    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {'form': form})
```

**Django form class for validation:**
```python
# products/forms.py
from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full rounded-md border-gray-300 shadow-sm',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-md border-gray-300 shadow-sm',
                'rows': 4,
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full rounded-md border-gray-300 shadow-sm',
                'step': '0.01',
            }),
        }
```

**HTMX-enhanced template:**
```html
<!-- products/product_list.html -->
{% extends "base.html" %}

{% block content %}
<div class="max-w-6xl mx-auto px-4 py-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Products</h1>
    <a href="{% url 'products:create' %}"
       class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
      New Product
    </a>
  </div>

  <input type="search"
         name="search"
         value="{{ search }}"
         placeholder="Search products..."
         class="w-full rounded-md border-gray-300 shadow-sm mb-4"
         hx-get="{% url 'products:list' %}"
         hx-trigger="input changed delay:300ms"
         hx-target="#product-table"
         hx-swap="outerHTML" />

  <div id="product-table">
    {% include "products/partials/product_table.html" %}
  </div>
</div>
{% endblock %}
```

**HTMX partial template:**
```html
<!-- products/partials/product_table.html -->
<div id="product-table">
  <table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50">
      <tr>
        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
      </tr>
    </thead>
    <tbody class="bg-white divide-y divide-gray-200">
      {% for product in products %}
      <tr>
        <td class="px-6 py-4 whitespace-nowrap">
          <a href="{% url 'products:detail' slug=product.slug %}"
             class="text-indigo-600 hover:text-indigo-900">{{ product.name }}</a>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">${{ product.price }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-right">
          <a href="{% url 'products:update' slug=product.slug %}"
             class="text-sm text-gray-600 hover:text-gray-900">Edit</a>
        </td>
      </tr>
      {% empty %}
      <tr>
        <td colspan="3" class="px-6 py-4 text-center text-gray-500">No products found.</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

**Alpine.js for client-side interactivity:**
```html
<!-- Dropdown menu -->
<div x-data="{ open: false }" class="relative">
  <button x-on:click="open = !open"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
    Actions
    <svg x-bind:class="open && 'rotate-180'" class="h-4 w-4 transition-transform" ...></svg>
  </button>
  <div x-show="open"
       x-on:click.outside="open = false"
       x-transition
       class="absolute right-0 mt-2 w-48 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5">
    <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Export CSV</a>
    <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Archive</a>
  </div>
</div>

<!-- Modal toggle -->
<div x-data="{ showModal: false }">
  <button x-on:click="showModal = true"
          class="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white">
    Delete
  </button>
  <div x-show="showModal" x-transition class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="fixed inset-0 bg-black bg-opacity-50" x-on:click="showModal = false"></div>
    <div class="relative rounded-lg bg-white p-6 shadow-xl">
      <p class="mb-4 text-gray-700">Are you sure you want to delete this item?</p>
      <div class="flex justify-end gap-3">
        <button x-on:click="showModal = false"
                class="rounded-md border px-4 py-2 text-sm text-gray-700">Cancel</button>
        <button hx-delete="{% url 'products:delete' slug=product.slug %}"
                hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
                class="rounded-md bg-red-600 px-4 py-2 text-sm text-white">Confirm</button>
      </div>
    </div>
  </div>
</div>
```

**CSRF protection for HTMX:** Include a meta tag in `base.html` and configure
HTMX to send it with every request:
```html
<meta name="csrf-token" content="{{ csrf_token }}">
<script>
  document.body.addEventListener('htmx:configRequest', function(event) {
    event.detail.headers['X-CSRFToken'] =
      document.querySelector('meta[name="csrf-token"]').content;
  });
</script>
```

---

## Pattern: Auth

Identical to django-nextjs. Session-based authentication via the `auth1` app.

- Sessions stored server-side (database-backed), token as httpOnly cookie.
- Server-side revocation is instant (no JWT expiry wait).
- Rate limiting on auth endpoints via django-ratelimit.
- No JWT transport layer -- Django handles the full request lifecycle.

Frontend: `@login_required` decorator on views. Unauthenticated requests
redirect to the login page via Django's `LOGIN_URL` setting. No client-side
auth state to manage.

```python
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    return render(request, 'dashboard.html', {'user': request.user})
```

---

## Pattern: Permissions

Identical to django-nextjs. Group-based. Never user-based. No exceptions.

**Defining:** `config/permissions.py` with `ModelPermissions`. Generated enum
in `config/roles_gen.py` (regenerate: `make perms`).
```python
class ProductPermissions(ModelPermissions):
    model = FieldPermissions(
        view=P.PRODUCT_VIEW, add=P.PRODUCT_ADD,
        change=P.PRODUCT_CHANGE, delete=P.PRODUCT_DELETE,
    )
```

**Checking in views:**
```python
P.PRODUCT_VIEW.check(request.user)          # raises if denied
P.PRODUCT_CHANGE.check(request.user, False)  # returns False if denied
```

Assign to groups in admin, never directly to users.

**Template guards:**
```html
{% if perms.products.view_product %}
  <a href="{% url 'products:list' %}">Products</a>
{% endif %}
```

---

## Pattern: Background Jobs

Identical to django-nextjs. Celery with Redis broker. Tasks in
`appname/tasks.py`. Import models inside the function to avoid circular
imports.

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

Same JSON Schema definitions as django-nextjs, but rendered server-side via
Django template tags instead of React components.

**Backend:** `FormDefinition` model with versioned JSON Schema (draft ->
published -> archived). `field_types.py` defines 21+ built-in types. Logic
engine evaluates conditional rules (show/hide/require/calculate).

**Rendering:** Custom template tags render form fields from JSON Schema. No
React Hook Form -- standard Django form rendering with Tailwind classes.

```html
{% load dynamic_forms %}

<form method="post" hx-post="{% url 'forms:submit' slug=form_def.slug %}"
      hx-target="#form-result" hx-swap="outerHTML">
  {% csrf_token %}
  {% render_dynamic_form form_def submission %}
  <button type="submit"
          class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">
    Submit
  </button>
</form>
<div id="form-result"></div>
```

**Visual builder:** Django admin `FormBuilderWidget` (vanilla JS,
drag-and-drop, JSON toggle). No separate React form builder -- the admin
widget handles it.

**Adding a field type:**
1. `backend/forms/field_types.py` -- add to `FIELD_TYPES` dict
2. `backend/forms/templatetags/dynamic_forms.py` -- add rendering logic
3. `backend/core/static/admin/js/form_builder.js` -- add to type picker

---

## Pattern: Workflow Engine

Same state machine model as django-nextjs, but with a simpler editor.

**State:** `{name, label, is_initial, is_final, color, form_slug?, assigned_role?}`
**Transition:** `{from_state, to_state, label, conditions[], actions[]}`

**Condition types:** `user_has_role`, `field_equals`, `field_in`,
`is_authenticated`, `is_superuser`
**Action types:** `notify_user`, `send_email`, `call_webhook`, `update_field`

**Editor:** Table-based workflow editor in Django admin via
`WorkflowStatesWidget` + `WorkflowTransitionsWidget`. No ReactFlow canvas --
states and transitions are managed as editable rows.

Celery tasks execute async actions. Transition logging provides an immutable
audit trail.

---

## Pattern: Feature Toggles

Identical to django-nextjs.

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
and its URL patterns are not registered. Runtime toggles via django-constance
admin UI.

---

## Pattern: Admin

Identical to django-nextjs. Django Admin with custom dark theme. All admin
classes inherit `BaseCoreAdmin`.

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

Django test client integration tests. Assert against rendered HTML and database
state. Real database, not mocks.

```python
class ProductViewTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='TestOrg')
        self.user = User.objects.create_superuser(
            username='test', email='t@t.com', password='x')
        OrganizationMember.objects.create(
            organization=self.org, member=self.user, is_active=True)
        self.user.profile.active_organization = self.org
        self.user.profile.save()
        self.client.login(username='test', password='x')

    def test_create_product(self):
        response = self.client.post(reverse('products:create'), {
            'name': 'Widget',
            'description': 'A test widget',
            'price': '9.99',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(name='Widget').exists())
        product = Product.objects.get(name='Widget')
        self.assertEqual(product.created_by, self.user)

    def test_list_htmx_partial(self):
        Product.objects.create(name='Widget', price='9.99', created_by=self.user)
        response = self.client.get(
            reverse('products:list'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Widget')
        self.assertTemplateUsed(response, 'products/partials/product_table.html')

    def test_list_requires_permission(self):
        # Create a non-superuser without product view permission
        limited_user = User.objects.create_user(
            username='limited', email='l@t.com', password='x')
        self.client.login(username='limited', password='x')
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 403)
```

**Rules:** Assert against database state, not hardcoded strings. No empty test
bodies. Test both allowed and denied permission cases. Integration tests via
Django test client, not isolated model tests. Real database -- never mock.

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `boilerworks-local` (Django + Gunicorn) | 8000 | `/health/` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Celery Worker | Same image, different entrypoint | -- | -- |
| Celery Beat | Same image, different entrypoint | -- | -- |
| Flower | mher/flower | 5555 | -- |
| OpenSearch | opensearch:2 (optional) | 9200 | HTTP check |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No separate frontend service. Django serves everything -- templates, static
files (Tailwind via `django-tailwind` or pre-built CSS), and HTMX partials.
One fewer container than django-nextjs.

---

## Pattern: CI/CD

`Makefile` targets: `make lint`, `make test`, `make build`. GitHub Actions runs
lint (Ruff via pre-commit) and test (with Postgres + Redis services).
CI must pass before merge. Tests run against a real database with seed data.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens (raw to client, hash to DB). API
keys also hashed. httpOnly cookies, secure in prod, sameSite lax. 30-day
expiry. CORS restricted to explicit origin whitelist (simpler than
django-nextjs since same-origin). Rate limiting on auth endpoints.

**Authorization:** Auth check at the top of every view. Ownership checks on
mutations. Never trust client-provided IDs alone.

**CSRF protection:** `{% csrf_token %}` in all forms. HTMX requests include
CSRF token via `htmx:configRequest` event handler. Django's CSRF middleware
validates all POST/PUT/DELETE requests.

**Input validation:** Django forms at view boundaries. Filename sanitization.
MIME whitelist + 50MB size limit for uploads.

**SSRF protection:** URL validator on all outgoing requests. Block private IPs,
localhost, non-HTTP schemes.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Ruff (format) | `pyproject.toml` |
| Linting | Ruff (check) | `pyproject.toml` |
| Max line length | 140 characters | `pyproject.toml` |
| Import sorting | Ruff (isort rules) | Built into Ruff |
| Pre-commit hooks | Ruff | `.pre-commit-config.yaml` |
| CSS | Tailwind CSS | `tailwind.config.js` |

Run `make lint` before committing. Two blank lines between top-level
definitions. Docstrings only where logic is not self-evident. PEP 8 throughout.

---

## What Carries Over

### From django-nextjs (reusable as-is)

All Django backend code carries over unchanged:
- `Tracking`/`BaseCoreModel` base classes and all business models
- `config/permissions.py` + `roles_gen.py`
- `BaseCoreAdmin` + all custom admin widgets
- `auth1` session auth app
- Celery task patterns and beat configuration
- `config/features.py` feature toggles
- Management commands and seed data
- All model migrations

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (not portable from django-nextjs)

- Django views returning HTML (replace GraphQL resolvers)
- Django templates with Tailwind CSS (replace React components)
- HTMX partials for dynamic behavior (replace Apollo Client queries)
- Django template tags for forms engine (replace React form renderer)
- Table-based workflow editor (replace ReactFlow canvas)
- Tailwind CSS build pipeline (replace Next.js CSS setup)

---

## Build Order

### Phase 0: Scaffolding
- [ ] Project structure (Django monolith, no separate frontend)
- [ ] Django 5 app with ORM, views, templates
- [ ] Tailwind CSS integration (django-tailwind or standalone CLI)
- [ ] HTMX + Alpine.js included in base template
- [ ] Docker Compose (no frontend service)
- [ ] Health check, basic config

### Phase 1: Auth + Permissions
- [ ] auth1 session auth (login, logout views with templates)
- [ ] `@login_required` decorator on all views
- [ ] User, Group, Permission models + seed
- [ ] `P.PERMISSION.check()` in views
- [ ] Template permission guards (`{% if perms.* %}`)

### Phase 2: Core Views
- [ ] URL pattern conventions (list, detail, create, update, delete)
- [ ] Base templates with Tailwind layout (sidebar, nav, content area)
- [ ] HTMX partial response pattern (`HX-Request` header detection)
- [ ] Django form classes with Tailwind widget attrs
- [ ] CSRF token injection for HTMX requests
- [ ] Alpine.js patterns (dropdowns, modals, toggles)

### Phase 3: Forms Engine
- [ ] FormDefinition model (shared from django-nextjs)
- [ ] Field types + validation (shared from django-nextjs)
- [ ] Logic engine (shared from django-nextjs)
- [ ] `{% render_dynamic_form %}` template tag
- [ ] HTMX form submission + inline error rendering
- [ ] Admin FormBuilderWidget (shared from django-nextjs)

### Phase 4: Workflow Engine
- [ ] Workflow models (shared from django-nextjs)
- [ ] State machine service (shared from django-nextjs)
- [ ] Job queue processors for actions (shared from django-nextjs)
- [ ] Table-based workflow editor templates
- [ ] Transition UI with HTMX (state buttons, confirmation modals)

### Phase 5: Infrastructure & Polish
- [ ] File uploads (MinIO/S3)
- [ ] Email service (ses/Mailpit)
- [ ] Notifications (in-app, rendered via HTMX)
- [ ] Feature toggles
- [ ] Seed data + examples
- [ ] README, CLAUDE.md, bootstrap.md
- [ ] CI pipeline
