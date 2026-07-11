# Boilerworks SvelteKit Full -- Primer

> SvelteKit on Cloudflare Pages. Full-stack edge app with the simplest
> developer experience -- one framework, one language, one deploy target.
> Server routes for API, SSR for pages, Svelte 5 runes for reactivity.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-sveltekit-full`
**Sibling variant:** None

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

- Full-stack edge apps where a single framework handles API, SSR, and
  UI with minimal boilerplate. SvelteKit has the simplest DX of any
  full-stack framework.
- Teams wanting modern reactive UI without React's complexity. Svelte 5
  runes are straightforward and produce smaller bundles.
- Globally distributed apps where edge rendering and low latency matter.

### Not Ideal For

- Apps that need heavy backend infrastructure (background jobs, complex
  permissions, workflow engines). Use a full-stack template with a
  dedicated backend instead.
- Teams with existing React or Vue expertise who don't want to learn
  Svelte. See remix-full or nuxt-full.
- Enterprise environments that require JVM, .NET, or Python backends.

---

## Architecture

```
Browser
  |
  v (HTTPS)
  |
SvelteKit (Cloudflare Pages)
  |-- +page.server.ts (SSR data loading)
  |-- +server.ts (API routes)
  |-- adapter-cloudflare
  |-- D1 or Turso (database)
  |-- R2 (file storage)
  |-- KV (sessions, cache)
  +-- Tailwind CSS
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | SvelteKit + Svelte 5 | Full-stack, SSR + SPA, smallest bundle sizes |
| Rendering | SSR (edge) + client hydration | Fast first paint, interactive after hydration |
| API | +server.ts routes | Colocated API, typed with TypeScript |
| Database | D1 (SQLite) or Turso | Edge-native, zero config |
| Cache/Sessions | Cloudflare KV | Globally distributed key-value |
| Storage | Cloudflare R2 | S3-compatible, no egress fees |
| Auth | Custom session-based or Cloudflare Access | httpOnly cookies |
| Styling | Tailwind CSS | Utility-first, tree-shaken |
| Deploy | Cloudflare Pages | `adapter-cloudflare` |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | D1 table with `created_at`/`updated_at`/`created_by`/`updated_by` | |
| Soft deletes | `deleted_at`/`deleted_by` columns | Filtered in queries |
| External IDs (no integer PKs) | UUID primary keys | `crypto.randomUUID()` |
| API contract | +server.ts (REST) + +page.server.ts (SSR) | Typed with TypeScript |
| MutationResult pattern | `ActionResult` from form actions | `{ok, errors}` |
| Auth (session-based) | KV-backed sessions, httpOnly cookies | Custom middleware in hooks |
| Permissions (group-based) | DB-backed groups + permissions | Checked in load/action functions |
| Background jobs | Cloudflare Queues | No Redis needed |
| Forms engine | Phase 2 | |
| Workflow engine | Phase 2 | |
| Feature toggles | Env vars | Platform env in `wrangler.toml` |
| Admin panel | Custom admin routes | Auth-gated `/admin` section |
| Testing framework | vitest + Playwright | Unit + E2E |
| Linter/Formatter | Prettier + ESLint + svelte-check | Standard |
| Package manager | npm or pnpm | `package.json` |
| Migrations | D1 migrations (SQL files) | `wrangler d1 migrations apply` |

---

## Pattern: Models & ORM

D1 with raw SQL or Drizzle ORM for type safety.

```sql
-- migrations/0001_create_users.sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    is_superuser INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## Pattern: API Layer

SvelteKit has two API patterns: `+page.server.ts` for page data loading
and `+server.ts` for standalone API endpoints.

```typescript
// src/routes/api/items/+server.ts
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ locals, request, platform }) => {
  if (!locals.user) return new Response(JSON.stringify({ ok: false }), { status: 401 });

  const body = await request.json();
  const id = crypto.randomUUID();
  await platform.env.DB.prepare(
    "INSERT INTO items (id, name, created_by) VALUES (?, ?, ?)"
  ).bind(id, body.name, locals.user.id).run();

  return Response.json({ ok: true, data: { id } });
};

// src/routes/items/+page.server.ts
export const load = async ({ locals, platform }) => {
  if (!locals.user) throw redirect(303, "/login");
  const { results } = await platform.env.DB.prepare(
    "SELECT * FROM items WHERE deleted_at IS NULL AND created_by = ?"
  ).bind(locals.user.id).all();
  return { items: results };
};
```

---

## Pattern: Auth

Session-based auth with KV-backed sessions and httpOnly cookies.
Validated in SvelteKit hooks.

```typescript
// src/hooks.server.ts
export const handle: Handle = async ({ event, resolve }) => {
  const token = event.cookies.get("session");
  if (token) {
    const tokenHash = await sha256Hex(token);
    const session = await event.platform.env.SESSIONS.get(tokenHash, "json");
    if (session && new Date(session.expires_at) > new Date()) {
      event.locals.user = session.user;
      event.locals.permissions = session.permissions;
    }
  }
  return resolve(event);
};
```

---

## Pattern: Permissions

Group-based permissions checked in load/action functions.

```typescript
function requirePermission(locals: App.Locals, permission: string) {
  if (!locals.user) throw redirect(303, "/login");
  if (locals.user.is_superuser) return;
  if (!locals.permissions?.includes(permission)) throw error(403, "Forbidden");
}

// In a +page.server.ts
export const load = async ({ locals, platform }) => {
  requirePermission(locals, "items.view");
  // ...
};
```

---

## Pattern: Background Jobs

Cloudflare Queues for async work.

```typescript
await platform.env.EMAIL_QUEUE.send({
  to: user.email,
  template: "welcome",
  data: { name: user.name },
});
```

---

## Pattern: Forms Engine

Phase 2. SvelteKit's form actions provide a natural foundation for
building a JSON Schema-driven form renderer.

---

## Pattern: Workflow Engine

Phase 2.

---

## Pattern: Feature Toggles

Environment variables via `wrangler.toml` or Cloudflare dashboard.

```typescript
// src/hooks.server.ts
if (event.platform.env.FEATURE_ADMIN === "true") {
  // Register admin routes
}
```

---

## Pattern: Admin

Custom admin routes at `/admin`, auth-gated to superusers.

---

## Pattern: Testing

vitest for unit/integration tests, Playwright for E2E.

```typescript
// tests/e2e/login.test.ts
import { test, expect } from "@playwright/test";

test("login flow", async ({ page }) => {
  await page.goto("/login");
  await page.fill('[name="email"]', "admin@example.com");
  await page.fill('[name="password"]', "password");
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL("/dashboard");
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Real D1 database via miniflare -- never mock the database

---

## Pattern: Docker Infrastructure

**NOTE:** No Docker in production. Cloudflare Pages deploys via Wrangler
or git integration.

Docker Compose for local development only (optional):

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| SvelteKit dev | `node:22-alpine` + wrangler | 5173 | HTTP check |

Most developers will use `wrangler pages dev` or `npm run dev` directly.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Prettier + ESLint + svelte-check
- **Test job:** vitest + Playwright
- **Deploy job:** Cloudflare Pages (via Wrangler or git integration)
- **Audit job:** `npm audit`

---

## Pattern: Security

**Session hashing:** SHA256 via Web Crypto before KV storage.

**CSRF protection:** SvelteKit's built-in origin checking for form actions.

**Input validation:** Zod schemas at API boundaries.

**SSRF protection:** URL validator on outgoing fetch calls.

**CORS:** SvelteKit handles same-origin by default; explicit config for
cross-origin API routes.

**Content Security Policy:** Set via Cloudflare Pages headers or SvelteKit hooks.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier | `.prettierrc` |
| Linting | ESLint + svelte plugin | `eslint.config.js` |
| Type checking | svelte-check | `tsconfig.json` |

---

## What Carries Over

### Shared Infrastructure (adapted for edge)

- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for sveltekit-full)

- SvelteKit scaffold with adapter-cloudflare
- Session auth with KV storage
- User, Group, Permission tables in D1
- Permission checking in hooks and load functions
- Admin section with superuser gate
- Playwright E2E test suite
- Wrangler configuration

---

## Build Order

### Phase 0: Scaffolding
- [ ] SvelteKit project, Svelte 5 runes, TypeScript
- [ ] adapter-cloudflare, wrangler.toml
- [ ] D1 database, initial migrations
- [ ] Tailwind CSS, Prettier + ESLint + svelte-check
- [ ] Health check

### Phase 1: Auth + Permissions
- [ ] User, Session tables in D1
- [ ] Session auth (login, logout, hooks middleware)
- [ ] Group, Permission tables + seed
- [ ] Permission checking in load/action functions
- [ ] Auth-gated layout

### Phase 2: Core App
- [ ] +server.ts API routes with typed responses
- [ ] +page.server.ts SSR data loading
- [ ] Form actions with validation
- [ ] Audit logging (created_by, updated_by)

### Phase 3: Infrastructure + Polish
- [ ] File uploads (R2)
- [ ] Cloudflare Queues for async work
- [ ] Admin section
- [ ] Playwright E2E tests
- [ ] CI pipeline (lint, test, deploy)
- [ ] README, CLAUDE.md
