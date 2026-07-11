# Boilerworks Hono Micro -- Primer

> Hono on Cloudflare Workers. Lightweight edge API with globally
> distributed low-latency responses. No Docker in production -- Wrangler
> CLI for dev and deploy. Choose this for edge APIs and Cloudflare-first
> infrastructure.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-hono-micro`
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

- Edge APIs that need globally distributed, low-latency responses
  without managing servers. Cloudflare Workers run in 300+ locations.
- Cloudflare-first infrastructure: D1 for database, KV for caching,
  R2 for storage, Queues for async work -- all integrated, all managed.
- Lightweight services (webhooks, proxies, API gateways) where cold
  start time and per-request cost matter.

### Not Ideal For

- Services that need long-running processes or persistent connections.
  Workers have a CPU time limit per request.
- Teams that need full Postgres. D1 is SQLite -- simpler, but no
  advanced Postgres features (JSONB operators, CTEs with write, etc.).
- Applications that will grow into user-facing products with complex
  auth. Start with sveltekit-full or remix-full instead.

---

## Architecture

```
Caller (browser, service, webhook sender)
  |
  v (HTTP + API key or Cloudflare Access)
  |
Hono (Cloudflare Workers runtime)
  |-- D1 (SQLite at the edge) or Turso (distributed SQLite)
  |-- Cloudflare KV (key-value cache)
  |-- Cloudflare R2 (S3-compatible storage)
  |-- Cloudflare Queues (async work)
  +-- Health check at /health
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Hono (Web Standards API) | Fast, lightweight, built for Workers |
| API | REST (JSON) | Standard HTTP handlers |
| Database | D1 (SQLite) or Turso | Edge-native, zero config |
| Cache | Cloudflare KV | Globally distributed key-value |
| Queue | Cloudflare Queues | Async work without Redis |
| Storage | Cloudflare R2 | S3-compatible, no egress fees |
| Auth | API-key middleware or Cloudflare Access | SHA256-hashed keys |
| Deploy | Wrangler CLI | `wrangler deploy` |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | D1 table with `created_at`/`updated_at` | No user references |
| Soft deletes | `deleted_at` column | `WHERE deleted_at IS NULL` |
| External IDs (no integer PKs) | UUID primary keys | `crypto.randomUUID()` |
| API contract | REST (JSON) | Hono handlers |
| MutationResult pattern | `ApiResponse` object | `{ok, message, errors}` |
| Auth | API-key middleware | SHA256 hashing via Web Crypto |
| Permissions | Key-level scopes | Middleware checks |
| Background jobs | Cloudflare Queues | Producer/consumer pattern |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars (wrangler.toml) | `env.FEATURE_X` |
| Admin panel | None | Keep it lean |
| Testing framework | vitest + miniflare | Local Workers simulator |
| Linter/Formatter | Prettier + ESLint | Standard |
| Package manager | npm or pnpm | `package.json` |
| Migrations | D1 migrations (SQL files) | `wrangler d1 migrations apply` |

---

## Pattern: Models & ORM

D1 uses SQLite syntax. Migrations are plain SQL files applied via Wrangler.

```sql
-- migrations/0001_create_api_keys.sql
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    last_used_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

No ORM by default. Raw SQL with D1's prepared statements. Drizzle ORM
is an option if you want type-safe queries.

---

## Pattern: API Layer

Hono handlers with typed JSON responses.

```typescript
interface ApiResponse<T = unknown> {
  ok: boolean;
  message?: string;
  data?: T;
  errors?: { field: string; message: string }[];
}

app.post("/webhooks", apiKeyAuth(), async (c) => {
  const payload = await c.req.json();
  // Process...
  return c.json<ApiResponse>({ ok: true, message: "Processed" });
});
```

---

## Pattern: Auth

API-key middleware using Web Crypto API for SHA256 hashing.

```typescript
function apiKeyAuth(): MiddlewareHandler {
  return async (c, next) => {
    const key = c.req.header("X-API-Key");
    if (!key) return c.json<ApiResponse>({ ok: false, message: "API key required" }, 401);

    const keyHash = await sha256Hex(key);
    const row = await c.env.DB.prepare(
      "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1"
    ).bind(keyHash).first();

    if (!row) return c.json<ApiResponse>({ ok: false, message: "Invalid API key" }, 401);

    c.set("apiKey", row);
    await next();
  };
}

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
```

---

## Pattern: Permissions

Optional per-key scopes checked inline.

```typescript
function requireScope(scope: string): MiddlewareHandler {
  return async (c, next) => {
    const apiKey = c.get("apiKey");
    const scopes: string[] = JSON.parse(apiKey.scopes);
    if (!scopes.includes("*") && !scopes.includes(scope)) {
      return c.json<ApiResponse>({ ok: false, message: "Missing scope" }, 403);
    }
    await next();
  };
}
```

---

## Pattern: Background Jobs

Cloudflare Queues for async work. No Redis needed.

```typescript
// Producer: send to queue from a handler
await c.env.WEBHOOK_QUEUE.send({ event: "order.created", data: payload });

// Consumer: process queue messages in a separate export
export default {
  async queue(batch: MessageBatch, env: Env) {
    for (const msg of batch.messages) {
      await processWebhook(env, msg.body);
      msg.ack();
    }
  },
};
```

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

Environment variables defined in `wrangler.toml`.

```typescript
if (c.env.FEATURE_MONITORING === "true") {
  app.route("/monitoring", monitoringRouter);
}
```

---

## Pattern: Admin

None. Hono micro stays lean. Manage API keys via Wrangler D1 console
or seed script.

---

## Pattern: Testing

vitest with miniflare for local Workers simulation.

```typescript
import { env } from "cloudflare:test";
import { describe, it, expect } from "vitest";
import app from "../src/index";

describe("POST /webhooks", () => {
  it("accepts valid API key", async () => {
    await seedApiKey(env.DB, "test-key", ["*"]);
    const resp = await app.request("/webhooks", {
      method: "POST",
      headers: { "X-API-Key": "test-key", "Content-Type": "application/json" },
      body: JSON.stringify({ event: "order.created" }),
    }, env);
    expect(resp.status).toBe(200);
    const body = await resp.json();
    expect(body.ok).toBe(true);
  });

  it("rejects missing API key", async () => {
    const resp = await app.request("/webhooks", { method: "POST" }, env);
    expect(resp.status).toBe(401);
  });
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both valid and invalid API key cases
- Integration tests via HTTP handlers
- Real D1 database via miniflare -- never mock the database

---

## Pattern: Docker Infrastructure

**NOTE:** No Docker in production. Wrangler CLI deploys directly to
Cloudflare Workers.

Docker Compose for local development only (optional):

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Wrangler dev | `node:22-alpine` + wrangler | 8787 | `GET /health` |

Most developers will use `wrangler dev` directly without Docker.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Prettier + ESLint
- **Test job:** vitest with miniflare
- **Deploy job:** `wrangler deploy` (staging/production)
- **Audit job:** `npm audit`

---

## Pattern: Security

**API key hashing:** SHA256 via Web Crypto API. Never store plaintext.

**Rate limiting:** Cloudflare Rate Limiting rules or custom middleware
with KV counters.

**Input validation:** Zod or manual validation at handler boundaries.

**SSRF protection:** URL validator on outgoing fetch calls.

**CORS:** Hono CORS middleware with explicit origin whitelist.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier | `.prettierrc` |
| Linting | ESLint | `eslint.config.js` |

---

## What Carries Over

### Shared Infrastructure (adapted for edge)

- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for hono-micro)

- Hono project scaffold with Cloudflare Workers bindings
- API-key middleware using Web Crypto API
- D1 schema and migrations
- Cloudflare Queues consumer
- Wrangler configuration (`wrangler.toml`)
- CI pipeline with Wrangler deploy

---

## Build Order

### Phase 0: Scaffolding
- [ ] Hono app, Wrangler config, TypeScript setup
- [ ] D1 database, initial migration
- [ ] Health check, Prettier + ESLint config
- [ ] vitest + miniflare test setup

### Phase 1: Auth
- [ ] ApiKey table + D1 queries
- [ ] API-key middleware
- [ ] Key creation seed script
- [ ] Optional scope checking

### Phase 2: Core API
- [ ] REST handlers with JSON responses
- [ ] `ApiResponse` wrapper
- [ ] Input validation (Zod)
- [ ] Cloudflare Queues integration

### Phase 3: Infrastructure + Polish
- [ ] Rate limiting
- [ ] CI pipeline (lint, test, deploy)
- [ ] README, CLAUDE.md
