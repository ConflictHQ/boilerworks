# Boilerworks Saleor + Next.js -- Primer

> E-commerce template built on Saleor 3.x with a Next.js 16 storefront.
> Choose this for online stores, marketplaces, and any project that needs
> product catalog, cart, checkout, and payment processing out of the box.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-saleor-nextjs`
**Sibling variant:** None (dedicated e-commerce template)

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
9. [Pattern: E-Commerce Domain](#pattern-e-commerce-domain)
10. [Pattern: Storefront](#pattern-storefront)
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

- E-commerce projects that need product catalog, cart, checkout, and payments
  out of the box -- online stores, marketplaces, subscription boxes.
- Teams familiar with Django/Python who want a modern, API-first commerce
  platform without building order management from scratch.
- Multi-channel, multi-currency storefronts where Saleor's channel system
  handles regional pricing, taxes, and shipping without custom code.

### Not Ideal For

- Non-e-commerce projects -- use django-nextjs or another template. Saleor's
  entire data model is commerce-specific and will fight you otherwise.
- Simple storefronts that do not need Saleor's full feature set -- consider
  Shopify or a lightweight headless CMS with Stripe Checkout instead.
- Teams that need extreme customization of the checkout or order workflow
  beyond what Saleor supports through its plugin/app system.

---

## Architecture

```
Browser
  |-- Storefront (Next.js 16 -- customer-facing)
  |     +-- Apollo Client --> Saleor GraphQL API
  |
  +-- Dashboard (Saleor Dashboard -- staff/admin)
        +-- Built-in React app --> Saleor GraphQL API
              |
              v
        Saleor 3.x (Django + Strawberry GraphQL)
              |-- Celery (async tasks: order processing, email, webhooks)
              |-- Postgres 16 (products, orders, customers, inventory)
              |-- Redis 7 (cache, sessions, broker)
              +-- MinIO / S3 (product images, digital goods)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Saleor 3.x (Django + Strawberry) | Full commerce engine: products, orders, checkout, payments, inventory |
| Frontend | Next.js 16 | App Router, Server Components, streaming |
| API | Saleor GraphQL (Strawberry) | Saleor provides the schema; you query and extend |
| ORM | Django ORM (via Saleor) | Saleor manages models; extend with plugins/apps |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Celery + Redis | Saleor built-in: order processing, emails, webhooks |
| Auth | Saleor built-in | JWT for storefront, sessions for dashboard, social login |
| Storage | MinIO (S3-compatible) | Product images, digital goods, invoices |
| Email | Mailpit (dev) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Saleor built-in models | Extend via plugins, not custom base classes |
| Soft deletes | Saleor handles internally | Products unpublished; orders never deleted |
| External IDs | Saleor GraphQL global IDs | Relay-style; never expose integer PKs |
| API contract | Saleor GraphQL schema | Saleor provides it; storefront queries it |
| MutationResult | Saleor error types | `errors { field, message, code }` on every mutation |
| Auth | Saleor JWT + refresh tokens | Storefront JWT; dashboard sessions |
| Permissions | Saleor permission system | Staff, app, and channel-scoped permissions |
| Background jobs | Celery (Saleor built-in) | Order processing, webhook dispatch, email |
| Forms engine | N/A | Saleor uses its own attributes system |
| Workflow engine | N/A | Saleor has built-in order/fulfillment workflows |
| Feature toggles | Saleor plugins + env-based | Toggle payment gateways, shipping, etc. |
| Admin panel | Saleor Dashboard | Separate React app for staff operations |
| Testing | pytest + Playwright | Backend integration + storefront E2E |
| Linter/Formatter | Ruff + Prettier/ESLint | Backend + storefront |
| Package manager | uv + pnpm | Backend + storefront |
| Migrations | Django migrations (via Saleor) | Custom plugins have own migrations |

---

## Pattern: Models & ORM

Saleor provides the commerce data model. You extend via plugins and metadata,
not by building models from scratch.

**Core models:** `Product`, `ProductVariant`, `ProductType`, `Category`,
`Collection`, `Order`, `OrderLine`, `Fulfillment`, `Checkout`, `CheckoutLine`,
`Address`, `User`, `Warehouse`, `Stock`, `Allocation`, `Channel`.

**Extending:** Custom plugin models live in your plugin directory with their
own migrations. For lightweight extension, use Saleor's metadata (key-value
store on most models: `store_value_in_metadata()` for public,
`store_value_in_private_metadata()` for staff-only). Never modify Saleor core
models directly.

---

## Pattern: API Layer

Saleor provides the GraphQL schema. Custom logic is added through plugins and
apps, not by building resolvers.

**Storefront queries** use Relay-style pagination with `edges/node/pageInfo`.
Channel is required on most product queries.

**Checkout mutations** (`checkoutCreate`, `checkoutLinesAdd`,
`checkoutShippingAddressUpdate`, `checkoutComplete`, etc.) each return the
updated checkout object and an `errors` array.

Every mutation returns `errors { field, message, code }`. Error codes:
`REQUIRED`, `INVALID`, `NOT_FOUND`, `INSUFFICIENT_STOCK`.

For complex extensions, build a Saleor App (separate service) that
communicates via webhooks and the Saleor API.

---

## Pattern: Auth

Saleor handles authentication. Storefront uses JWT; dashboard uses sessions.

**Storefront flow:** `tokenCreate` returns access token (short-lived JWT) and
refresh token. Access token sent as `Authorization: Bearer <token>`. Refresh
via `tokenRefresh`. Social login via OpenID Connect plugin. Access token kept
in-memory (Apollo reactive variable, never localStorage). Refresh token as
httpOnly cookie via Next.js API route proxy.

---

## Pattern: Permissions

Saleor's built-in permission system. Staff permissions assigned to groups,
never directly to users. Customer accounts access only their own data.

**Staff permissions:** `MANAGE_PRODUCTS`, `MANAGE_ORDERS`,
`MANAGE_CUSTOMERS`, `MANAGE_SHIPPING`, `MANAGE_DISCOUNTS`,
`MANAGE_PLUGINS`, `MANAGE_STAFF`, `MANAGE_SETTINGS`, `MANAGE_CHECKOUTS`,
`MANAGE_APPS`, `MANAGE_CHANNELS`, `HANDLE_PAYMENTS`. Staff can be
channel-scoped. Customers access only their own data -- Saleor enforces
ownership at the resolver level.

---

## Pattern: Background Jobs

Celery with Redis broker, managed by Saleor.

**Built-in tasks:** order confirmation emails, webhook delivery (with retry),
thumbnail generation, export jobs (CSV). Custom plugin tasks use
`@shared_task` with standard Celery patterns (bind, max_retries, countdown).
Celery Beat for periodic tasks. Flower at `localhost:5555` for monitoring.

---

## Pattern: E-Commerce Domain

Core Saleor concepts the team must understand.

**Products and Variants.** `ProductType` defines attributes. Products have
one or more variants (size, color) carrying SKU, price, and stock. Attributes:
dropdown, multiselect, numeric, rich text, file, date, boolean, swatch.

**Categories** are hierarchical (tree); one per product. **Collections** are
curated groups (many per product); used for promotions and merchandising.

**Channels.** Each channel has its own currency, country, product availability,
and pricing. Orders belong to a channel.

**Checkout:** `CheckoutCreate` --> add lines --> shipping address --> shipping
method --> billing address --> payment --> `checkoutComplete` (atomic order
creation). Each step is a separate mutation.

**Payments.** Saleor payment apps (Stripe, PayPal, Adyen) communicate via
webhooks. Saleor manages the payment state machine (pending, authorized,
captured, refunded, cancelled).

**Orders.** Fulfillment (ship, track, partial). Refunds (full/partial).
Returns (customer-initiated, staff-approved).

**Warehouses.** Per-warehouse stock, allocation during checkout, click-and-collect.

**Webhooks.** `ORDER_CREATED`, `ORDER_PAID`, `PRODUCT_UPDATED`,
`CUSTOMER_CREATED`, payment events, fulfillment events.

**Translations.** Multi-language per locale for products, attributes,
categories, collections, pages.

---

## Pattern: Storefront

The storefront differs significantly from the generic dashboard frontend in
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md). Same tech stack (App Router,
Apollo, shadcn/ui, Tailwind, next-intl) but commerce-specific structure.

**Route groups:** `(shop)/` for public storefront (products, categories,
collections, cart, checkout, search), `(shop)/account/` for auth-gated
customer pages (orders, addresses, profile), `(auth)/` for login/register,
`api/` for token proxy and webhook receivers.

**Components:** `product/` (ProductCard, ProductGrid, VariantSelector),
`cart/` (CartDrawer, CartLine, CartSummary), `checkout/` (AddressForm,
ShippingMethodPicker, PaymentForm), `layout/` (Header, Footer, Navigation).

**GraphQL:** `products/`, `checkout/`, `orders/`, `account/` -- each with
types, queries/mutations, and hooks files.

**Lib:** Apollo Client setup, `channels.ts` (currency/locale context),
`checkout.ts` (checkout ID in cookie), `formatters.ts` (price/date).

**Product pages:** Server Components fetch data. Filters are URL-driven for
SSR and shareability. Variant selection is client-side.

**Cart:** Checkout ID stored in a cookie (persists for guests). `checkoutCreate`
on first add-to-cart; `checkoutLinesAdd` for subsequent items. Cart drawer in
the layout.

**Checkout:** Multi-step (address, shipping, payment, confirmation). Each
step validates via Saleor mutations before proceeding.

**Search:** Saleor built-in or Algolia for larger catalogs. URL params for
SSR. Debounced input.

---

## Pattern: Feature Toggles

Env-based: `FEATURE_ALGOLIA_SEARCH=true`, `FEATURE_LOYALTY_PROGRAM=true`.
Saleor plugins enabled/disabled via dashboard or env vars. Custom features
follow the same env-based pattern as other stacks, tied to Docker Compose
profiles.

---

## Pattern: Admin

Saleor Dashboard ships as a Docker service. Covers product, order, customer,
catalog, channel, staff, plugin, and site management. You do not build the
admin. For custom pages, build a Saleor App that embeds via App Bridge SDK.

---

## Pattern: Testing

**Backend** -- pytest against a real Saleor instance. Test custom plugin
logic, model behavior, and Saleor API integration with real database fixtures.

**Storefront E2E** -- Playwright against running Saleor + storefront. Cover
product browsing, cart operations, full checkout flow, and account pages.

**Rules (universal):** Assert against database state, not hardcoded strings.
No empty test bodies. Test both allowed and denied permission cases.
Integration tests via API layer. Real database -- never mock.

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Saleor API | `saleor` (Django + Gunicorn) | 8000 | `/health/` |
| Storefront | `storefront` (Next.js) | 3000 | HTTP check |
| Dashboard | `saleor-dashboard` (React) | 9003 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Celery Worker | Same as Saleor API, different entrypoint | -- | -- |
| Celery Beat | Same as Saleor API, different entrypoint | -- | -- |
| Flower | mher/flower | 5555 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

---

## Pattern: CI/CD

`Makefile` targets: `make lint`, `make test`, `make build`, `make e2e`.

GitHub Actions: lint, build (Docker images), test (pytest + Playwright E2E
against seeded Saleor), audit. CI must pass before merge.

---

## Pattern: Security

**Auth:** Short-lived JWT (5 min), refresh tokens as httpOnly cookies via
Next.js API proxy, CORS restricted to storefront and dashboard origins.

**Authorization:** Saleor enforces permissions on every query/mutation.
Group-based staff permissions. Ownership-scoped customer access.

**Payments:** Card data never touches Saleor -- goes directly to payment
provider (Stripe Elements, PayPal SDK). Transaction references only.

**GraphQL:** Depth limiting, introspection disabled in prod, cost analysis,
rate limiting on auth/checkout. Saleor validates inputs at the GraphQL layer.
File uploads through Saleor media handling (MIME whitelist, size limits).

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Backend formatting/linting | Ruff | `pyproject.toml` |
| Backend max line length | 140 | `pyproject.toml` |
| Backend import sorting | Ruff (isort rules) | `pyproject.toml` |
| Storefront formatting | Prettier | `.prettierrc` |
| Storefront linting | ESLint | `.eslintrc.js` |
| Pre-commit hooks | Ruff + Prettier | `.pre-commit-config.yaml` |

Run `make lint` before committing.

---

## What Carries Over

### From django-nextjs (reusable patterns)

- Next.js frontend patterns (App Router, Apollo, shadcn/ui, Tailwind, i18n).
- Docker Compose infra (Postgres, Redis, MinIO, Mailpit, Celery, Flower).
- CI pipeline structure, agent shim, health checks, feature toggles.
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`.

### What Does NOT Carry Over

- **Django backend replaced by Saleor.** No `Tracking`/`BaseCoreModel`, no
  `auth1`, no `config/permissions.py`. You extend Saleor, not build from scratch.
- **No forms or workflow engines.** Saleor has its own attributes system and
  built-in order/fulfillment workflows.
- **Storefront is commerce-specific.** Product pages, cart, checkout, and
  account flows differ entirely from the generic dashboard frontend.

---

## Build Order

### Phase 0: Scaffolding
- [ ] Saleor in Docker (API + Dashboard)
- [ ] Next.js storefront with Apollo
- [ ] Docker Compose
- [ ] Health checks
- [ ] Seed data (test channel, product types, sample products)

### Phase 1: Storefront Core
- [ ] Product listing/detail pages
- [ ] Category and collection navigation
- [ ] Search
- [ ] Header/footer/nav
- [ ] i18n, dark mode

### Phase 2: Cart and Checkout
- [ ] Cart management + drawer
- [ ] Multi-step checkout
- [ ] Guest checkout
- [ ] Stripe payment app

### Phase 3: Customer Accounts
- [ ] Registration/login
- [ ] JWT management with httpOnly cookie proxy
- [ ] Order history
- [ ] Addresses, profile

### Phase 4: Saleor Customization
- [ ] Custom plugin scaffolding
- [ ] Webhook integration
- [ ] Saleor App skeleton
- [ ] Multi-channel
- [ ] Translations

### Phase 5: Infrastructure
- [ ] Playwright E2E + pytest
- [ ] CI pipeline
- [ ] Production Docker
- [ ] Seed data script
- [ ] README, CLAUDE.md, bootstrap.md
