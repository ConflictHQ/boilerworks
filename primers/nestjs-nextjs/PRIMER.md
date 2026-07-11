# Boilerworks NestJS + Next.js -- Primer

> Full TypeScript stack for enterprise apps that want type safety from database to browser. NestJS backend with Prisma ORM and Pothos GraphQL, Next.js frontend via shared reference.

**Status:** Done
**Repo:** `ConflictHQ/boilerworks-nestjs-nextjs`
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

- Full TypeScript teams that want a single language and type system from database schema to React components, with no context switching.
- Enterprise SaaS apps that need structured backend architecture -- NestJS gives you dependency injection, modules, guards, and interceptors out of the box.
- Projects where type safety across the entire stack is a hard requirement -- Prisma types flow through Pothos into GraphQL and out to Apollo Client.

### Not Ideal For

- Teams without TypeScript expertise -- NestJS has a steep learning curve (decorators, DI, modules) and rewards developers who already know the patterns.
- Simple CRUD apps that do not need the structural overhead of NestJS modules, services, and resolvers. A lighter framework would move faster.
- Projects where Python or Ruby expertise is the team's strength -- pick the django or rails stack instead.

NestJS only makes sense paired with Next.js in Boilerworks. There is no sibling variant.

---

## Architecture

```
Browser
  |
  v
Next.js 16 (App Router, SSR + CSR)
  |
  | Apollo Client (GraphQL over HTTP, httpOnly cookie auth)
  v
NestJS 11 (GraphQL Yoga + Pothos)
  |
  +---> Prisma ORM ---> Postgres 16
  +---> BullMQ -------> Redis 7
  +---> Nodemailer ----> Mailpit (dev) / SMTP (prod)
  +---> S3 SDK -------> MinIO (dev) / S3 (prod)
  +---> OpenSearch client --> OpenSearch (feature-gated)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | NestJS 11 | Modular, decorator-based, dependency injection, mature TypeScript ecosystem |
| Frontend | Next.js 16 | Shared across all GraphQL stacks (see NEXTJS_FRONTEND.md) |
| API | Pothos GraphQL (via GraphQL Yoga) | Code-first schema builder with best-in-class TS type inference |
| ORM | Prisma | Schema-first, type-safe queries, auto-generated client, Prisma Studio |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | BullMQ | Native Node.js job queues, retries, scheduled jobs, Bull Board dashboard |
| Auth | Auth0 + custom sessions (httpOnly cookies) | Auth0 for identity, backend sessions for API auth |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Nodemailer + Mailpit (dev) | Standard across all stacks |
| Search | OpenSearch (feature-gated) | Same engine as Django stack, Prisma fallback when disabled |

---

## Stack Mapping

How universal Boilerworks patterns map to this stack's implementation:

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `createdAt`, `updatedAt`, `createdById`, `updatedById` on all Prisma models | Convention, not a base class |
| Soft deletes | `deletedAt` field + Prisma Extension (`prisma/extensions/soft-delete.ts`) | Auto-filters `deletedAt IS NULL` on findMany/findFirst |
| External IDs (no integer PKs) | `cuid()` default on all `id` fields | `@id @default(cuid())` in schema.prisma |
| API contract | Pothos GraphQL (code-first, Prisma plugin, Relay plugin) | Types auto-mapped from Prisma schema |
| MutationResult pattern | `MutationResult { ok, errors }` simple object | All mutations return this type |
| Auth (session-based) | Auth0 callback + backend session + httpOnly cookie | SHA256 hashed token storage |
| Permissions (group-based) | User -> UserGroup -> Group -> GroupPermission -> Permission | Enum in `permissions/roles.enum.ts`, `PermissionsGuard` |
| Background jobs | BullMQ with 4 queues + `JobDispatcher` service | workflow-actions, email, webhooks, notifications |
| Forms engine | FormDefinition (versioned JSON Schema) + FormSubmission | Ajv validation, logic engine, 21+ field types |
| Workflow engine | WorkflowDefinition (JSON state machine) + WorkflowInstance + TransitionLog | Conditions + actions, BullMQ execution |
| Feature toggles | Env-based (`config/features.ts`) | Gates module registration + resolver execution |
| Admin panel | Prisma Studio at :5555 | Dev-only, Docker Compose service |
| Testing framework | Vitest + Supertest | Real database, no mocks |
| Linter/Formatter | Prettier + ESLint (`@typescript-eslint`) | Husky + lint-staged pre-commit |
| Package manager | npm workspaces + Turborepo | Monorepo with `apps/api`, `apps/web`, `packages/shared` |
| Migrations | `prisma migrate dev` / `prisma migrate deploy` | Schema-first, auto-generated SQL |

---

## Pattern: Models & ORM

Prisma uses a schema-first approach. There is no base class -- conventions are followed per model. Soft deletes are handled by a Prisma Extension, not by model inheritance.

### Schema conventions

```prisma
model Invoice {
  id          String    @id @default(cuid())
  name        String
  amount      Decimal
  status      String    @default("draft")
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  deletedAt   DateTime?                     // soft delete
  createdById String?
  updatedById String?

  organization   Organization? @relation(fields: [organizationId], references: [id])
  organizationId String?

  @@index([status])
  @@index([organizationId])
}
```

Rules:
- Every model has `id` (`cuid()`), `createdAt`, `updatedAt`
- Business models add `deletedAt` for soft deletes -- never call `prisma.model.delete()`
- Use `@@index` for any field used in filters or joins
- Use `@@unique` for natural keys (e.g., `[slug, version]`)
- Relations always specify `onDelete` behavior

### Soft delete extension

```typescript
// prisma/extensions/soft-delete.ts
const SOFT_DELETE_MODELS = [
  "FormDefinition", "WorkflowDefinition", "Upload", "Organization",
];

export const softDeleteExtension = Prisma.defineExtension({
  name: "soft-delete",
  query: {
    $allModels: {
      async findMany({ model, args, query }) {
        if (SOFT_DELETE_MODELS.includes(model)) {
          args.where = { ...args.where, deletedAt: null };
        }
        return query(args);
      },
      async findFirst({ model, args, query }) {
        if (SOFT_DELETE_MODELS.includes(model)) {
          args.where = { ...args.where, deletedAt: null };
        }
        return query(args);
      },
    },
  },
});
```

Applied via `PrismaService` which uses `$extends(softDeleteExtension)`. To soft-delete:

```typescript
await this.prisma.invoice.update({
  where: { id },
  data: { deletedAt: new Date(), updatedById: userId },
});
```

---

## Pattern: API Layer

Pothos GraphQL with Prisma plugin and Relay plugin, served via GraphQL Yoga.

### Schema builder

```typescript
// graphql/schema.ts
import SchemaBuilder from "@pothos/core";
import PrismaPlugin from "@pothos/plugin-prisma";
import RelayPlugin from "@pothos/plugin-relay";
import SimpleObjectsPlugin from "@pothos/plugin-simple-objects";

export const builder = new SchemaBuilder<{
  PrismaTypes: PrismaTypes;
  Context: GraphQLContext;
}>({
  plugins: [PrismaPlugin, RelayPlugin, SimpleObjectsPlugin],
  prisma: { client: prisma },
});
```

Types are registered via side-effect imports:

```typescript
import "./invoices/invoices.types"; // registers types on the builder
```

### Type definition (mapped from Prisma)

```typescript
// invoices/invoices.types.ts
builder.prismaObject("Invoice", {
  fields: (t) => ({
    id: t.exposeID("id"),
    name: t.exposeString("name"),
    amount: t.exposeFloat("amount"),
    status: t.exposeString("status"),
    createdAt: t.expose("createdAt", { type: "DateTime" }),
    submissions: t.relation("submissions"),
    submissionCount: t.relationCount("submissions"),
  }),
});
```

### Query

```typescript
builder.queryField("invoices", (t) =>
  t.prismaField({
    type: ["Invoice"],
    args: { status: t.arg.string({ required: false }) },
    resolve: (query, _root, args, ctx) => {
      requireAuth(ctx);
      requirePermission(ctx, "invoices.view");
      return ctx.prisma.invoice.findMany({
        ...query,
        where: args.status ? { status: args.status } : {},
        orderBy: { createdAt: "desc" },
      });
    },
  }),
);
```

### Mutation (always returns MutationResult)

```typescript
const MutationError = builder.simpleObject("MutationError", {
  fields: (t) => ({
    field: t.string({ nullable: true }),
    messages: t.stringList(),
  }),
});

const MutationResult = builder.simpleObject("MutationResult", {
  fields: (t) => ({
    ok: t.boolean(),
    errors: t.field({ type: [MutationError], nullable: true }),
  }),
});

builder.mutationField("createInvoice", (t) =>
  t.field({
    type: MutationResult,
    args: {
      name: t.arg.string({ required: true }),
      amount: t.arg.float({ required: true }),
    },
    resolve: async (_root, args, ctx) => {
      requireAuth(ctx);
      requirePermission(ctx, "invoices.create");
      const parsed = CreateInvoiceSchema.parse(args);
      await ctx.prisma.invoice.create({
        data: { ...parsed, createdById: ctx.user!.id },
      });
      return { ok: true, errors: null };
    },
  }),
);
```

### Context

```typescript
// graphql/context.ts
export type GraphQLContext = {
  user:
    | (User & {
        groups: Array<{
          group: { permissions: Array<{ permission: { slug: string } }> };
        }>;
      })
    | null;
  permissions: Set<string>;
  prisma: PrismaClient;
  req: Request;
};
```

Context is created per-request. Session token is read from the `backend_jwt` cookie or `Authorization: Bearer` header. User + permissions are loaded eagerly (includes groups -> permissions). `PrismaService` is injected to ensure the soft-delete extension is active.

### Auth check rule

Auth check at the top of every resolver and mutation. No exceptions:

```typescript
function requireAuth(
  ctx: GraphQLContext,
): asserts ctx is GraphQLContext & { user: User } {
  if (!ctx.user) throw new GraphQLError("Authentication required");
}
```

---

## Pattern: Auth

Auth0 for identity provider, custom session-based auth for API access. httpOnly cookies. No JWT stored client-side.

### Login flow

1. Frontend redirects to Auth0 universal login.
2. Auth0 callback hits backend with authorization code.
3. Backend exchanges code for Auth0 tokens (id_token + access_token).
4. Backend creates or finds local user, creates Session with SHA256-hashed token, sets httpOnly cookie with backend JWT.
5. Frontend uses cookie for all subsequent GraphQL requests.

### Session management

```typescript
// auth/auth.service.ts
import { createHash, randomBytes } from "crypto";

@Injectable()
export class AuthService {
  constructor(private prisma: PrismaService) {}

  async handleCallback(code: string): Promise<Session> {
    const auth0Tokens = await this.exchangeCode(code);
    const user = await this.findOrCreateUser(auth0Tokens);
    return this.createSession(user.id);
  }

  async createSession(userId: string): Promise<{ session: Session; rawToken: string }> {
    const rawToken = randomBytes(32).toString("hex");
    const tokenHash = createHash("sha256").update(rawToken).digest("hex");
    const session = await this.prisma.session.create({
      data: { userId, token: tokenHash, expiresAt: addDays(new Date(), 30) },
    });
    return { session, rawToken }; // rawToken sent to client, hash stored in DB
  }

  async validateSession(rawToken: string): Promise<User | null> {
    const tokenHash = createHash("sha256").update(rawToken).digest("hex");
    const session = await this.prisma.session.findUnique({
      where: { token: tokenHash },
      include: { user: true },
    });
    if (!session || session.expiresAt < new Date()) return null;
    return session.user;
  }
}
```

### Auth guard

```typescript
// common/guards/auth.guard.ts
@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private auth: AuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const ctx = GqlExecutionContext.create(context).getContext();
    const token = ctx.req.cookies?.backend_jwt;
    if (!token) return false;
    ctx.user = await this.auth.validateSession(token);
    return !!ctx.user;
  }
}
```

### Auth0 env vars

```
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=...
AUTH0_CLIENT_SECRET=...
AUTH0_CLIENT_SCOPES="openid profile email read:users create:users update:users"
AUTH0_DATABASE_CONNECTION_ID="Username-Password-Authentication"
```

### Additional auth flows

Password reset, email verification, and user invitation are all implemented with email delivery via Nodemailer.

---

## Pattern: Permissions

Group-based. Never assign permissions directly to users.

### Define permissions

```typescript
// permissions/roles.enum.ts
export enum P {
  INVOICE_VIEW = "invoices.view",
  INVOICE_CREATE = "invoices.create",
  INVOICE_EDIT = "invoices.edit",
  INVOICE_DELETE = "invoices.delete",
  FORM_VIEW = "forms.view",
  FORM_CREATE = "forms.create",
  WORKFLOW_VIEW = "workflows.view",
  WORKFLOW_MANAGE = "workflows.manage",
}
```

### Check in resolver (GraphQL)

```typescript
function requirePermission(ctx: GraphQLContext, slug: string) {
  requireAuth(ctx);
  if (ctx.permissions.has("*")) return; // superuser
  if (!ctx.permissions.has(slug)) {
    throw new GraphQLError("Permission denied");
  }
}
```

### NestJS guard (for REST endpoints)

```typescript
// permissions/permissions.decorator.ts
export const RequirePermission = (...slugs: string[]) =>
  SetMetadata("permissions", slugs);

// permissions/permissions.guard.ts
@Injectable()
export class PermissionsGuard implements CanActivate {
  constructor(private reflector: Reflector, private prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const required = this.reflector.get<string[]>("permissions", context.getHandler());
    if (!required?.length) return true;

    const ctx = GqlExecutionContext.create(context).getContext();
    const user = ctx.user;
    if (!user) return false;
    if (user.isSuperuser) return true;

    const count = await this.prisma.groupPermission.count({
      where: {
        permission: { slug: { in: required } },
        group: { users: { some: { userId: user.id } } },
      },
    });
    return count > 0;
  }
}
```

### Debug tools

- `permissionDiagnose(userId, action)` -- traces the permission chain and reports why access was granted or denied.
- `effectivePermissions(userId)` -- GraphQL query returning all resolved permission slugs for a user.

### Frontend guards

```tsx
// Server Component
await requirePermission(PermissionSlug.InvoiceView);

// Client Component
<PermissionGuard permission={PermissionSlug.InvoiceView}>
  <InvoiceList />
</PermissionGuard>
```

---

## Pattern: Background Jobs

BullMQ with Redis. 4 queues, 4 processors, 1 dispatcher service.

### Queue definitions

```typescript
// jobs/queues.ts
export const QUEUES = {
  WORKFLOW_ACTIONS: "workflow-actions",
  EMAIL: "email",
  WEBHOOKS: "webhooks",
  NOTIFICATIONS: "notifications",
} as const;
```

### Processor

```typescript
// jobs/workflow-action.processor.ts
@Processor("workflow-actions")
export class WorkflowActionProcessor {
  constructor(
    private prisma: PrismaService,
    private email: EmailService,
    private notifications: NotificationsService,
  ) {}

  @Process("execute")
  async handleAction(job: Job<WorkflowActionData>) {
    const { action, instanceId, fromState, toState, userId } = job.data;

    switch (action.type) {
      case "notify_user":
        await this.notifications.create(action.user, action.subject, action.message);
        break;
      case "send_email":
        await this.email.send(action.to, action.subject, action.message);
        break;
      case "call_webhook":
        await this.webhookService.deliver(action.url, {
          instanceId, fromState, toState, userId,
        });
        break;
      case "update_field":
        // Polymorphic field update via targetModel + targetId
        break;
    }
  }
}
```

### Dispatching from business logic

```typescript
// Fire-and-forget with configurable retries
await this.jobDispatcher.dispatch("workflow-actions", "execute", {
  instanceId,
  actionType,
  payload,
});
```

### Module registration

```typescript
// jobs/jobs.module.ts
@Module({
  imports: [PrismaModule],
  providers: [
    WorkflowActionProcessor,
    EmailProcessor,
    WebhookProcessor,
    NotificationProcessor,
    JobDispatcher,
    EmailService,
  ],
  exports: [JobDispatcher, EmailService],
})
export class JobsModule {}
```

### Monitoring

Bull Board at `/admin/queues` -- requires valid session + superuser. Redis connection parsed from `REDIS_URL` env var.

---

## Pattern: Forms Engine

JSON Schema definitions rendered at runtime. No code changes to add a new form.

**Backend:** `FormDefinition` model stores versioned JSON Schema. `field-types.ts` defines 21+ types. `logic-engine.ts` evaluates conditional rules (show/hide/require/calculate). Validation via Ajv.

**Frontend:** `DynamicForm` reads schema, `field-registry.tsx` maps types to widgets, React Hook Form manages state. `FormBuilder` provides @dnd-kit drag-and-drop editing with live preview and per-type config panels.

### Prisma model

```prisma
model FormDefinition {
  id                String    @id @default(cuid())
  name              String
  slug              String
  description       String?
  formType          String    @default("standard")
  status            String    @default("draft")    // draft, published, archived
  isPublic          Boolean   @default(false)
  version           Int       @default(1)
  schema            Json      @default("{}")
  fieldConfig       Json      @default("{}")
  logicRules        Json      @default("[]")
  scoring           Json?
  publishedAt       DateTime?
  createdAt         DateTime  @default(now())
  updatedAt         DateTime  @updatedAt
  deletedAt         DateTime?
  createdById       String?

  submissions       FormSubmission[]

  @@unique([slug, version])
  @@index([slug])
  @@index([status])
}
```

### Validation

```typescript
const ajv = new Ajv();
const validate = ajv.compile(formDefinition.schema);
if (!validate(payload)) {
  return { ok: false, errors: formatAjvErrors(validate.errors) };
}
```

### Field types

text, textarea, number, integer, boolean, date, datetime, time, email, url, select, multi_select, radio, file, signature, rating, scale, pin, text_block, section_header, page_break, image, percentage_split, repeatable, user_lookup

---

## Pattern: Workflow Engine

JSON-defined state machines attached to any model via `targetModel` + `targetId`.

### Data model

**State:** `{ name, label, is_initial, is_final, color, form_slug?, assigned_role? }`
**Transition:** `{ from_state, to_state, label, conditions[], actions[] }`

**Condition types:** `user_has_role`, `field_equals`, `field_in`, `is_authenticated`, `is_superuser`
**Action types:** `notify_user`, `send_email`, `call_webhook`, `update_field`

### Service pattern

```typescript
// Start workflow
const instance = await workflowService.start(workflow, targetModel, targetId, user);

// Transition
await workflowService.transition(instanceId, "approved", user, "Looks good");

// Check available transitions
const available = await workflowService.getAvailableTransitions(instanceId, user);
```

Actions execute via BullMQ -- fire-and-forget with configurable retries.

### Rule engine

Condition evaluator with 8 operators, AND logic, model/trigger filtering. Used by workflows and available as a standalone service for other conditional logic needs.

### Visual builder

Next.js `WorkflowBuilder` -- ReactFlow canvas, click-to-edit panels for states and transitions, conditions/actions editors, form picker for attaching forms to states, role assignment via TagInput.

---

## Pattern: Feature Toggles

Env-based toggles that gate module registration and resolver execution.

```typescript
// config/features.ts
export const features = {
  forms: envBool("FEATURE_FORMS", true),
  workflows: envBool("FEATURE_WORKFLOWS", true),
  search: envBool("FEATURE_SEARCH", false),
  temporal: envBool("FEATURE_TEMPORAL", false),
};
```

### Module gating

```typescript
// app.module.ts
@Module({
  imports: [
    AuthModule,
    UsersModule,
    ...(features.forms ? [FormsModule] : []),
    ...(features.workflows ? [WorkflowsModule] : []),
  ],
})
export class AppModule {}
```

### Resolver gating

```typescript
import { requireFeature } from "../config/features";

// Throws FEATURE_DISABLED if flag is off
requireFeature("forms");
```

Setting `FEATURE_FORMS=false` removes forms types and resolvers from the GraphQL schema entirely. The `features` GraphQL query returns all flag states to the frontend.

---

## Pattern: Admin

Prisma Studio serves as the admin panel. Dev-only, runs as a Docker Compose service on port 5555.

```yaml
# docker/docker-compose.yaml
prisma-studio:
  build:
    context: ../apps/api
  command: npx prisma studio --port 5555
  ports:
    - "5555:5555"
  environment:
    DATABASE_URL: postgresql://dbadmin:dbadmin@postgres:5432/boilerworks
  depends_on:
    postgres:
      condition: service_healthy
```

No custom admin panel. Prisma Studio provides visual CRUD, filtering, and relation browsing for all models. For production admin needs, the app's own UI with superuser permissions serves that role.

---

## Pattern: Testing

Vitest + Supertest. Real database, no mocks.

```typescript
describe("createInvoice", () => {
  it("creates and persists an invoice", async () => {
    const res = await request(app.getHttpServer())
      .post("/graphql")
      .set("Cookie", `backend_jwt=${testSession.rawToken}`)
      .send({
        query: `mutation { createInvoice(name: "Test", amount: 100) { ok } }`,
      });

    expect(res.body.data.createInvoice.ok).toBe(true);

    // Assert against database state -- not hardcoded strings
    const invoice = await prisma.invoice.findFirst({
      where: { name: "Test" },
    });
    expect(invoice).toBeTruthy();
    expect(invoice!.amount).toBe(100);
    expect(invoice!.createdById).toBe(testUser.id);
  });

  it("denies unauthenticated access", async () => {
    const res = await request(app.getHttpServer())
      .post("/graphql")
      .send({
        query: `mutation { createInvoice(name: "Test", amount: 100) { ok } }`,
      });

    expect(res.body.errors[0].message).toContain("Authentication");
  });

  it("denies access without required permission", async () => {
    const res = await request(app.getHttpServer())
      .post("/graphql")
      .set("Cookie", `backend_jwt=${unprivilegedSession.rawToken}`)
      .send({
        query: `mutation { createInvoice(name: "Test", amount: 100) { ok } }`,
      });

    expect(res.body.errors[0].message).toContain("Permission denied");
  });
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via API layer, not isolated model tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| API | `docker/Dockerfile.api` | 4000 | HTTP GET /health |
| Frontend | `docker/Dockerfile.web` | 3000 | HTTP GET / |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Worker | Same as API, `node dist/worker.js` | -- | -- |
| Bull Board | Served by API at `/admin/queues` | 4000 | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |
| OpenSearch | opensearchproject/opensearch | 9200 | Feature-gated |
| Prisma Studio | Same as API, `npx prisma studio` | 5555 | -- |

Source directories are volume-mounted for hot reload (src/, prisma/, app/, components/). Containers have their own node_modules (not mounted from host). After adding new npm deps, rebuild: `docker compose up --build`.

### Command center

```bash
./run.sh up           # Start everything
./run.sh stop         # Stop everything
./run.sh logs         # Tail API logs
./run.sh migrate      # Run Prisma migrations
./run.sh seed         # Load dev fixtures
./run.sh test         # Run test suite
./run.sh lint         # Run linters
./run.sh health       # Check service health
```

---

## Pattern: CI/CD

GitHub Actions with 4 jobs:

- **lint:** `npm run lint` + `npm run format:check`
- **audit:** `npm audit --omit=dev --audit-level=critical` (blocks on critical vulns only)
- **build:** Prisma generate, migrate, `nest build`, `next build` (with Postgres + Redis services)
- **test:** Prisma generate, migrate, seed, `vitest --run` (with Postgres + Redis services)

---

## Pattern: Security

### Session token hashing

Sessions are hashed with SHA256 before storage. Raw token is returned to the client, hash is stored in the database. Same pattern used for API keys.

### API keys

Service account tokens (`bw_live_...`) with hashed storage and scoped permissions. Keys are never stored in plaintext.

### SSRF protection

`common/url-validator.ts` exports `validateWebhookUrl()`. Must be called before any outgoing HTTP request (webhooks, workflow actions). Blocks localhost, private IPs (10.x, 172.16-31.x, 192.168.x, 127.x), and non-HTTP schemes.

### GraphQL depth limiting

Max depth 10 via custom validation rule (`graphql/depth-limit.ts`). Introspection disabled in production. Error messages are masked in production to avoid leaking internals.

### Ownership checks

Every mutation that modifies a user-owned resource must verify `record.createdById === ctx.user!.id` (or allow superusers). Pattern established in `uploads.resolver.ts` and `notifications.resolver.ts`.

### Webhook delivery

Outgoing webhooks are HMAC-signed. The webhook delivery service computes an HMAC signature over the payload and includes it in the request headers so receivers can verify authenticity.

### Env validation

All env vars validated at startup via Zod (`config/env.ts`). App fails fast on missing or invalid config. No silent defaults for required values.

### Other measures

- **CORS:** Configured in `main.ts`, allowed origins from `CORS_ORIGINS` env var
- **Helmet:** HTTP security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- **Cookies:** httpOnly, secure (prod), sameSite: lax
- **Rate limiting:** Per-endpoint, configurable via decorator
- **Input validation:** Zod at API boundaries, Ajv for JSON Schema forms
- **No raw SQL:** Always use Prisma query builder
- **Upload validation:** MIME type whitelist, filename sanitization (strips `..`, null bytes, path separators), 50MB size limit
- **Bull Board:** Protected at `/admin/queues` -- requires valid session + superuser

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier (with `prettier-plugin-tailwindcss`) | `.prettierrc` |
| Linting | ESLint with `@typescript-eslint` | `.eslintrc` |
| Max line length | Managed by Prettier (default 100) | |
| Import sorting | ESLint import plugin | |
| Pre-commit hooks | Husky + lint-staged | `.husky/`, `lint-staged` in package.json |
| TypeScript | Strict mode (`strict: true`, `noImplicitAny: true`) | `tsconfig.json` |

```bash
npm run format        # Format all files
npm run format:check  # Check formatting
npm run lint          # Lint all files
npm run test          # Run tests
```

---

## What Carries Over

### Frontend (~80% reuse)

The Next.js frontend is backend-agnostic. See `NEXTJS_FRONTEND.md` for the full reference. The following are shared identically with `django-nextjs`:

- `components/ui/` -- entire shadcn/ui library
- `components/forms/` -- DynamicForm, FormBuilder, field-registry, logic-engine
- `components/workflows/` -- WorkflowBuilder with TagInput
- `components/data-table/` -- DataTable, DataTableServer
- `hooks/` -- useDebounce, useLocalStorage, useCopyToClipboard, useConfirm
- `lib/apollo/` -- cache config, error link, auth link
- `graphql/` -- query/mutation/hook structure
- `app/(app)/` -- page layouts, dashboard, sidebar, breadcrumbs
- `messages/` -- i18n translations (7 languages)

### Shared code (packages/shared)

- Form field type registry (TypeScript enums + types)
- Workflow condition/action type system
- Permission slug enum

### Shared infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs porting (same concept, different implementation vs Django)

- ORM layer: Django ORM -> Prisma schema + extensions
- GraphQL: Strawberry (decorators) -> Pothos (builder pattern)
- Background jobs: Celery -> BullMQ
- Auth: Django sessions -> Auth0 + custom sessions
- Validation: DRF serializers -> Zod + Ajv
- Testing: pytest + BaseTest -> Vitest + Supertest
- Admin: Django Admin -> Prisma Studio
- Polymorphic FK: GenericForeignKey -> `targetModel` + `targetId` strings

---

## Build Order

All phases are complete.

### Phase 0: Scaffolding

- [x] Monorepo setup (Turborepo -- `apps/api`, `apps/web`, `packages/shared`)
- [x] NestJS app with Prisma, Pothos, BullMQ
- [x] Next.js app (App Router, Apollo Client, shadcn/ui)
- [x] Docker Compose (postgres, redis, minio, mailpit, opensearch, prisma-studio)
- [x] Health check, Zod-based env validation (`config/env.ts`)
- [x] `run.sh` command center

### Phase 1: Auth + Permissions

- [x] Auth0 SSO + password fallback
- [x] Session auth with SHA256 token hashing (login, logout, callback)
- [x] Auth guard for GraphQL context
- [x] User, Group, Permission models + seed
- [x] Permission guard (`requirePermission` + `PermissionsGuard`)
- [x] Permission debug tools (`permissionDiagnose`, `effectivePermissions`)
- [x] Frontend auth gate + permission guards
- [x] Password reset, email verification, user invitation flows

### Phase 2: Core GraphQL

- [x] Pothos schema builder with Prisma plugin + Relay plugin + SimpleObjects
- [x] Context (user, session, permissions, prisma)
- [x] MutationResult pattern (ok + errors)
- [x] Audit log model + query with filters
- [x] GraphQL depth limiting (max 10)
- [x] Introspection disabled in production

### Phase 3: Forms Engine

- [x] Prisma models (FormDefinition, FormSubmission)
- [x] 21+ field types + JSON Schema validation (Ajv)
- [x] Logic engine (conditions, calculations)
- [x] GraphQL CRUD + public form submissions + analytics
- [x] Frontend: DynamicForm, FormBuilder, field-registry

### Phase 4: Workflow Engine

- [x] Prisma models (WorkflowDefinition, WorkflowInstance, TransitionLog)
- [x] State machine service (transition, conditions, actions)
- [x] Rule engine (8 operators, AND logic, model/trigger filtering)
- [x] BullMQ processors for actions
- [x] GraphQL CRUD + start/transition mutations
- [x] Frontend: WorkflowBuilder (ReactFlow canvas)

### Phase 5: Infrastructure + Extensions

- [x] File uploads (S3/MinIO presigned URLs, ownership verification)
- [x] Email service (Nodemailer + templates + Mailpit)
- [x] Notifications (in-app CRUD, unread count, mark read)
- [x] Webhooks (HMAC-signed outgoing delivery)
- [x] CSV import/export
- [x] Organization multi-tenancy (Organization + OrganizationMember with roles)
- [x] API keys (hashed storage, scoped permissions, `bw_live_...` prefix)
- [x] OpenSearch (feature-gated, Prisma fallback)
- [x] SSRF protection (`validateWebhookUrl`)
- [x] Feature toggles (env-based, gates modules + resolvers)
- [x] Bull Board monitoring (superuser-gated)

### Phase 6: Polish

- [x] Seed data + example forms/workflows
- [x] Prisma Studio admin (Docker Compose service)
- [x] README, CLAUDE.md, bootstrap.md
- [x] CI pipeline (lint, audit, build, test)
- [x] `run.sh` DX command center
- [x] GraphQL schema export
