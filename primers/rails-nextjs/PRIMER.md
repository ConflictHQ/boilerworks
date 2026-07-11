# Boilerworks Rails + Next.js -- Primer

> Rails 8 backend with a rich Next.js 16 frontend. The Rails API-mode backend
> paired with React's interactivity. Choose this over rails-hotwire when you need
> complex dashboards, drag-and-drop builders, or a full SPA experience.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-rails-nextjs`
**Sibling variant:** [rails-hotwire](../rails-hotwire/PRIMER.md)

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

- Ruby teams who want Rails conventions on the backend but need a richer
  frontend than Hotwire provides -- dashboards, chart-heavy UIs, drag-and-drop
  builders, complex multi-step wizards.
- Projects where the frontend will serve multiple clients (web, mobile) via
  a shared GraphQL API backed by Rails.
- Teams that want the shared Boilerworks Next.js frontend while leveraging
  Rails' convention-over-configuration productivity.

### Not Ideal For

- Apps where server-rendered HTML is sufficient. Choose
  [rails-hotwire](../rails-hotwire/PRIMER.md) -- simpler, one fewer service.
- Teams without Ruby experience. The backend learning curve is the same
  regardless of frontend choice.
- Microservices. Rails is a monolith framework by design.

### vs rails-hotwire

Choose rails-nextjs when you need rich client-side interactivity: dashboards
with charts, drag-and-drop builders, complex form wizards, real-time
collaboration, or anything that benefits from React's component model.

Choose rails-hotwire when server-rendered simplicity wins: content-heavy CRUD,
Turbo Streams for real-time, admin-facing tools where Hotwire handles all
dynamic behavior.

Both share the same Rails backend patterns (Active Record, Pundit, Solid
Queue). The difference is the frontend delivery model and API layer.

---

## Architecture

```
Browser
  +-- Next.js 16 (shared frontend -- see NEXTJS_FRONTEND.md)
        +-- Apollo Client -> GraphQL API
              |
              v
        Rails 8 (API mode or full Rails with GraphQL)
              |-- graphql-ruby (API layer)
              |-- Solid Queue (async jobs)
              |-- Postgres 16 (via Active Record)
              |-- Redis 7 (cache, sessions, Action Cable)
              +-- MinIO (S3-compatible via Active Storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Rails 8 | Convention-over-configuration, batteries-included |
| Frontend | Next.js 16 | Shared frontend -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) |
| API | GraphQL (graphql-ruby) | Type-safe API for React frontend, consistent with other Next.js stacks |
| ORM | Active Record | Mature, tightly integrated with Rails |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Solid Queue (Rails 8 default) | Database-backed, zero-config |
| Auth | Devise (session-based, httpOnly cookies) | Battle-tested |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Action Mailer (prod) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `ApplicationRecord` + `Auditable` concern | Same as rails-hotwire |
| Soft deletes | `SoftDeletable` concern | Same as rails-hotwire |
| External IDs (no integer PKs) | `ExternalId` concern (UUID) | Same as rails-hotwire |
| API contract | GraphQL (graphql-ruby) | Types, queries, mutations |
| MutationResult pattern | `MutationResult` GraphQL type | `{ok, errors}` |
| Auth (session-based) | Devise | httpOnly cookies, server-side sessions |
| Permissions (group-based) | Pundit policies | `authorize @record` |
| Background jobs | Solid Queue (Active Job) | Same as rails-hotwire |
| Forms engine | Phase 2 | JSON Schema, same concept |
| Workflow engine | Phase 2 | State machine, same concept |
| Feature toggles | `config/features.rb` + env vars | Same as rails-hotwire |
| Admin panel | ActiveAdmin or Administrate | Same as rails-hotwire |
| Testing framework | RSpec + FactoryBot | Request specs for GraphQL |
| Linter/Formatter | RuboCop | `.rubocop.yml` |
| Package manager | Bundler | `Gemfile` |
| Migrations | Active Record migrations | `rails db:migrate` |

---

## Pattern: Models & ORM

Identical to rails-hotwire. All business models inherit from
`ApplicationRecord` and include `Auditable`, `SoftDeletable`, `ExternalId`
concerns. `Current.user` provides audit context.

```ruby
class Product < ApplicationRecord
  include Auditable, SoftDeletable, ExternalId
  validates :name, presence: true
  validates :price, numericality: { greater_than: 0 }
end
```

---

## Pattern: API Layer

GraphQL via graphql-ruby. Each domain has types, queries, and mutations.
Schema assembled in `app/graphql/`.

```ruby
module Types
  class ProductType < Types::BaseObject
    field :id, ID, null: false, method: :uuid
    field :name, String, null: false
    field :slug, String, null: false
    field :price, String, null: false
    field :created_at, GraphQL::Types::ISO8601DateTime, null: false
  end
end

module Mutations
  class CreateProduct < BaseMutation
    argument :name, String, required: true
    argument :price, String, required: true

    field :ok, Boolean, null: false
    field :errors, [Types::FieldErrorType], null: true

    def resolve(name:, price:)
      authorize Product, :create?
      product = Product.new(name: name, price: BigDecimal(price))
      if product.save
        { ok: true, errors: nil }
      else
        { ok: false, errors: format_errors(product) }
      end
    end
  end
end
```

Auth check at the top of every resolver. `context[:current_user]` populated
by Devise via controller.

---

## Pattern: Auth

Identical to rails-hotwire. Devise with session-based auth. `Current.user`
via `SetCurrentAttributes`. SHA256-hashed tokens.

Frontend: Next.js auth gate -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Permissions

Identical to rails-hotwire. Pundit policies. Group-based, never user-based.

```ruby
# In GraphQL mutations:
def resolve(...)
  authorize Product, :create?
  ...
end
```

Frontend: permission guards via shared Next.js hooks.

---

## Pattern: Background Jobs

Identical to rails-hotwire. Solid Queue with Active Job. Mission Control
for monitoring.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Rails backend implementation, Next.js
DynamicForm + FormBuilder from shared frontend.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Rails backend with AASM, Active Job
for async actions. Next.js WorkflowBuilder (ReactFlow) from shared frontend.

---

## Pattern: Feature Toggles

Identical to rails-hotwire. `config/features.rb` with env vars. Conditional
route mounting and schema registration.

---

## Pattern: Admin

Identical to rails-hotwire. ActiveAdmin with Pundit integration. Auth-gated.

---

## Pattern: Testing

RSpec request specs targeting the GraphQL endpoint. Real database via
FactoryBot.

```ruby
RSpec.describe "Products GraphQL", type: :request do
  let(:user) { create(:user, :with_product_permissions) }

  it "creates a product" do
    post "/graphql", params: { query: <<~GQL }, headers: auth_headers(user)
      mutation {
        createProduct(name: "Widget", price: "9.99") {
          ok
          errors { field messages }
        }
      }
    GQL

    data = json_response["data"]["createProduct"]
    expect(data["ok"]).to be true
    expect(Product.last.name).to eq("Widget")
  end

  it "denies unauthenticated access" do
    post "/graphql", params: { query: "{ products { id } }" }
    expect(json_response["errors"]).to be_present
  end
end
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via GraphQL endpoint, not isolated model tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `api` (Rails + Puma) | 3000 | `/up` |
| Frontend | `ui` (Next.js) | 3001 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Solid Queue Worker | Same image, `bin/jobs` entrypoint | -- | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** RuboCop (backend), ESLint + Prettier (frontend)
- **Build job:** Docker build for both services
- **Test job:** RSpec with Postgres + Redis services
- **Audit job:** `bundle audit` + `brakeman` (backend), npm audit (frontend)

---

## Pattern: Security

Identical to rails-hotwire for the backend. Session hardening, Pundit
authorization, strong parameters, Brakeman, SSRF protection, Active Storage
validation.

GraphQL-specific: query depth limiting, introspection disabled in prod,
masked error messages.

CORS restricted to explicit origin whitelist for the Next.js frontend.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting/Linting | RuboCop | `.rubocop.yml` |
| Max line length | 120 characters | `.rubocop.yml` |
| Frontend formatting | Prettier | `.prettierrc` |
| Frontend linting | ESLint | `eslint.config.js` |

---

## What Carries Over

### Frontend (shared across all Next.js stacks)

The Next.js frontend is backend-agnostic. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md). Carries over as-is.

### From rails-hotwire (reusable as-is)

All Rails backend code carries over unchanged:
- `ApplicationRecord` + concerns (Auditable, SoftDeletable, ExternalId)
- Devise auth configuration
- Pundit policies
- Solid Queue job infrastructure
- Active Record models and migrations
- Feature toggles, ActiveAdmin
- Seed data

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new implementation)

- graphql-ruby schema (types, queries, mutations)
- GraphQL context with Devise current_user
- CORS configuration for Next.js frontend
- Rails API mode or GraphQL controller setup

---

## Build Order

### Phase 0: Scaffolding
- [ ] Rails 8 (API mode or full with GraphQL controller)
- [ ] graphql-ruby gem + schema structure
- [ ] Active Record + concerns (from rails-hotwire)
- [ ] Next.js 16 frontend (copy from shared template)
- [ ] Docker Compose (api, ui, postgres, redis, minio, mailpit)
- [ ] Health check, RuboCop + ESLint config

### Phase 1: Auth + Permissions
- [ ] Devise session auth (from rails-hotwire)
- [ ] GraphQL context with current_user
- [ ] Pundit policies (from rails-hotwire)
- [ ] Frontend auth gate (shared from NEXTJS_FRONTEND)

### Phase 2: Core API
- [ ] GraphQL types, queries, mutations for core models
- [ ] MutationResult pattern
- [ ] Audit logging via Auditable concern
- [ ] Soft delete pattern

### Phase 3: Forms Engine
- [ ] FormDefinition model (from rails-hotwire)
- [ ] GraphQL CRUD for forms
- [ ] Frontend DynamicForm + FormBuilder (shared)

### Phase 4: Workflow Engine
- [ ] Workflow models (from rails-hotwire)
- [ ] GraphQL CRUD + transition mutations
- [ ] Frontend WorkflowBuilder (shared)

### Phase 5: Infrastructure + Polish
- [ ] Active Storage + MinIO, Action Mailer
- [ ] Feature toggles, Solid Queue + Mission Control
- [ ] Seed data, CI pipeline, README, CLAUDE.md
