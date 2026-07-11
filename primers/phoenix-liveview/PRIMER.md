# Boilerworks Phoenix + LiveView -- Primer

> Phoenix 1.7 with LiveView for real-time, collaborative applications. Choose this
> for apps where real-time is the default -- chat, collaborative editing, live
> dashboards, multiplayer experiences -- all over WebSocket with no separate
> frontend deployment.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-phoenix-liveview`
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

- Real-time applications where live updates are the primary UX -- chat,
  collaborative editing, live dashboards, multiplayer experiences, auction
  platforms.
- Teams with Elixir/Erlang experience who want the BEAM's fault tolerance,
  concurrency model, and ability to hold millions of WebSocket connections.
- Projects where real-time is built in, not bolted on -- LiveView's WebSocket
  connection eliminates the need for a separate real-time layer.

### Not Ideal For

- Teams without Elixir experience -- the learning curve is steep (functional
  programming, OTP, process model) and the talent pool is smaller.
- Apps that need rich client-side state management or offline support. LiveView
  requires a persistent WebSocket connection.
- SEO-critical public-facing sites where full SSR with hydration (Next.js)
  gives better control over initial render and crawlability.

---

## Architecture

```
Browser
  +-- Phoenix LiveView (WebSocket connection)
        |
        v (WebSocket -- bidirectional, persistent)
        |
  Phoenix 1.7 (Plug pipeline, Ecto, PubSub)
        |-- Oban (async jobs, Postgres-backed)
        |-- Postgres 16 (via Ecto)
        |-- Redis 7 (PubSub adapter for multi-node, cache)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Phoenix 1.7 (Elixir) | BEAM concurrency, fault tolerance, real-time native |
| Frontend | LiveView | Server-rendered, real-time via WebSocket, no separate JS framework |
| API | LiveView (WebSocket) | No separate REST/GraphQL -- LiveView handles state + rendering |
| ORM | Ecto | Explicit queries, composable, excellent migration system |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | PubSub adapter for distributed Phoenix nodes |
| Job Queue | Oban | Postgres-backed, reliable, built for Elixir |
| Auth | phx.gen.auth | Phoenix's built-in auth generator, session-based |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Swoosh (prod) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Ecto schema + `Auditable` behaviour | `inserted_at`, `updated_at`, `created_by`, `updated_by` |
| Soft deletes | `deleted_at`/`deleted_by` fields | Ecto query filter |
| External IDs (no integer PKs) | UUID binary primary keys | `:binary_id` in Ecto schema |
| API contract | LiveView events + PubSub | No REST/GraphQL for frontend; optional JSON API for external clients |
| MutationResult pattern | Ecto changeset errors | `{:ok, record}` or `{:error, changeset}` |
| Auth (session-based) | phx.gen.auth | Session tokens, httpOnly cookies |
| Permissions (group-based) | Custom RBAC with Ecto | `has_permission?/2` helper |
| Background jobs | Oban | Postgres-backed, `Oban.Worker` behaviours |
| Forms engine | Phase 2 | JSON Schema, LiveView rendering |
| Workflow engine | Phase 2 | State machine, Oban for async actions |
| Feature toggles | `config/features.ex` + env vars | Conditional module loading |
| Admin panel | Kaffy or custom LiveView admin | Auto-generated from Ecto schemas |
| Testing framework | ExUnit | Integration tests with real database |
| Linter/Formatter | `mix format` + Credo | Standard Elixir tooling |
| Package manager | Mix + Hex | `mix.exs` + `mix.lock` |
| Migrations | Ecto migrations | `mix ecto.migrate` |

---

## Pattern: Models & ORM

Ecto schemas with shared audit fields. UUID primary keys throughout.
Changesets for validation.

```elixir
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}

  schema "users" do
    field :email, :string
    field :hashed_password, :string
    has_many :group_memberships, MyApp.Accounts.UserGroup
    has_many :groups, through: [:group_memberships, :group]
    timestamps()
  end
end

defmodule MyApp.Catalog.Product do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}

  schema "products" do
    field :name, :string
    field :slug, :string
    field :price, :decimal
    field :deleted_at, :utc_datetime
    belongs_to :created_by, MyApp.Accounts.User, type: :binary_id
    belongs_to :updated_by, MyApp.Accounts.User, type: :binary_id
    belongs_to :deleted_by, MyApp.Accounts.User, type: :binary_id
    timestamps()
  end

  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :price])
    |> validate_required([:name, :price])
    |> validate_number(:price, greater_than: 0)
    |> unique_constraint(:slug)
  end
end
```

Soft deletes: set `deleted_at`/`deleted_by`. Filter with
`where(is_nil(p.deleted_at))` in all queries.

---

## Pattern: API Layer

No separate API for the frontend. LiveView handles state management and
rendering over a persistent WebSocket connection. Events from the client
trigger server-side callbacks that update state and re-render.

```elixir
defmodule MyAppWeb.ProductLive.Index do
  use MyAppWeb, :live_view

  alias MyApp.Catalog

  @impl true
  def mount(_params, _session, socket) do
    require_permission!(socket, "product.view")
    products = Catalog.list_products()

    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, "products")
    end

    {:ok, assign(socket, products: products, search: "")}
  end

  @impl true
  def handle_event("search", %{"search" => search}, socket) do
    products = Catalog.list_products(search: search)
    {:noreply, assign(socket, products: products, search: search)}
  end

  @impl true
  def handle_info({:product_created, product}, socket) do
    {:noreply, update(socket, :products, &[product | &1])}
  end
end
```

Real-time updates via PubSub -- when a product is created anywhere, all
connected clients see the update immediately.

---

## Pattern: Auth

phx.gen.auth generates session-based authentication with token hashing.
Sessions stored in the database, delivered as httpOnly cookies.

```elixir
# Generated by: mix phx.gen.auth Accounts User users
# Provides:
# - User schema with hashed_password
# - UserToken schema (SHA256 hashed before storage)
# - Registration, login, logout, password reset
# - Session plug (populates conn.assigns.current_user)
# - LiveView on_mount hook for auth
```

LiveView auth: `on_mount` hook validates the session token on WebSocket
connection. Server-side revocation is instant.

---

## Pattern: Permissions

Custom RBAC with Ecto. Group-based, never user-based.

```elixir
defmodule MyApp.Authorization do
  import Ecto.Query
  alias MyApp.Repo

  def has_permission?(%{id: user_id}, permission_slug) do
    Repo.exists?(
      from p in "permissions",
      join: gp in "group_permissions", on: gp.permission_id == p.id,
      join: ug in "user_groups", on: ug.group_id == gp.group_id,
      where: ug.user_id == ^user_id and p.slug == ^permission_slug
    )
  end
end

# LiveView helper
defp require_permission!(socket, slug) do
  unless Authorization.has_permission?(socket.assigns.current_user, slug) do
    raise MyAppWeb.ForbiddenError
  end
end
```

---

## Pattern: Background Jobs

Oban -- Postgres-backed, reliable, built for Elixir. No Redis dependency
for job storage.

```elixir
defmodule MyApp.Workers.ProcessInvoice do
  use Oban.Worker, queue: :default, max_attempts: 3

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"invoice_id" => invoice_id}}) do
    invoice = MyApp.Billing.get_invoice!(invoice_id)
    MyApp.Billing.process_invoice(invoice)
  end
end

# Dispatch
%{invoice_id: invoice.id}
|> MyApp.Workers.ProcessInvoice.new()
|> Oban.insert()
```

Oban Web (paid) or custom LiveView dashboard for monitoring. Oban provides
built-in scheduling (cron), unique jobs, and structured logging.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Elixir implementation of validation and
logic engine. LiveView components render form fields dynamically. LiveView's
built-in form handling provides real-time validation feedback.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Elixir implementation with Oban workers
for async actions. LiveView provides real-time workflow state updates via
PubSub -- all connected users see transitions immediately.

---

## Pattern: Feature Toggles

```elixir
# config/features.ex
defmodule MyApp.Features do
  def enabled?(:forms), do: System.get_env("FEATURE_FORMS") == "true"
  def enabled?(:workflows), do: System.get_env("FEATURE_WORKFLOWS") == "true"
end

# In router:
if MyApp.Features.enabled?(:forms) do
  live "/forms", FormLive.Index, :index
end
```

When disabled, routes are not mounted and navigation links are hidden. Tied
to Docker Compose profiles for optional infrastructure.

---

## Pattern: Admin

Kaffy (auto-generated admin from Ecto schemas) or custom LiveView admin pages.

```elixir
# config/kaffy.exs
config :kaffy,
  otp_app: :my_app,
  resources: &MyApp.Kaffy.Config.create_resources/1
```

Kaffy provides basic CRUD, search, and filtering. For more control, build
custom LiveView admin pages with the same permission system.

---

## Pattern: Testing

ExUnit with real Postgres database. Test LiveView interactions with
`Phoenix.LiveViewTest`.

```elixir
defmodule MyAppWeb.ProductLive.IndexTest do
  use MyAppWeb.ConnCase
  import Phoenix.LiveViewTest

  setup :register_and_log_in_user

  test "lists products", %{conn: conn} do
    product = product_fixture(name: "Widget")
    {:ok, view, _html} = live(conn, ~p"/products")
    assert has_element?(view, "td", "Widget")
  end

  test "creates a product", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/products/new")
    view
    |> form("#product-form", product: %{name: "Widget", price: "9.99"})
    |> render_submit()

    assert MyApp.Catalog.get_product_by_slug("widget")
  end

  test "denies access without permission", %{conn: conn} do
    conn = log_in_user(conn, user_without_permissions())
    assert {:error, {:redirect, _}} = live(conn, ~p"/products")
  end
end
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via LiveView, not isolated function tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `app` (Phoenix + Cowboy) | 4000 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No separate frontend container. LiveView is served by Phoenix. Oban runs
within the Phoenix application (no separate worker process needed, though
one can be configured for heavy workloads).

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** `mix format --check-formatted` + Credo
- **Build job:** `mix compile --warnings-as-errors` + Docker build
- **Test job:** `mix test` with Postgres service
- **Audit job:** `mix deps.audit` + `mix hex.audit`

CI must pass before merge.

---

## Pattern: Security

**Session hardening:** phx.gen.auth provides SHA256-hashed tokens, httpOnly
cookies, sameSite lax. Server-side revocation is instant.

**Authorization:** Permission check in every LiveView `mount/3` and
`handle_event/3`. Ownership checks on mutations.

**Input validation:** Ecto changesets at all boundaries. Parameterized queries
prevent SQL injection (Ecto does this by default).

**SSRF protection:** URL validator on outgoing HTTP requests.

**WebSocket security:** LiveView WebSocket connections are authenticated via
session token. CSRF protection via Phoenix's built-in CSRF plug.

**File uploads:** LiveView provides built-in upload handling with MIME
validation, size limits, and progress tracking.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | `mix format` | `.formatter.exs` |
| Linting | Credo | `.credo.exs` |
| Max line length | 98 characters (Elixir default) | `.formatter.exs` |
| Pre-commit hooks | `mix format` + Credo | `.pre-commit-config.yaml` |

Standard Elixir formatting. `mix format` is non-negotiable. Two-space
indentation. snake_case for functions/variables. CamelCase for modules.

---

## What Carries Over

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- CI pipeline structure (lint, test, audit jobs)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Shared Concepts (same mental model, Elixir implementation)

- Permission model (group-based RBAC, same pattern)
- Forms engine (JSON Schema, same field types, same lifecycle)
- Workflow engine (same state machine, same condition/action types)
- Audit trail (`created_by`/`updated_by` fields)
- Soft deletes (`deleted_at` filter)

### Needs Building (new implementation)

- Ecto schemas with audit fields and soft delete
- phx.gen.auth customization (groups, permissions)
- Custom RBAC permission system
- Oban job queue setup
- LiveView components for forms and workflows
- Kaffy or custom admin panel
- LiveView-specific test patterns

---

## Build Order

### Phase 0: Scaffolding
- [ ] Phoenix 1.7 project with LiveView, Ecto, Tailwind CSS
- [ ] Ecto schemas with audit fields, UUID primary keys
- [ ] Docker Compose (app, postgres, redis, minio, mailpit)
- [ ] Health check, `mix format` + Credo config

### Phase 1: Auth + Permissions
- [ ] phx.gen.auth (session auth, token hashing)
- [ ] User, Group, Permission schemas + seed data
- [ ] Custom RBAC (`has_permission?/2`)
- [ ] LiveView auth hooks + permission guards

### Phase 2: Core LiveViews
- [ ] CRUD LiveViews with real-time updates via PubSub
- [ ] LiveComponent patterns (forms, tables, modals)
- [ ] Audit logging via changeset callbacks

### Phase 3: Forms Engine
- [ ] FormDefinition Ecto schema, field types, validation
- [ ] Logic engine (Elixir implementation)
- [ ] LiveView dynamic form renderer + builder

### Phase 4: Workflow Engine
- [ ] Workflow Ecto schemas (definition, instance, transition log)
- [ ] State machine service, Oban action workers
- [ ] LiveView workflow builder with real-time state

### Phase 5: Infrastructure + Polish
- [ ] File uploads (LiveView uploads + MinIO)
- [ ] Email (Swoosh + Mailpit), notifications via PubSub
- [ ] Feature toggles, Oban dashboard
- [ ] Seed data, CI pipeline, README, CLAUDE.md
