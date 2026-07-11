# Boilerworks NestJS Micro -- Primer

> Lightweight NestJS microservice with API-key auth. No users, no sessions, no
> frontend. Choose this for TypeScript microservices that need NestJS's DI,
> module system, and decorator-based architecture.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-nestjs-micro`
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

- TypeScript teams that want a structured, enterprise-grade microservice
  framework with dependency injection, decorators, and a strong module system.
- Services that will integrate with other NestJS applications or use NestJS
  microservice transports (Redis, NATS, gRPC, Kafka).
- Internal APIs and webhook processors where NestJS's guard/interceptor/pipe
  architecture provides clean separation of concerns.

### Not Ideal For

- Simple services where NestJS's abstractions add unnecessary overhead. Choose
  a lighter framework or [go-micro](../go-micro/PRIMER.md).
- Applications with user accounts and a frontend. Choose
  [nestjs-nextjs](../nestjs-nextjs/PRIMER.md) instead.
- Teams unfamiliar with NestJS's decorator-heavy, Angular-inspired patterns.

---

## Architecture

```
Caller (service, cron, webhook sender)
  |
  v (HTTP + API key in header)
  |
NestJS 11 (TypeScript, Fastify or Express)
  |-- Prisma (Postgres)
  |-- Redis (optional, for caching or message transport)
  +-- Swagger UI at /api/docs
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | NestJS 11 (TypeScript) | DI, modules, decorators, enterprise structure |
| API | REST (NestJS controllers) | Swagger auto-generated |
| ORM | Prisma | Type-safe queries, auto-generated client, schema-first |
| Database | Postgres 16 | Standard across all stacks |
| Cache | Redis (optional) | Only if caching is needed |
| Auth | NestJS guards (API-key) | `@UseGuards(ApiKeyGuard)` |
| Validation | class-validator + class-transformer | DTO validation via decorators |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | Prisma `@@map` with audit fields | `createdAt`, `updatedAt` |
| Soft deletes | `deletedAt` field + Prisma middleware | Filter deleted records |
| External IDs (no integer PKs) | UUID `@id @default(uuid())` | Standard |
| API contract | REST (NestJS controllers + DTOs) | Swagger auto-generated |
| MutationResult pattern | `ApiResponse` DTO | `{ok, data, errors}` |
| Auth | API-key guard | `@UseGuards(ApiKeyGuard)` |
| Permissions | Key-level scopes | Guard checks scopes |
| Background jobs | None (or BullMQ if needed) | Add only when needed |
| Forms engine | N/A | Micro template |
| Workflow engine | N/A | Micro template |
| Feature toggles | Env vars via ConfigService | NestJS ConfigModule |
| Admin panel | Prisma Studio (dev only) | Or skip |
| Testing framework | Vitest | Integration tests |
| Linter/Formatter | ESLint + Prettier | Standard TypeScript |
| Package manager | pnpm | `package.json` + `pnpm-lock.yaml` |
| Migrations | Prisma Migrate | `prisma migrate dev` |

---

## Pattern: Models & ORM

Prisma schema with audit fields. UUID primary keys throughout.

```prisma
model ApiKey {
  id         String    @id @default(uuid())
  name       String
  keyHash    String    @unique @map("key_hash")
  scopes     String[]  @default([])
  isActive   Boolean   @default(true) @map("is_active")
  lastUsedAt DateTime? @map("last_used_at")
  createdAt  DateTime  @default(now()) @map("created_at")

  @@map("api_keys")
}

model Event {
  id        String   @id @default(uuid())
  type      String
  payload   Json
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")
  deletedAt DateTime? @map("deleted_at")

  @@map("events")
}
```

Soft deletes via Prisma middleware that filters `deletedAt IS NULL` on all
queries by default.

---

## Pattern: API Layer

NestJS controllers with DTOs for validation. Swagger auto-generated via
`@nestjs/swagger` decorators.

```typescript
class WebhookDto {
  @IsString()
  event: string;

  @IsObject()
  data: Record<string, unknown>;
}

class ApiResponse<T = unknown> {
  ok: boolean;
  message?: string;
  data?: T;
  errors?: Array<{ field: string; messages: string[] }>;
}

@Controller('webhooks')
@UseGuards(ApiKeyGuard)
export class WebhookController {
  constructor(private readonly webhookService: WebhookService) {}

  @Post()
  async receiveWebhook(@Body() dto: WebhookDto): Promise<ApiResponse> {
    await this.webhookService.process(dto);
    return { ok: true, message: 'Processed' };
  }
}
```

---

## Pattern: Auth

NestJS guard for API-key authentication. Keys are SHA256-hashed before
storage.

```typescript
@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const key = request.headers['x-api-key'];
    if (!key) throw new UnauthorizedException('API key required');

    const keyHash = createHash('sha256').update(key).digest('hex');
    const apiKey = await this.prisma.apiKey.findUnique({
      where: { keyHash, isActive: true },
    });
    if (!apiKey) throw new UnauthorizedException('Invalid API key');

    await this.prisma.apiKey.update({
      where: { id: apiKey.id },
      data: { lastUsedAt: new Date() },
    });

    request.apiKey = apiKey;
    return true;
  }
}
```

---

## Pattern: Permissions

Optional per-key scopes via a custom guard or decorator.

```typescript
export const RequireScope = (scope: string) => SetMetadata('scope', scope);

@Injectable()
export class ScopeGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const scope = this.reflector.get<string>('scope', context.getHandler());
    if (!scope) return true;

    const { apiKey } = context.switchToHttp().getRequest();
    return apiKey.scopes.includes(scope) || apiKey.scopes.includes('*');
  }
}

// Usage:
@Post('import')
@RequireScope('data.write')
async importData(@Body() dto: ImportDto): Promise<ApiResponse> { ... }
```

---

## Pattern: Background Jobs

Not included by default. Add BullMQ only when async processing is needed.

```typescript
// Only if needed:
@Processor('webhooks')
export class WebhookProcessor {
  @Process()
  async handle(job: Job<WebhookDto>): Promise<void> {
    // Process async...
  }
}
```

---

## Pattern: Forms Engine

N/A. Micro templates do not include a forms engine.

---

## Pattern: Workflow Engine

N/A. Micro templates do not include a workflow engine.

---

## Pattern: Feature Toggles

NestJS ConfigModule with env vars.

```typescript
// In module:
const isMonitoringEnabled = configService.get('FEATURE_MONITORING') === 'true';
if (isMonitoringEnabled) {
  // Register monitoring module
}
```

---

## Pattern: Admin

Prisma Studio for development data inspection (`npx prisma studio`). No
production admin panel by default -- keep it lean.

---

## Pattern: Testing

Vitest with real Postgres. Test with API key headers.

```typescript
describe('WebhookController', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = module.createNestApplication();
    prisma = module.get(PrismaService);
    await app.init();
  });

  it('processes a webhook', async () => {
    const rawKey = 'test-key';
    const keyHash = createHash('sha256').update(rawKey).digest('hex');
    await prisma.apiKey.create({ data: { name: 'test', keyHash, scopes: ['*'] } });

    const response = await request(app.getHttpServer())
      .post('/webhooks')
      .set('X-API-Key', rawKey)
      .send({ event: 'order.created', data: { id: '123' } });

    expect(response.status).toBe(201);
    expect(response.body.ok).toBe(true);
  });

  it('rejects without API key', async () => {
    const response = await request(app.getHttpServer())
      .post('/webhooks')
      .send({ event: 'order.created', data: { id: '123' } });

    expect(response.status).toBe(401);
  });
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both valid and invalid API key cases
- Integration tests via HTTP endpoints
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| API | `api` (NestJS + Node.js) | 3000 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine (optional) | 6379 | redis-cli ping |

Minimal. No frontend, no job worker unless needed.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** ESLint + Prettier
- **Build job:** TypeScript compile + Docker build
- **Test job:** Vitest with Postgres service
- **Audit job:** `pnpm audit`

---

## Pattern: Security

**API key hashing:** SHA256 before storage. Never store plaintext.

**Rate limiting:** `@nestjs/throttler` on all endpoints.

**Input validation:** class-validator DTOs at controller boundaries.

**SSRF protection:** URL validator on outgoing requests.

**CORS:** Disabled by default. Enable only if needed.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier | `.prettierrc` |
| Linting | ESLint | `eslint.config.js` |
| Max line length | 100 characters | Prettier config |
| Import sorting | ESLint import plugin | Built-in |

---

## What Carries Over

### From nestjs-nextjs (subset, reusable patterns)

- NestJS module/service/controller architecture
- Prisma schema patterns and migration setup
- Guard/interceptor patterns
- Docker Compose (Postgres)
- Vitest test setup

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern
- Health check pattern
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new for micro)

- API-key guard (replaces session auth)
- ApiKey Prisma model
- Per-key scope guard
- Simplified module structure (no auth module, no user module)

---

## Build Order

### Phase 0: Scaffolding
- [ ] NestJS 11 project (Fastify adapter)
- [ ] Prisma setup, initial migration
- [ ] Docker Compose (api, postgres, redis optional)
- [ ] Health check, ESLint + Prettier config

### Phase 1: Auth
- [ ] ApiKey Prisma model
- [ ] ApiKeyGuard
- [ ] Key creation endpoint
- [ ] Optional ScopeGuard

### Phase 2: Core API
- [ ] REST controllers with DTOs
- [ ] ApiResponse wrapper
- [ ] Swagger setup (`@nestjs/swagger`)
- [ ] Input validation

### Phase 3: Infrastructure + Polish
- [ ] Rate limiting (`@nestjs/throttler`)
- [ ] CI pipeline (lint, test, audit)
- [ ] README, CLAUDE.md
