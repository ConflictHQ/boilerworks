# Boilerworks Spring Boot + Angular -- Primer

> Enterprise-grade Java backend with Angular frontend. Choose this for banking,
> fintech, healthcare, and regulated industries where Spring's ecosystem, strong
> typing, and enterprise integrations are non-negotiable.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-spring-angular`
**Sibling variant:** [spring-nextjs](../spring-nextjs/PRIMER.md)

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

- Banking, fintech, insurance, and healthcare apps where Spring's enterprise
  integrations (JMS, LDAP, SAML, OAuth2) and mature security model are required.
- Large enterprise teams with Java expertise and existing Spring infrastructure
  -- CI pipelines, artifact repos, monitoring stacks built around the JVM.
- Angular shops that value strong typing end-to-end (Java + TypeScript),
  opinionated project structure, and RxJS-based reactive patterns.

### Not Ideal For

- Small teams or rapid prototyping -- Spring + Angular has significant
  boilerplate and setup overhead compared to lighter stacks.
- Projects where the frontend team prefers React. Choose
  [spring-nextjs](../spring-nextjs/PRIMER.md) instead.
- Microservices that need to stay lean. Consider [go-micro](../go-micro/PRIMER.md)
  or [fastapi-micro](../fastapi-micro/PRIMER.md) instead.

### vs spring-nextjs

Choose spring-angular when the frontend team is Angular-focused, or the
organization standardizes on Angular. Angular's opinionated structure, built-in
DI, RxJS, and Angular Material/PrimeNG align well with enterprise development
practices.

Choose spring-nextjs when the frontend team prefers React, or you need the
shared Next.js frontend from other Boilerworks stacks. Next.js offers faster
prototyping and a larger component ecosystem.

Both share the same Spring Boot backend. The difference is the frontend framework.

---

## Architecture

```
Browser
  +-- Angular 19 (TypeScript, RxJS, Angular Material or PrimeNG)
        |
        v (REST or GraphQL via HTTP)
        |
  Spring Boot 3 (Spring MVC, Spring Data JPA, Spring Security)
        |-- Spring Batch or Quartz (scheduled/batch jobs)
        |-- Postgres 16 (via Hibernate/JPA)
        |-- Redis 7 (cache, sessions)
        |-- OpenSearch 2 (full-text search, optional)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Spring Boot 3 (Java 21+) | Enterprise standard, massive ecosystem, mature security |
| Frontend | Angular 19 | Strong typing, opinionated structure, enterprise adoption |
| API | REST (Spring MVC) or GraphQL (graphql-java/DGS) | REST is default; GraphQL available for complex data graphs |
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
| Base model (audit trails) | `@MappedSuperclass AuditableEntity` | `createdAt/By`, `updatedAt/By` via JPA auditing |
| Soft deletes | `@Where(clause = "deleted_at IS NULL")` | `deletedAt/By` fields, never call `delete()` |
| External IDs (no integer PKs) | UUID `@Id` or separate `externalId` column | Never expose integer PKs |
| API contract | Spring MVC REST controllers or GraphQL | `@RestController` or DGS framework |
| MutationResult pattern | `ApiResponse<T>` wrapper | `{ok, data, errors[{field, messages}]}` |
| Auth (session-based) | Spring Security + session registry | httpOnly cookies, server-side sessions |
| Permissions (group-based) | Spring Security `GrantedAuthority` via roles | `@PreAuthorize("hasAuthority('product.view')")` |
| Background jobs | Spring Batch or Quartz | `@Scheduled` for cron, Batch for ETL |
| Forms engine | Phase 2 | JSON Schema, same concept |
| Workflow engine | Phase 2 | State machine, same concept |
| Feature toggles | `@ConditionalOnProperty` + env vars | Spring Boot conditional beans |
| Admin panel | Spring Boot Admin | Monitoring + basic management |
| Testing framework | JUnit 5 + MockMvc + Testcontainers | Real Postgres via Testcontainers |
| Linter/Formatter | Checkstyle + google-java-format | `.checkstyle.xml` |
| Package manager | Gradle (Kotlin DSL) or Maven | `build.gradle.kts` or `pom.xml` |
| Migrations | Flyway or Liquibase | Versioned SQL migration files |

---

## Pattern: Models & ORM

JPA entities with a shared `AuditableEntity` superclass. Spring Data JPA
auditing populates `createdBy`/`updatedBy` automatically via `AuditorAware`.

```java
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AuditableEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @CreatedDate
    private Instant createdAt;

    @CreatedBy
    private UUID createdBy;

    @LastModifiedDate
    private Instant updatedAt;

    @LastModifiedBy
    private UUID updatedBy;

    private Instant deletedAt;
    private UUID deletedBy;
}

@Entity
@Table(name = "products")
@Where(clause = "deleted_at IS NULL")
public class Product extends AuditableEntity {
    private String name;
    private String slug;
    private BigDecimal price;
}
```

Soft deletes: set `deletedAt`/`deletedBy`. Never call `repository.delete()`.
Hibernate `@Where` filters deleted records from all queries by default.

---

## Pattern: API Layer

Spring MVC REST controllers with standard CRUD. GraphQL via DGS or
graphql-java is an alternative for complex data graphs.

```java
@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
public class ProductController {
    private final ProductService productService;

    @GetMapping
    @PreAuthorize("hasAuthority('product.view')")
    public List<ProductDto> list(@RequestParam(required = false) String search) {
        return productService.findAll(search);
    }

    @PostMapping
    @PreAuthorize("hasAuthority('product.add')")
    public ApiResponse<ProductDto> create(@Valid @RequestBody CreateProductRequest request) {
        Product product = productService.create(request);
        return ApiResponse.ok(ProductDto.from(product));
    }
}
```

`ApiResponse<T>` wraps all mutation responses with `ok`, `data`, and `errors`.

---

## Pattern: Auth

Spring Security with session-based authentication. Sessions stored server-side
(Spring Session backed by Redis or JDBC). Token delivered as httpOnly cookie.

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
            .authorizeHttpRequests(a -> a
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/health").permitAll()
                .anyRequest().authenticated()
            );
        return http.build();
    }
}
```

SHA256-hashed session tokens. Rate limiting on auth endpoints via Bucket4j or
Spring Cloud Gateway filters.

---

## Pattern: Permissions

Spring Security `GrantedAuthority` mapped from group-based permissions.
Users belong to groups. Groups have permissions. Never assign permissions
directly to users.

```java
@PreAuthorize("hasAuthority('product.view')")
public List<ProductDto> list() { ... }

@PreAuthorize("hasAuthority('product.add')")
public ApiResponse<ProductDto> create(...) { ... }
```

Custom `UserDetailsService` loads permissions via group membership. Angular
guards check permissions client-side for UI gating.

---

## Pattern: Background Jobs

Spring Batch for ETL and bulk processing. Quartz for scheduled/cron jobs.
Both integrate with Spring Boot auto-configuration.

```java
@Component
@RequiredArgsConstructor
public class InvoiceProcessingJob {
    private final InvoiceService invoiceService;

    @Scheduled(cron = "0 0 2 * * *")  // 2 AM daily
    public void processOverdueInvoices() {
        invoiceService.processOverdue();
    }
}
```

Spring Boot Admin or Micrometer metrics for monitoring. Spring Batch provides
built-in job execution history and restart capabilities.

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern: versioned form definitions (draft ->
published -> archived), 21+ field types, logic engine for conditional rules.
Java implementation of the validation and logic engine.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Spring Statemachine is an option, or
custom JSON-defined states/transitions matching the Boilerworks pattern.
Action execution via Spring Batch or `@Async` tasks.

---

## Pattern: Feature Toggles

Spring Boot `@ConditionalOnProperty` for bean registration. Environment
variables control feature availability.

```java
@Configuration
@ConditionalOnProperty(name = "features.forms", havingValue = "true")
public class FormsModuleConfig {
    // Beans for forms module registered only when enabled
}
```

When disabled, the module's beans are not created and its endpoints are not
registered. Tied to Docker Compose profiles for optional infrastructure.

---

## Pattern: Admin

Spring Boot Admin for application monitoring and basic management. Custom
admin endpoints for data management if needed.

Auth-gated via Spring Security -- admin role required. Provides health checks,
metrics, log levels, environment inspection.

---

## Pattern: Testing

JUnit 5 with MockMvc for API integration tests. Testcontainers for real
Postgres. Never mock the database.

```java
@SpringBootTest
@Testcontainers
class ProductControllerTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ProductRepository productRepository;

    @Test
    @WithMockUser(authorities = {"product.add"})
    void createProduct() throws Exception {
        mockMvc.perform(post("/api/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Widget\",\"price\":\"9.99\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.ok").value(true));

        Product product = productRepository.findByName("Widget").orElseThrow();
        assertThat(product.getPrice()).isEqualByComparingTo("9.99");
    }

    @Test
    void createProductDenied() throws Exception {
        mockMvc.perform(post("/api/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Widget\",\"price\":\"9.99\"}"))
            .andExpect(status().isUnauthorized());
    }
}
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
| Backend | `api` (Spring Boot + embedded Tomcat) | 8080 | `/actuator/health` |
| Frontend | `ui` (Angular, nginx) | 4200 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

Spring Boot Admin runs within the backend container at `/admin`.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Checkstyle + google-java-format (backend), ESLint + Prettier (Angular)
- **Build job:** Gradle build + Docker build
- **Test job:** JUnit 5 + Testcontainers (with Postgres + Redis services)
- **Audit job:** OWASP Dependency-Check (backend), npm audit (frontend)

CI must pass before merge.

---

## Pattern: Security

**Session hardening:** SHA256-hashed tokens, httpOnly cookies, secure in prod,
sameSite lax. Spring Session with JDBC or Redis backend. Server-side
revocation is instant.

**Authorization:** `@PreAuthorize` on every controller method. Ownership checks
on mutations. Never trust client-provided IDs alone.

**Input validation:** `@Valid` + Bean Validation (Hibernate Validator) at
controller boundaries. `@Size`, `@NotBlank`, `@Pattern` annotations.

**SSRF protection:** URL validator on outgoing requests. Block private IPs,
localhost, non-HTTP schemes.

**CORS:** Explicit origin whitelist via `WebMvcConfigurer.addCorsMappings()`.

**File uploads:** MIME whitelist, size limits via `spring.servlet.multipart`,
filename sanitization.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | google-java-format | Gradle plugin |
| Linting | Checkstyle | `.checkstyle.xml` |
| Max line length | 120 characters | Checkstyle config |
| Frontend formatting | Prettier | `.prettierrc` |
| Frontend linting | ESLint | `eslint.config.js` |
| Pre-commit hooks | Checkstyle + ESLint | `.pre-commit-config.yaml` or Husky |

---

## What Carries Over

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- CI pipeline structure (lint, test, audit jobs)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Shared Concepts (same mental model, Spring implementation)

- Permission model (group-based, Spring Security maps to Boilerworks pattern)
- Forms engine (JSON Schema, same field types, same lifecycle)
- Workflow engine (same state machine, same condition/action types)
- Audit trail (JPA auditing with `AuditorAware`)

### Needs Building (new implementation)

- JPA entities with audit base classes
- Flyway or Liquibase migration setup
- Spring Security session auth with SHA256 token hashing
- Spring Data JPA repositories and service layer
- Angular frontend (components, services, guards, routing)
- Angular Material or PrimeNG design system
- Spring Batch / Quartz job infrastructure

---

## Build Order

### Phase 0: Scaffolding
- [ ] Spring Boot 3 project (Gradle Kotlin DSL, Java 21+)
- [ ] Spring Data JPA + Hibernate + Flyway
- [ ] Angular 19 app (Angular CLI, TypeScript strict)
- [ ] Docker Compose (api, ui, postgres, redis, minio, mailpit)
- [ ] Health check (`/actuator/health`), Checkstyle config

### Phase 1: Auth + Permissions
- [ ] Spring Security session auth, httpOnly cookies
- [ ] User, Group, Permission JPA entities + seed data
- [ ] `@PreAuthorize` on controllers
- [ ] Angular auth guard + permission service

### Phase 2: Core API
- [ ] REST controllers with `ApiResponse<T>` wrapper
- [ ] JPA auditing (`@CreatedBy`, `@LastModifiedBy` via `AuditorAware`)
- [ ] Soft delete pattern with `@Where`
- [ ] Angular services + components for CRUD

### Phase 3: Forms Engine
- [ ] FormDefinition JPA entity, field types, validation
- [ ] Logic engine, JSON Schema processing
- [ ] Angular dynamic form renderer + builder

### Phase 4: Workflow Engine
- [ ] Workflow JPA entities (definition, instance, transition log)
- [ ] State machine service, async action execution
- [ ] Angular workflow builder

### Phase 5: Infrastructure + Polish
- [ ] File uploads (MinIO via AWS SDK), email (Spring Mail)
- [ ] Feature toggles (`@ConditionalOnProperty`)
- [ ] Spring Boot Admin, monitoring
- [ ] Seed data, CI pipeline, README, CLAUDE.md
