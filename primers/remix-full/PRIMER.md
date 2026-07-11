# Boilerworks Remix Full -- Primer

> Remix on Cloudflare Workers. Server-first React at the edge with
> loader/action pattern, progressive enhancement, and built-in session
> helpers. Choose this for React teams wanting server-first architecture
> with edge deployment.

**Status:** Planned (Tier 4)
**Repo:** `ConflictHQ/boilerworks-remix-full`
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

- React teams that want server-first architecture. Remix's loader/action
  pattern keeps data fetching and mutations on the server, with
  progressive enhancement for free.
- Apps where forms and mutations are central. Remix's form handling
  with built-in validation, pending states, and optimistic UI is best
  in class.
- Edge deployment with React -- Remix on Cloudflare Workers gives you
  globally distributed SSR with the React ecosystem.

### Not Ideal For

- Teams that want SPA-style client-heavy React. Remix is opinionated
  about server-first -- if you want full client control, use Next.js
  with a backend template instead.
- Teams without React experience. The loader/action mental model is
  different from traditional React, but it still assumes React knowledge.
- Apps that don't need React at all. See sveltekit-full or nuxt-full
  for simpler alternatives.

---

## Architecture

```
Browser
  |
  v (HTTPS)
  |
Remix (Cloudflare Workers)
  |-- loader functions (data fetching, SSR)
  |-- action functions (mutations, form handling)
  |-- D1 or Turso (database)
  |-- R2 (file storage)
  |-- KV (sessions, cache)
  +-- Tailwind CSS
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | Remix + React | Server-first React, progressive enhancement |
| Data | Loaders (GET) + Actions (POST) | Colocated data fetching, no client waterfalls |
| Database | D1 (SQLite) or Turso | Edge-native, zero config |
| Cache/Sessions | Cloudflare KV | Remix session storage adapter |
| Storage | Cloudflare R2 | S3-compatible, no egress fees |
| Auth | Custom session-based (Remix session helpers) | httpOnly cookies, KV-backed |
| Styling | Tailwind CSS | Utility-first, tree-shaken |
| Deploy | Cloudflare Workers | Remix Cloudflare adapter |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | D1 table with `created_at`/`updated_at`/`created_by`/`updated_by` | |
| Soft deletes | `deleted_at`/`deleted_by` columns | Filtered in queries |
| External IDs (no integer PKs) | UUID primary keys | `crypto.randomUUID()` |
| API contract | Loaders + Actions | Colocated with routes |
| MutationResult pattern | Action return `{ok, errors}` | Consumed by `useActionData()` |
| Auth (session-based) | Remix `createCookieSessionStorage` + KV | httpOnly cookies |
| Permissions (group-based) | DB-backed groups + permissions | Checked in loaders/actions |
| Background jobs | Cloudflare Queues | No Redis needed |
| Forms engine | Phase 2 | |
| Workflow engine | Phase 2 | |
| Feature toggles | Env vars | Worker bindings |
| Admin panel | Custom admin routes | Auth-gated `/admin` section |
| Testing framework | vitest + Playwright | Unit + E2E |
| Linter/Formatter | Prettier + ESLint | Standard |
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

Remix uses loaders for data fetching and actions for mutations. Both
run on the server -- no separate API layer needed.

```typescript
// app/routes/items._index.tsx
export async function loader({ context, request }: LoaderFunctionArgs) {
  const user = await requireAuth(context, request);
  const db = context.cloudflare.env.DB;
  const { results } = await db.prepare(
    "SELECT * FROM items WHERE deleted_at IS NULL AND created_by = ?"
  ).bind(user.id).all();
  return json({ items: results });
}

export async function action({ context, request }: ActionFunctionArgs) {
  const user = await requireAuth(context, request);
  requirePermission(user, "items.create");

  const formData = await request.formData();
  const name = formData.get("name") as string;
  if (!name) return json({ ok: false, errors: [{ field: "name", message: "Required" }] }, 400);

  const id = crypto.randomUUID();
  const db = context.cloudflare.env.DB;
  await db.prepare(
    "INSERT INTO items (id, name, created_by) VALUES (?, ?, ?)"
  ).bind(id, name, user.id).run();

  return json({ ok: true, data: { id } });
}

export default function Items() {
  const { items } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  return (
    <Form method="post">
      {actionData?.errors && <Errors errors={actionData.errors} />}
      <input name="name" />
      <button type="submit">Add Item</button>
      <ul>{items.map((item) => <li key={item.id}>{item.name}</li>)}</ul>
    </Form>
  );
}
```

---

## Pattern: Auth

Session-based auth using Remix's built-in session helpers with KV storage.

```typescript
// app/services/session.server.ts
const sessionStorage = createCookieSessionStorage({
  cookie: {
    name: "__session",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    secrets: [SESSION_SECRET],
  },
});

export async function requireAuth(context: AppLoadContext, request: Request) {
  const session = await sessionStorage.getSession(request.headers.get("Cookie"));
  const tokenHash = session.get("tokenHash");
  if (!tokenHash) throw redirect("/login");

  const userData = await context.cloudflare.env.SESSIONS.get(tokenHash, "json");
  if (!userData) throw redirect("/login");
  return userData;
}
```

---

## Pattern: Permissions

Group-based permissions checked in loaders and actions.

```typescript
export function requirePermission(user: User, permission: string) {
  if (user.is_superuser) return;
  if (!user.permissions?.includes(permission)) {
    throw json({ message: "Forbidden" }, 403);
  }
}
```

---

## Pattern: Background Jobs

Cloudflare Queues for async work, same as other edge templates.

---

## Pattern: Forms Engine

Phase 2. Remix's form actions and `useActionData` provide a natural
foundation for a form engine.

---

## Pattern: Workflow Engine

Phase 2.

---

## Pattern: Feature Toggles

Environment variables via Worker bindings.

```typescript
// In a loader
if (context.cloudflare.env.FEATURE_ADMIN === "true") {
  // Enable admin features
}
```

---

## Pattern: Admin

Custom admin routes at `/admin`, auth-gated to superusers.

---

## Pattern: Testing

vitest for unit/integration, Playwright for E2E.

```typescript
// tests/e2e/items.test.ts
import { test, expect } from "@playwright/test";

test("create item flow", async ({ page }) => {
  await loginAs(page, "admin@example.com");
  await page.goto("/items");
  await page.fill('[name="name"]', "Test item");
  await page.click('button[type="submit"]');
  await expect(page.locator("li")).toContainText("Test item");
});

test("rejects unauthenticated access", async ({ page }) => {
  await page.goto("/items");
  await expect(page).toHaveURL("/login");
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Real D1 database -- never mock the database

---

## Pattern: Docker Infrastructure

**NOTE:** No Docker in production. Cloudflare Workers deploy via Wrangler.

Local development uses `remix vite:dev` with Wrangler's local bindings.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Prettier + ESLint
- **Test job:** vitest + Playwright
- **Deploy job:** Cloudflare Workers (Wrangler)
- **Audit job:** `npm audit`

---

## Pattern: Security

**Session hashing:** SHA256 before KV storage.

**CSRF protection:** Remix forms use POST by convention; same-origin
checks in Workers.

**Input validation:** Zod schemas in action functions.

**SSRF protection:** URL validator on outgoing fetch calls.

**CORS:** Workers handle same-origin by default.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier | `.prettierrc` |
| Linting | ESLint | `eslint.config.js` |
| Type checking | TypeScript | `tsconfig.json` |

---

## What Carries Over

### Shared Infrastructure (adapted for edge)

- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for remix-full)

- Remix scaffold with Cloudflare Workers adapter
- Session auth with KV storage and Remix session helpers
- User, Group, Permission tables in D1
- Permission checking in loaders/actions
- Admin section
- Playwright E2E test suite

---

## Build Order

### Phase 0: Scaffolding
- [ ] Remix project, Vite, TypeScript
- [ ] Cloudflare Workers adapter, wrangler.toml
- [ ] D1 database, initial migrations
- [ ] Tailwind CSS, Prettier + ESLint

### Phase 1: Auth + Permissions
- [ ] User, Session tables in D1
- [ ] Session auth (login, logout, cookie session storage)
- [ ] Group, Permission tables + seed
- [ ] Permission checking in loaders/actions
- [ ] Auth-gated layout routes

### Phase 2: Core App
- [ ] Loader/action patterns with typed responses
- [ ] Form handling with validation and error display
- [ ] Optimistic UI patterns
- [ ] Audit logging

### Phase 3: Infrastructure + Polish
- [ ] File uploads (R2)
- [ ] Cloudflare Queues for async work
- [ ] Admin section
- [ ] Playwright E2E tests
- [ ] CI pipeline (lint, test, deploy)
- [ ] README, CLAUDE.md
