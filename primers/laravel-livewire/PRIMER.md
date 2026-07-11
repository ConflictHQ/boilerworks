# Boilerworks Laravel + Livewire -- Primer

> Laravel 11 with Livewire 3 for server-rendered reactive PHP. Choose this for
> teams that want Laravel's ecosystem with dynamic, reactive UIs without writing
> JavaScript. Server-rendered components that feel like an SPA.

**Status:** Planned (Tier 4)
**Repo:** `ConflictHQ/boilerworks-laravel-livewire`
**Sibling variant:** [laravel-vue](../laravel-vue/PRIMER.md)

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

- PHP teams that want reactive, SPA-like UIs without a JavaScript framework --
  Livewire components are PHP classes that render Blade templates and update
  the DOM via AJAX automatically.
- Admin panels, internal tools, and CRUD-heavy apps where Livewire's
  server-rendered reactivity eliminates the need for a client-side router
  or state management.
- Projects that benefit from Laravel's ecosystem (Forge, Vapor, Nova, Horizon,
  Cashier) but do not need Vue's client-side rendering model.

### Not Ideal For

- Apps needing rich client-side interactivity with complex client state --
  drag-and-drop builders, canvas-based editors, offline support. Choose
  [laravel-vue](../laravel-vue/PRIMER.md) instead.
- Projects where the frontend team is Vue/React-focused and would find
  Livewire's server-rendered model limiting.
- High-frequency real-time UIs (games, collaborative text editors) where
  Livewire's AJAX round-trips add unacceptable latency.

### vs laravel-vue

Choose laravel-livewire when server-rendered reactivity wins: CRUD apps, admin
panels, form-heavy interfaces, dashboards where Livewire's PHP-only component
model means faster development and no JavaScript build step.

Choose laravel-vue when you need rich client-side interactivity: complex SPAs,
drag-and-drop, client-side state management, offline support, or when the
frontend team prefers Vue's component model.

Both share the same Laravel backend (Eloquent, queues, auth, permissions). The
difference is the frontend rendering model.

---

## Architecture

```
Browser
  +-- Livewire 3 (Blade templates, server-rendered reactive components)
        |
        v (AJAX requests to Livewire endpoint)
        |
  Laravel 11 (Eloquent, Queue, Events)
        |-- Laravel Horizon (Redis queue monitoring)
        |-- Postgres 16 (via Eloquent)
        |-- Redis 7 (cache, sessions, queue broker)
        +-- MinIO (S3-compatible file storage)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Laravel 11 (PHP 8.3+) | Batteries-included, massive ecosystem |
| Frontend | Livewire 3 + Blade + Tailwind CSS | Server-rendered reactive components, no JS framework |
| API | Livewire AJAX (no separate API for frontend) | Components communicate via server round-trips |
| ORM | Eloquent | Expressive, Active Record pattern, excellent for rapid development |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Laravel Queues (Redis driver) | First-party, battle-tested |
| Auth | Laravel Breeze or Fortify (session-based) | httpOnly cookies, built-in |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Laravel Mail (prod) | Standard across all stacks |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `AuditableTrait` on Eloquent models | Same as laravel-vue |
| Soft deletes | `SoftDeletes` trait | Same as laravel-vue |
| External IDs (no integer PKs) | UUID primary keys (`HasUuids` trait) | Same as laravel-vue |
| API contract | Livewire component actions | No REST/GraphQL for frontend |
| MutationResult pattern | Livewire validation + flash messages | Blade renders errors inline |
| Auth (session-based) | Laravel Breeze / Fortify | Same as laravel-vue |
| Permissions (group-based) | Spatie laravel-permission | Same as laravel-vue |
| Background jobs | Laravel Queues + Horizon | Same as laravel-vue |
| Forms engine | Phase 2 | JSON Schema, Livewire rendering |
| Workflow engine | Phase 2 | State machine, queue actions |
| Feature toggles | `config/features.php` + env vars | Same as laravel-vue |
| Admin panel | Filament or Laravel Nova | Livewire-native admin |
| Testing framework | Pest PHP + Livewire test helpers | Component + feature tests |
| Linter/Formatter | Laravel Pint | `pint.json` |
| Package manager | Composer | `composer.json` |
| Migrations | Laravel migrations | `php artisan migrate` |

---

## Pattern: Models & ORM

Identical to laravel-vue. Eloquent models with `AuditableTrait`,
`SoftDeletes`, and `HasUuids`.

```php
class Product extends Model
{
    use HasUuids, SoftDeletes, AuditableTrait;

    protected $fillable = ['name', 'slug', 'price'];

    protected $casts = [
        'price' => 'decimal:2',
    ];
}
```

`AuditableTrait` populates `created_by`/`updated_by` via `Auth::id()` on
model events. Soft deletes via Laravel's built-in `SoftDeletes` trait.

---

## Pattern: API Layer

No separate API for the frontend. Livewire components are PHP classes that
handle user interactions via server round-trips and re-render Blade templates.

```php
class ProductList extends Component
{
    public string $search = '';

    public function mount(): void
    {
        $this->authorize('viewAny', Product::class);
    }

    public function delete(Product $product): void
    {
        $this->authorize('delete', $product);
        $product->delete(); // SoftDeletes
        session()->flash('message', 'Product deleted.');
    }

    public function render(): View
    {
        return view('livewire.product-list', [
            'products' => Product::query()
                ->when($this->search, fn ($q) => $q->where('name', 'like', "%{$this->search}%"))
                ->latest()
                ->paginate(20),
        ]);
    }
}
```

```blade
{{-- livewire/product-list.blade.php --}}
<div>
    <input wire:model.live.debounce.300ms="search" placeholder="Search..." />

    @foreach ($products as $product)
        <div class="flex items-center justify-between py-2">
            <span>{{ $product->name }}</span>
            <button wire:click="delete({{ $product->id }})" wire:confirm="Delete this product?">
                Delete
            </button>
        </div>
    @endforeach

    {{ $products->links() }}
</div>
```

Livewire handles reactivity automatically -- typing in the search input
triggers a server round-trip, re-renders the component, and patches the DOM.

---

## Pattern: Auth

Identical to laravel-vue. Laravel Breeze or Fortify for session-based auth.
httpOnly cookies, server-side sessions. SHA256-hashed tokens.

Livewire components access the authenticated user via `Auth::user()` or
`$this->authorize()`.

---

## Pattern: Permissions

Identical to laravel-vue. Spatie laravel-permission. Group-based (roles map
to groups). Never assign permissions directly to users.

```php
// In Livewire components:
$this->authorize('update', $product);

// In Blade templates:
@can('create', App\Models\Product::class)
    <button wire:click="showCreateForm">New Product</button>
@endcan
```

---

## Pattern: Background Jobs

Identical to laravel-vue. Laravel Queues with Redis driver. Horizon for
monitoring.

```php
class ProcessInvoice implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(public Invoice $invoice) {}

    public function handle(): void
    {
        $this->invoice->process();
    }
}

// Dispatch
ProcessInvoice::dispatch($invoice);
```

---

## Pattern: Forms Engine

Phase 2. Same JSON Schema pattern. Livewire components render form fields
from JSON Schema definitions. Livewire's real-time validation provides
immediate feedback as users fill out forms.

---

## Pattern: Workflow Engine

Phase 2. Same state machine pattern. Laravel backend with queue-based async
actions. Livewire provides real-time workflow state display via polling or
Laravel Echo for WebSocket updates.

---

## Pattern: Feature Toggles

Identical to laravel-vue. `config/features.php` with env vars.

```php
// config/features.php
return [
    'forms' => env('FEATURE_FORMS', false),
    'workflows' => env('FEATURE_WORKFLOWS', false),
];

// Usage:
if (config('features.forms')) {
    // Register routes, load Livewire components
}
```

---

## Pattern: Admin

Filament (Livewire-native admin panel) is the natural choice. Filament is
built on Livewire and provides rich CRUD, form builders, table builders,
and dashboard widgets out of the box.

```php
class ProductResource extends Resource
{
    protected static ?string $model = Product::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            TextInput::make('name')->required(),
            TextInput::make('price')->numeric()->required(),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table->columns([
            TextColumn::make('name')->searchable(),
            TextColumn::make('price')->money(),
            TextColumn::make('created_at')->dateTime(),
        ]);
    }
}
```

Alternative: Laravel Nova (paid, first-party).

---

## Pattern: Testing

Pest PHP with Livewire test helpers. Real database, not mocks.

```php
test('can list products', function () {
    $user = User::factory()->withPermission('product.view')->create();
    $product = Product::factory()->create(['name' => 'Widget']);

    Livewire::actingAs($user)
        ->test(ProductList::class)
        ->assertSee('Widget');
});

test('can search products', function () {
    $user = User::factory()->withPermission('product.view')->create();
    Product::factory()->create(['name' => 'Widget']);
    Product::factory()->create(['name' => 'Gadget']);

    Livewire::actingAs($user)
        ->test(ProductList::class)
        ->set('search', 'Widget')
        ->assertSee('Widget')
        ->assertDontSee('Gadget');
});

test('denies access without permission', function () {
    $user = User::factory()->create();

    Livewire::actingAs($user)
        ->test(ProductList::class)
        ->assertForbidden();
});
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via Livewire test helpers, not isolated model tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | `app` (Laravel + PHP-FPM + Nginx) | 8000 | `GET /health` |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Queue Worker | Same image, `php artisan queue:work` | -- | -- |
| Horizon | Same image, `php artisan horizon` | -- | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |

No separate frontend container. Livewire is served by Laravel. One fewer
service than laravel-vue.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Laravel Pint (PHP), Prettier (Blade if applicable)
- **Build job:** Docker build
- **Test job:** Pest PHP with Postgres + Redis services
- **Audit job:** `composer audit`

CI must pass before merge.

---

## Pattern: Security

Identical to laravel-vue for the backend. Session hardening, CSRF protection
(Livewire handles this automatically), authorization via policies.

**Livewire-specific:** Livewire 3 includes built-in CSRF protection on all
component requests. `wire:model` only binds to public properties you
explicitly declare. Livewire validates all incoming data against the
component's public API.

**Input validation:** Laravel validation rules in Livewire components.
Form request classes for complex validation.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Laravel Pint | `pint.json` |
| Linting | PHPStan (Larastan) | `phpstan.neon` |
| Max line length | 120 characters | `pint.json` |
| Pre-commit hooks | Pint + PHPStan | `.pre-commit-config.yaml` or Husky |

---

## What Carries Over

### From laravel-vue (reusable as-is)

All Laravel backend code carries over unchanged:
- Eloquent models with traits (AuditableTrait, SoftDeletes, HasUuids)
- Spatie laravel-permission configuration
- Laravel Queues + Horizon job infrastructure
- Migrations, seeders, factories
- Feature toggle configuration
- Auth configuration (Breeze/Fortify)

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern, feature toggle pattern (env-based)
- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Building (new implementation)

- Livewire components (replace Inertia/Vue pages)
- Blade templates with Tailwind (replace Vue SFCs)
- Filament admin panel (replace or supplement Nova)
- Livewire-specific test patterns
- Form/workflow rendering via Livewire components

---

## Build Order

### Phase 0: Scaffolding
- [ ] Laravel 11 project with Livewire 3, Tailwind CSS
- [ ] Eloquent models + traits (from laravel-vue)
- [ ] Docker Compose (app, postgres, redis, minio, mailpit)
- [ ] Health check, Pint + PHPStan config

### Phase 1: Auth + Permissions
- [ ] Laravel Breeze with Livewire starter kit
- [ ] Spatie laravel-permission (from laravel-vue)
- [ ] Livewire component authorization

### Phase 2: Core Livewire Components
- [ ] CRUD components (list, create, edit, delete)
- [ ] Blade layouts with Tailwind (sidebar, nav, content)
- [ ] Real-time search, pagination, sorting
- [ ] Flash messages, validation errors

### Phase 3: Forms Engine
- [ ] FormDefinition model (from laravel-vue)
- [ ] Livewire dynamic form renderer
- [ ] Livewire form builder component

### Phase 4: Workflow Engine
- [ ] Workflow models (from laravel-vue)
- [ ] State machine service, queue actions
- [ ] Livewire workflow display + transition UI

### Phase 5: Infrastructure + Polish
- [ ] File uploads (Livewire uploads + MinIO)
- [ ] Email, notifications
- [ ] Filament admin panel, Horizon
- [ ] Feature toggles, seed data, CI pipeline, README, CLAUDE.md
