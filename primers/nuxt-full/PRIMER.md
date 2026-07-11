# Boilerworks Nuxt Full -- Primer

> Nuxt 4 on Cloudflare Pages. Full-stack Vue at the edge with Nitro
> server engine, auto-imports, and zero-config deployment. Choose this
> for Vue teams wanting edge deployment with server-side capabilities.

**Status:** Planned (Tier 4)
**Repo:** `ConflictHQ/boilerworks-nuxt-full`
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

- Vue teams wanting a full-stack edge framework with SSR, API routes,
  and database access in one project. Nuxt 4 + Nitro makes this seamless.
- Applications that benefit from auto-imports, file-based routing, and
  Vue 3 Composition API -- Nuxt handles the glue so you write less code.
- Globally distributed apps where Cloudflare's edge network provides
  low latency without managing infrastructure.

### Not Ideal For

- Teams without Vue experience. The Nuxt conventions (auto-imports,
  server/ directory, composables) assume Vue knowledge.
- Apps that need heavy backend infrastructure (complex job queues,
  multi-tenant permissions). Use a dedicated backend template.
- React or Svelte teams. See remix-full or sveltekit-full.

---

## Architecture

```
Browser
  |
  v (HTTPS)
  |
Nuxt 4 (Cloudflare Pages via Nitro)
  |-- server/api/ (API routes)
  |-- pages/ (SSR + client hydration)
  |-- composables/ (shared logic, auto-imported)
  |-- D1 or Turso (database)
  |-- R2 (file storage)
  |-- KV (sessions, cache)
  +-- Tailwind CSS
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | Nuxt 4 + Vue 3 Composition API | Full-stack, SSR, auto-imports, DX |
| Server | Nitro | Edge-native, multi-preset, auto-scanned API routes |
| Database | D1 (SQLite) or Turso | Edge-native, zero config |
| Cache/Sessions | Cloudflare KV | Globally distributed key-value |
| Storage | Cloudflare R2 | S3-compatible, no egress fees |
| Auth | nuxt-auth-utils or custom | Session-based, httpOnly cookies |
| Styling | Tailwind CSS | Utility-first, tree-shaken |
| Deploy | Cloudflare Pages | Nitro `cloudflare-pages` preset |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | D1 table with `created_at`/`updated_at`/`created_by`/`updated_by` | |
| Soft deletes | `deleted_at`/`deleted_by` columns | Filtered in queries |
| External IDs (no integer PKs) | UUID primary keys | `crypto.randomUUID()` |
| API contract | server/api/ routes (REST) | Auto-scanned by Nitro |
| MutationResult pattern | `{ok, errors, data}` response shape | |
| Auth (session-based) | nuxt-auth-utils or custom KV sessions | httpOnly cookies |
| Permissions (group-based) | DB-backed groups + permissions | Checked in server middleware |
| Background jobs | Cloudflare Queues | No Redis needed |
| Forms engine | Phase 2 | |
| Workflow engine | Phase 2 | |
| Feature toggles | Env vars | `runtimeConfig` in `nuxt.config.ts` |
| Admin panel | Custom admin pages | Auth-gated `/admin` section |
| Testing framework | vitest + @nuxt/test-utils | Unit + integration |
| Linter/Formatter | Prettier + ESLint (@nuxt/eslint) | Standard |
| Package manager | npm or pnpm | `package.json` |
| Migrations | D1 migrations (SQL files) | `wrangler d1 migrations apply` |

---

## Pattern: Models & ORM

D1 with raw SQL or Drizzle ORM. Same migration pattern as other edge
templates.

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
```

---

## Pattern: API Layer

Nitro auto-scans `server/api/` for route handlers. Nuxt provides
`useFetch` and `$fetch` for typed client-side data fetching.

```typescript
// server/api/items/index.post.ts
export default defineEventHandler(async (event) => {
  const user = await requireAuth(event);
  requirePermission(user, "items.create");

  const body = await readBody(event);
  const id = crypto.randomUUID();
  const db = hubDatabase();

  await db.prepare(
    "INSERT INTO items (id, name, created_by) VALUES (?, ?, ?)"
  ).bind(id, body.name, user.id).run();

  return { ok: true, data: { id } };
});

// server/api/items/index.get.ts
export default defineEventHandler(async (event) => {
  const user = await requireAuth(event);
  const db = hubDatabase();
  const { results } = await db.prepare(
    "SELECT * FROM items WHERE deleted_at IS NULL AND created_by = ?"
  ).bind(user.id).all();
  return { ok: true, data: results };
});
```

---

## Pattern: Auth

Session-based auth using nuxt-auth-utils or custom KV-backed sessions.

```typescript
// server/utils/auth.ts
export async function requireAuth(event: H3Event) {
  const session = await getUserSession(event);
  if (!session?.user) throw createError({ statusCode: 401, message: "Unauthorized" });
  return session.user;
}

// server/middleware/auth.ts
export default defineEventHandler(async (event) => {
  const session = await getUserSession(event);
  event.context.user = session?.user ?? null;
  event.context.permissions = session?.permissions ?? [];
});
```

---

## Pattern: Permissions

Group-based permissions checked in API route handlers.

```typescript
export function requirePermission(user: User, permission: string) {
  if (user.is_superuser) return;
  if (!user.permissions?.includes(permission)) {
    throw createError({ statusCode: 403, message: "Forbidden" });
  }
}
```

---

## Pattern: Background Jobs

Cloudflare Queues for async work, same as other edge templates.

---

## Pattern: Forms Engine

Phase 2.

---

## Pattern: Workflow Engine

Phase 2.

---

## Pattern: Feature Toggles

Runtime config via `nuxt.config.ts` and environment variables.

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: {
    featureAdmin: process.env.FEATURE_ADMIN === "true",
  },
});
```

---

## Pattern: Admin

Custom admin pages at `/admin`, auth-gated to superusers via middleware.

---

## Pattern: Testing

vitest with @nuxt/test-utils for server-side testing.

```typescript
import { describe, it, expect } from "vitest";
import { $fetch, setup } from "@nuxt/test-utils";

describe("POST /api/items", async () => {
  await setup({ server: true });

  it("creates item with valid auth", async () => {
    const resp = await $fetch("/api/items", {
      method: "POST",
      headers: { Cookie: await getTestSessionCookie() },
      body: { name: "Test item" },
    });
    expect(resp.ok).toBe(true);
    expect(resp.data.id).toBeDefined();
  });

  it("rejects unauthenticated request", async () => {
    const resp = await $fetch("/api/items", {
      method: "POST",
      body: { name: "Test" },
      ignoreResponseError: true,
    });
    expect(resp.statusCode).toBe(401);
  });
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Real D1 database -- never mock the database

---

## Pattern: Docker Infrastructure

**NOTE:** No Docker in production. Cloudflare Pages deploys via Wrangler
or git integration.

Local development uses `nuxi dev` with Nitro's built-in dev server.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Prettier + ESLint (@nuxt/eslint)
- **Test job:** vitest + @nuxt/test-utils
- **Deploy job:** Cloudflare Pages (Wrangler or git integration)
- **Audit job:** `npm audit`

---

## Pattern: Security

**Session hashing:** SHA256 before KV storage.

**Input validation:** Zod schemas in API route handlers.

**SSRF protection:** URL validator on outgoing fetch calls.

**CORS:** Nitro handles same-origin by default.

**CSRF:** Nuxt's built-in CSRF protection for form submissions.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier | `.prettierrc` |
| Linting | ESLint (@nuxt/eslint) | `eslint.config.js` |
| Type checking | `nuxi typecheck` | `tsconfig.json` |

---

## What Carries Over

### Shared Infrastructure (adapted for edge)

- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for nuxt-full)

- Nuxt 4 scaffold with Nitro cloudflare-pages preset
- Session auth with KV storage
- User, Group, Permission tables in D1
- Permission middleware and composables
- Admin section
- CI pipeline with Wrangler deploy

---

## Build Order

### Phase 0: Scaffolding
- [ ] Nuxt 4 project, Vue 3 Composition API, TypeScript
- [ ] Nitro cloudflare-pages preset, wrangler.toml
- [ ] D1 database, initial migrations
- [ ] Tailwind CSS, Prettier + ESLint

### Phase 1: Auth + Permissions
- [ ] User, Session tables in D1
- [ ] Session auth (login, logout, server middleware)
- [ ] Group, Permission tables + seed
- [ ] Permission checking in route handlers
- [ ] Auth-gated layouts and middleware

### Phase 2: Core App
- [ ] server/api/ routes with typed responses
- [ ] Page data loading with useFetch
- [ ] Form submissions with validation
- [ ] Audit logging

### Phase 3: Infrastructure + Polish
- [ ] File uploads (R2)
- [ ] Cloudflare Queues for async work
- [ ] Admin section
- [ ] Test suite (vitest + @nuxt/test-utils)
- [ ] CI pipeline (lint, test, deploy)
- [ ] README, CLAUDE.md
