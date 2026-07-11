# Boilerworks Spring Boot + Next.js -- Primer

> Spring Boot 3 backend with a rich Next.js 16 frontend. Modern enterprise for
> teams that want Spring's backend power with React's frontend ecosystem. Choose
> this over spring-angular when the frontend team prefers React.

**Status:** Planned (Tier 4)
**Repo:** `ConflictHQ/boilerworks-spring-nextjs`
**Sibling variant:** [spring-angular](../spring-angular/PRIMER.md)

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

- Enterprise teams with Spring/Java backend expertise who want a modern React
  frontend rather than Angular's opinionated structure.
- Projects that need the shared Boilerworks Next.js frontend while keeping
  Spring Boot's enterprise backend integrations.
- Organizations migrating from Spring + Angular to React incrementally, or
  teams that are React-first but must integrate with existing Spring services.

### Not Ideal For

- Angular shops with established Angular expertise and component libraries.
  Choose [spring-angular](../spring-angular/PRIMER.md) instead.
- Teams that do not need Spring's enterprise features. Consider
  [fastapi-nextjs](../fastapi-nextjs/PRIMER.md) or
  [django-nextjs](../django-nextjs/PRIMER.md) for lighter backends.
- Rapid prototyping where Spring's setup overhead is not justified.

### vs spring-angular

Choose spring-nextjs when the frontend team prefers React, or you want to
leverage the shared Boilerworks Next.js frontend (Apollo Client, shared
components, i18n, form/workflow builders).

Choose spring-angular when the team is Angular-focused, or the organization
standardizes on Angular with its opinionated DI, RxJS patterns, and
Angular Material/PrimeNG.

Both share the same Spring Boot backend. The difference is the frontend.

---

## Architecture

```
Browser
  +-- Next.js 16 (shared frontend -- see NEXTJS_FRONTEND.md)
        +-- Apollo Client -> GraphQL API (or REST)
              |
              v
        Spring Boot 3 (Spring MVC, Spring Data JPA, Spring Security)
              |-- Spring Batch or Quartz (scheduled/batch jobs)
              |-- Postgres 16 (via Hibernate/JPA)
              |-- Redis 7 (cache, sessions)
              +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Spring Boot 3 (Java 21+) | Enterprise standard, massive ecosystem, mature security |
| Frontend | Next.js 16 | Shared frontend -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md) |
| API | GraphQL (DGS or graphql-java) or REST | GraphQL for consistency with other Next.js stacks; REST is valid |
| ORM | Spring Data JPA (Hibernate) | Mature, standard JPA, excellent query derivation |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Spring Batch or Quartz | Spring Batch for ETL/bulk; Quartz for scheduled tasks |
| Auth | Spring Security sessions (httpOnly cookies) | Enterprise-grade, session-based |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Spring Mail (prod) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `@MappedSuperclass AuditableEntity` | JPA auditing with `AuditorAware` |
| Soft deletes | `@Where(clause = "deleted_at IS NULL")` | `deletedAt/By`, never `delete()` |
| External IDs (no integer PKs) | UUID `@Id` | Never expose integer PKs |
| API contract | GraphQL (DGS) or REST controllers | GraphQL recommended for Next.js frontend |
| MutationResult pattern | `MutationResult` GraphQL type or `ApiResponse<T>` | `{ok, errors}` |
| Auth (session-based) | Spring Security + session registry | httpOnly cookies |
| Permissions (group-based) | Spring Security `GrantedAuthority` | `@PreAuthorize` |
| Background jobs | Spring Batch or Quartz | `@Scheduled`, Batch jobs |
| Forms engine | Phase 2 | JSON Schema, same concept |
| Workflow engine | Phase 2 | State machine, same concept |
| Feature toggles | `@ConditionalOnProperty` + env vars | Conditional bean registration |
| Admin panel | Spring Boot Admin | Monitoring + management |
| Testing framework | JUnit 5 + MockMvc + Testcontainers | Real Postgres |
| Linter/Formatter | Checkstyle + google-java-format | Backend; Prettier + ESLint for frontend |
| Package manager | Gradle (Kotlin DSL) | `build.gradle.kts` |
| Migrations | Flyway or Liquibase | Versioned SQL files |

---

## Pattern: Models & ORM

Identical to spring-angular. JPA entities with `AuditableEntity` superclass.
Spring Data JPA auditing populates `createdBy`/`updatedBy` via `AuditorAware`.

```java
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AuditableEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @CreatedDate private Instant createdAt;
    @CreatedBy  private UUID createdBy;
    @LastModifiedDate private Instant updatedAt;
    @LastModifiedBy  private UUID updatedBy;
    private Instant deletedAt;
    private UUID deletedBy;
}
```

Soft deletes via `@Where`. Never call `repository.delete()`.

---

## Pattern: API Layer

GraphQL via Netflix DGS framework is recommended for consistency with the
shared Next.js frontend (Apollo Client). REST via Spring MVC is a valid
alternative.

```java
@DgsComponent
public class ProductDataFetcher {
    @DgsQuery
    public List<Product> products(@InputArgument String search) {
        // Auth + permission check via Spring Security context
        return productService.findAll(search);
    }

    @DgsMutation
    public MutationResult createProduct(@InputArgument CreateProductInput input) {
        Product product = productService.create(input);
        return MutationResult.ok();
    }
}
```

Auth check enforced via Spring Security. `MutationResult` returns `ok` and
`errors` matching the Boilerworks pattern.

---

## Pattern: Auth

Identical to spring-angular. Spring Security with session-based auth. Sessions
stored server-side (Spring Session backed by Redis or JDBC). httpOnly cookies.
SHA256-hashed tokens.

Frontend: Next.js auth gate -- see [NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Permissions

Identical to spring-angular. Spring Security `GrantedAuthority` via group
membership. `@PreAuthorize("hasAuthority('...')")` on every endpoint.

Frontend: permission guards via shared Next.js hooks. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md).

---

## Pattern: Background Jobs

Identical to spring-angular. Spring Batch for ETL/bulk. Quartz for
scheduled tasks. `@Scheduled` for cron jobs.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Java backend implementation, Next.js
DynamicForm + FormBuilder from shared frontend.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Java backend implementation, Next.js
WorkflowBuilder (ReactFlow) from shared frontend.

---

## Pattern: Feature Toggles

Identical to spring-angular. `@ConditionalOnProperty` for bean registration.
Environment variables control feature availability.

---

## Pattern: Admin

Identical to spring-angular. Spring Boot Admin for monitoring. Custom admin
endpoints auth-gated via Spring Security.

---

## Pattern: Testing

Identical to spring-angular. JUnit 5 + MockMvc + Testcontainers with real
Postgres. Test both allowed and denied permission cases.

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
| Backend | `api` (Spring Boot + embedded Tomcat) | 8080 | `/actuator/health` |
| Frontend | `ui` (Next.js) | 3000 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Checkstyle (backend), ESLint + Prettier (frontend)
- **Build job:** Gradle build + Docker build
- **Test job:** JUnit 5 + Testcontainers (Postgres + Redis services)
- **Audit job:** OWASP Dependency-Check (backend), npm audit (frontend)

---

## Pattern: Security

Identical to spring-angular. Session hardening, `@PreAuthorize`, Bean
Validation, SSRF protection, CORS whitelist, file upload validation.

GraphQL-specific: query depth limiting, introspection disabled in prod,
masked error messages.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | google-java-format | Gradle plugin |
| Linting | Checkstyle | `.checkstyle.xml` |
| Max line length | 120 characters | Checkstyle config |
| Frontend formatting | Prettier | `.prettierrc` |
| Frontend linting | ESLint | `eslint.config.js` |

---

## What Carries Over

### Frontend (shared across all Next.js stacks)

The Next.js frontend is backend-agnostic. See
[NEXTJS_FRONTEND.md](../NEXTJS_FRONTEND.md). Carries over as-is from other
Next.js stacks.

### From spring-angular (reusable as-is)

All Spring Boot backend code carries over unchanged:
- `AuditableEntity` base class and all JPA entities
- Spring Security configuration and permission model
- Spring Data JPA repositories and service layer
- Spring Batch / Quartz job infrastructure
- Flyway/Liquibase migrations
- Feature toggle configuration

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new implementation)

- GraphQL schema (DGS) mapped to JPA entities (replaces REST if using GraphQL)
- Spring-to-Next.js session handoff (cookie configuration)
- Next.js frontend wired to Spring GraphQL endpoint

---

## Build Order

### Phase 0: Scaffolding
- [ ] Spring Boot 3 project (Gradle Kotlin DSL, Java 21+)
- [ ] Spring Data JPA + Hibernate + Flyway
- [ ] Next.js 16 frontend (copy from shared template)
- [ ] Docker Compose (api, ui, postgres, redis, minio, mailpit)
- [ ] Health check, Checkstyle + ESLint config

### Phase 1: Auth + Permissions
- [ ] Spring Security session auth, httpOnly cookies
- [ ] User, Group, Permission JPA entities + seed data
- [ ] `@PreAuthorize` on controllers/data fetchers
- [ ] Frontend auth gate (shared from NEXTJS_FRONTEND)

### Phase 2: Core API
- [ ] DGS GraphQL or REST controllers
- [ ] JPA auditing (`AuditorAware`)
- [ ] MutationResult pattern
- [ ] Soft delete pattern

### Phase 3: Forms Engine
- [ ] FormDefinition JPA entity, field types, validation
- [ ] GraphQL CRUD
- [ ] Frontend DynamicForm + FormBuilder (shared)

### Phase 4: Workflow Engine
- [ ] Workflow JPA entities
- [ ] State machine service, async actions
- [ ] Frontend WorkflowBuilder (shared)

### Phase 5: Infrastructure + Polish
- [ ] File uploads, email, notifications
- [ ] Feature toggles, Spring Boot Admin
- [ ] Seed data, CI pipeline, README, CLAUDE.md
