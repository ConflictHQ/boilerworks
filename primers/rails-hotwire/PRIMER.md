# Boilerworks Rails 8 + Hotwire -- Primer

> The Rails-native blessed path. Full-stack Rails 8 with Hotwire (Turbo + Stimulus)
> for progressive server-rendered HTML. Choose this for content platforms, marketplaces,
> social apps, and teams that want convention-over-configuration speed.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-rails-hotwire`
**Sibling variant:** [rails-nextjs](../rails-nextjs/PRIMER.md)

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

- Content platforms, marketplaces, social apps -- CRUD-centric domains where
  Rails conventions enable rapid development.
- Teams with Ruby expertise who want full-stack productivity without a
  separate frontend deployment.
- Server-rendered HTML with progressive enhancement -- real-time via Turbo
  Streams, minimal client-side JS.

### Not Ideal For

- Rich client-side interactivity (drag-and-drop, dashboards, complex wizards)
  -- choose rails-nextjs instead.
- Teams without Ruby experience.
- Microservices architectures -- Rails is a monolith framework.

### vs rails-nextjs

Choose rails-hotwire when server-rendered simplicity wins: content-heavy CRUD,
real-time via Turbo Streams, admin-facing tools. Choose rails-nextjs when you
need rich client-side interactivity: dashboards, drag-and-drop builders,
complex form wizards. Both share the same Rails backend patterns -- the
difference is the frontend delivery model.

---

## Architecture

```
Browser
  +-- Hotwire (Turbo Drive + Turbo Frames + Turbo Streams + Stimulus)
        |
        v (standard HTTP + Turbo Streams via WebSocket)
        |
  Rails 8 (Active Record, Action Cable, Action Mailer)
        |-- Solid Queue / Sidekiq (async jobs)
        |-- Postgres 16 (data)
        |-- Redis 7 (cache, sessions, Action Cable, Sidekiq broker if used)
        |-- OpenSearch / MeiliSearch (full-text search, optional)
        +-- MinIO (S3-compatible via Active Storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Rails 8 | Convention-over-configuration, batteries-included, rapid development |
| Frontend | Hotwire (Turbo + Stimulus) | Server-rendered HTML with progressive enhancement, no build step for JS |
| API | None (HTML over the wire) | Rails views serve HTML; Turbo handles dynamic updates |
| ORM | Active Record | Mature, tightly integrated with Rails, excellent migration system |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Solid Queue (Rails 8 default) | Database-backed, no Redis dependency for jobs, zero-config |
| Auth | Devise or Rails 8 auth generator | Session-based (httpOnly cookies), battle-tested |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Action Mailer (prod) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `ApplicationRecord` + `Auditable` concern | `created_by`/`updated_by` via `Current.user` |
| Soft deletes | `SoftDeletable` concern | `deleted_at`/`deleted_by`, default scope excludes deleted |
| External IDs (no integer PKs) | `ExternalId` concern (`uuid` column) | Never expose integer PKs in URLs |
| API contract | Rails controllers + ERB views | HTML over the wire; Turbo Streams for dynamic updates |
| MutationResult pattern | Controller flash + Turbo Stream responses | `turbo_stream` for success/error feedback |
| Auth (session-based) | Devise or Rails 8 auth generator | httpOnly cookies, server-side sessions |
| Permissions (group-based) | Pundit policies | `authorize @record` in controllers |
| Background jobs | Solid Queue (Active Job) | Database-backed, `ApplicationJob` base class |
| Forms engine | `FormDefinition` model + Stimulus | JSON Schema, server-side validation |
| Workflow engine | AASM gem + Active Job actions | JSON states/transitions, polymorphic association |
| Feature toggles | `config/features.rb` + env vars | Module-level gating |
| Admin panel | ActiveAdmin or Administrate | Model registration, custom pages |
| Testing framework | RSpec + FactoryBot + Capybara | Request specs + system specs |
| Linter/Formatter | RuboCop | `.rubocop.yml` |
| Package manager | Bundler | `Gemfile` + `Gemfile.lock` |
| Migrations | Active Record migrations | `rails db:migrate` |

---

## Pattern: Models & ORM

All business models inherit from `ApplicationRecord` and include shared
concerns. `Current.user` (thread-safe `ActiveSupport::CurrentAttributes`)
provides the audit context.

```ruby
# app/models/concerns/auditable.rb -- created_by/updated_by via Current.user
module Auditable
  extend ActiveSupport::Concern
  included do
    belongs_to :created_by, class_name: "User", optional: true
    belongs_to :updated_by, class_name: "User", optional: true
    before_create { self.created_by ||= Current.user }
    before_save   { self.updated_by = Current.user }
  end
end

# app/models/concerns/soft_deletable.rb -- never call .destroy
module SoftDeletable
  extend ActiveSupport::Concern
  included do
    belongs_to :deleted_by, class_name: "User", optional: true
    default_scope { where(deleted_at: nil) }
    scope :with_deleted, -> { unscope(where: :deleted_at) }
  end
  def soft_delete! = update!(deleted_at: Time.current, deleted_by: Current.user)
end

# app/models/concerns/external_id.rb -- UUID, never expose integer PKs
module ExternalId
  extend ActiveSupport::Concern
  included { before_create { self.uuid ||= SecureRandom.uuid } }
end

# app/models/product.rb
class Product < ApplicationRecord
  include Auditable, SoftDeletable, ExternalId
  validates :name, presence: true
  validates :price, numericality: { greater_than: 0 }
end
```

---

## Pattern: API Layer

No separate API layer for the frontend. Rails controllers serve HTML. Turbo
handles dynamic updates. A separate `Api::V1` namespace for mobile/third-party
if needed.

```ruby
class ProductsController < ApplicationController
  before_action :authenticate_user!
  before_action :set_product, only: [:show, :edit, :update, :destroy]

  def index
    authorize Product
    @products = policy_scope(Product).order(created_at: :desc)
  end

  def create
    @product = Product.new(product_params)
    authorize @product
    if @product.save
      respond_to do |format|
        format.html { redirect_to @product, notice: "Product created." }
        format.turbo_stream
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def destroy
    authorize @product
    @product.soft_delete!
    redirect_to products_path, notice: "Product deleted."
  end

  private
  def set_product = @product = Product.find_by!(uuid: params[:id])
  def product_params = params.require(:product).permit(:name, :price, :category_id)
end
```

**Turbo Frame** (lazy loading), **Turbo Stream** (real-time), **Stimulus**
(client behavior):
```erb
<%= turbo_frame_tag "products", src: products_path, loading: :lazy %>
<%= turbo_stream.prepend "products", partial: "products/product", locals: { product: @product } %>
```
```javascript
import { Controller } from "@hotwired/stimulus"
export default class extends Controller {
  static targets = ["menu"]
  toggle() { this.menuTarget.classList.toggle("hidden") }
}
```

---

## Pattern: Auth

Devise with session-based auth. Sessions stored server-side, delivered as
httpOnly cookies. `Current.user` populated via `before_action` in
`SetCurrentAttributes` concern.

```ruby
module SetCurrentAttributes
  extend ActiveSupport::Concern
  included { before_action :set_current_attributes }
  private
  def set_current_attributes
    Current.user = current_user
    Current.request_id = request.request_id
  end
end
```

SHA256-hashed session tokens (raw to client, hash to DB). Rate limiting via
`rack-attack`. Server-side revocation is instant.

---

## Pattern: Permissions

Pundit policies. Group-based -- never user-based. No exceptions.

```ruby
# Group has_and_belongs_to_many :users, :permissions
# Permission validates :slug, presence: true, uniqueness: true

class ApplicationPolicy
  attr_reader :user, :record
  def initialize(user, record) = (@user, @record = user, record)
  private
  def has?(slug) = user.groups.joins(:permissions).exists?(permissions: { slug: slug })
end

class ProductPolicy < ApplicationPolicy
  def index?   = has?("product.view")
  def create?  = has?("product.add")
  def update?  = has?("product.change")
  def destroy? = has?("product.delete")
  class Scope < ApplicationPolicy::Scope
    def resolve = has?("product.view") ? scope.all : scope.none
  end
end
```

Controller: `authorize @product`. View: `<% if policy(Product).create? %>`.
Assign permissions to groups in admin, never directly to users.

---

## Pattern: Background Jobs

Solid Queue (Rails 8 default) -- database-backed, no Redis dependency for
jobs.

```ruby
class ApplicationJob < ActiveJob::Base
  retry_on StandardError, wait: :polynomially_longer, attempts: 5
  discard_on ActiveJob::DeserializationError
end

class ProcessInvoiceJob < ApplicationJob
  queue_as :default
  retry_on InvoiceProcessingError, wait: 1.minute, attempts: 3
  def perform(invoice_id) = Invoice.find(invoice_id).process!
end

# Dispatching
ProcessInvoiceJob.perform_later(invoice.id)
```

Mission Control mounted at `/jobs` for monitoring.

---

## Pattern: Forms Engine

JSON Schema definitions rendered at runtime. Same concept as other stacks.

`FormDefinition` model with versioned JSON Schema (draft -> published ->
archived). `FormSubmission` stores submitted data as JSON. Server-side
validation via custom validator. Stimulus controllers handle conditional
logic (show/hide/require). ERB partials render each field type. Adding a
field type: add to `FormFieldTypes::TYPES`, create ERB partial, add
Stimulus config panel to builder.

---

## Pattern: Workflow Engine

JSON-defined state machines attached to any model via polymorphic association.

`WorkflowDefinition` stores states and transitions as JSON.
`WorkflowInstance` tracks current state via polymorphic association.
`TransitionLog` provides an immutable audit trail.
`WorkflowTransitionService` evaluates conditions, updates state in a
transaction, logs the transition, and enqueues actions via Active Job.
AASM gem for state management.

**Condition types:** `user_has_role`, `field_equals`, `field_in`,
`is_authenticated`, `is_superuser`.
**Action types:** `notify_user`, `send_email`, `call_webhook`, `update_field`.

---

## Pattern: Feature Toggles

```ruby
module Features
  FORMS     = ENV.fetch("FEATURE_FORMS", "false") == "true"
  WORKFLOWS = ENV.fetch("FEATURE_WORKFLOWS", "false") == "true"
  SEARCH    = ENV.fetch("FEATURE_SEARCH", "false") == "true"
end
# Usage: if Features::FORMS then mount routes, load models, show UI links
```

Tied to Docker Compose profiles for optional services.

---

## Pattern: Admin

ActiveAdmin with Pundit integration. Auth-gated via `authenticate_admin_user!`
checking admin group membership. Pundit adapter for per-model authorization.

```ruby
ActiveAdmin.register Product do
  permit_params :name, :price, :category_id
  index do
    selectable_column
    column :uuid; column :name; column :price; column :created_at
    actions
  end
end
```

---

## Pattern: Testing

RSpec with FactoryBot. Real database, not mocks.

```ruby
RSpec.describe "Products", type: :request do
  let(:user) { create(:user, :with_product_permissions) }
  before { sign_in user }

  it "creates a product" do
    expect {
      post products_path, params: { product: { name: "Widget", price: 9.99 } }
    }.to change(Product, :count).by(1)
    expect(Product.last.name).to eq("Widget")
    expect(Product.last.created_by).to eq(user)
  end
end

RSpec.describe "Products (unauthorized)", type: :request do
  let(:user) { create(:user) }
  before { sign_in user }
  it "denies access" do
    expect {
      post products_path, params: { product: { name: "X", price: 1 } }
    }.to raise_error(Pundit::NotAuthorizedError)
  end
end
```

System specs with Capybara for full-stack browser testing.

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via request specs, not isolated model tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `boilerworks-rails` (Rails + Puma) | 3000 | `/up` (Rails 8 built-in) |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Solid Queue Worker | Same image, `bin/jobs` entrypoint | -- | -- |
| Mission Control | Same image, mounted at `/jobs` | -- | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |
| Search | opensearch:2 or meilisearch (optional) | 9200/7700 | -- |

No separate frontend container -- Hotwire is served by Rails. Solid Queue
runs as a separate process from the same image (`bin/jobs` entrypoint).

---

## Pattern: CI/CD

GitHub Actions: lint (RuboCop + ERB Lint), test (RSpec with Postgres + Redis
services), audit (`bundle audit` + `brakeman`), assets (`rails
assets:precompile`). CI must pass before merge.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens, httpOnly cookies, secure in
prod, sameSite lax. 30-day expiry. CORS restricted. `rack-attack` rate
limiting.

**Authorization:** Pundit `authorize` in every action. `policy_scope` for
queries. Ownership checks on mutations.

**Input validation:** Strong parameters + model validations. Brakeman for
static analysis.

**SSRF protection:** Block private IPs, localhost, non-HTTP schemes on
outgoing requests.

**File uploads:** Active Storage with MIME whitelist, size limits, filename
sanitization.

**Rails 8 defaults:** `config.force_ssl`, encrypted credentials, CSRF
protection via authenticity tokens.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Linting | RuboCop | `.rubocop.yml` |
| Max line length | 120 | `.rubocop.yml` |
| ERB linting | ERB Lint | `.erb-lint.yml` |
| Pre-commit | Lefthook | `.lefthook.yml` |

Two-space indent. snake_case methods. CamelCase classes.

---

## What Carries Over

### Shared Infrastructure (reusable as-is, identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- CI pipeline structure (lint, test, audit jobs)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Shared Concepts (same mental model, Rails implementation)

- Permission model (group-based, Pundit maps to Boilerworks pattern)
- Forms engine (JSON Schema, same field types, same lifecycle)
- Workflow engine (same state machine, same condition/action types)
- Audit trail (`created_by`/`updated_by` via `Current.user`)
- Agent shim pattern (same interface, Ruby implementation)

### Needs Porting (same concept, new implementation)

- ORM concerns and base model (Active Record replaces Django ORM)
- Session auth (Devise replaces auth1 app)
- Permission middleware (Pundit replaces custom permission system)
- Job queue (Solid Queue replaces Celery)
- Admin panel (ActiveAdmin replaces Django Admin)
- Form/workflow builder widgets (Stimulus replaces React/vanilla JS)

---

## Build Order

### Phase 0: Scaffolding
- [ ] Rails 8 + Active Record + Hotwire + Tailwind CSS
- [ ] ApplicationRecord + Auditable, SoftDeletable, ExternalId concerns
- [ ] Docker Compose (Rails, Postgres, Redis, MinIO, Mailpit)
- [ ] Health check (`/up`), RuboCop config

### Phase 1: Auth + Permissions
- [ ] Devise session auth, SetCurrentAttributes concern
- [ ] User, Group, Permission models + seed data
- [ ] Pundit policies, rack-attack, session token hashing

### Phase 2: Core CRUD
- [ ] RESTful controllers with Turbo Stream/Frame responses
- [ ] Stimulus controllers (dropdowns, modals, form validation)
- [ ] Audit logging via Auditable concern

### Phase 3: Forms Engine
- [ ] FormDefinition + FormSubmission models, field types, validation
- [ ] Logic engine, dynamic form renderer (ERB + Stimulus)
- [ ] Form builder (Stimulus + drag-and-drop)

### Phase 4: Workflow Engine
- [ ] WorkflowDefinition + WorkflowInstance + TransitionLog models
- [ ] WorkflowTransitionService, Active Job action processors
- [ ] Workflow builder (Stimulus + Turbo Frames)

### Phase 5: Infrastructure + Polish
- [ ] Active Storage + MinIO, Action Mailer + Mailpit
- [ ] In-app notifications (Turbo Streams via Action Cable)
- [ ] Feature toggles, Solid Queue + Mission Control, ActiveAdmin
- [ ] Seed data, CI pipeline, README, CLAUDE.md, bootstrap.md
