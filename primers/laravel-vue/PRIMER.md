# Boilerworks Laravel + Vue -- Primer

> Laravel 11 with Inertia.js and Vue 3 Composition API. The blessed Laravel SPA
> stack -- server-driven routing with client-side rendering. Choose this for PHP
> teams wanting modern SPA-like interactivity without managing a separate frontend
> deployment or client-side router.

**Status:** Building
**Repo:** `ConflictHQ/boilerworks-laravel-vue`
**Sibling variant:** [laravel-livewire](../laravel-livewire/PRIMER.md)

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

- PHP teams wanting a modern SPA-like experience with client-side transitions,
  rich component state, and Vue's reactivity model -- without managing a separate
  frontend deployment or client-side router.
- Projects that benefit from Laravel's ecosystem: Forge, Vapor, Nova, Horizon,
  Cashier (payments), Socialite (OAuth), Scout (search).
- E-commerce adjacent apps, subscription platforms, and multi-tenant SaaS where
  Laravel's payment and subscription packages give you a head start.

### Not Ideal For

- True API-first architectures where you need GraphQL or REST endpoints consumed
  by mobile apps, third-party integrations, and a web frontend independently.
  Choose a decoupled stack instead.
- When the team prefers React over Vue -- Inertia supports React but the Laravel
  community and tooling center on Vue.
- When server-rendered simplicity is enough -- choose laravel-livewire instead
  of adding the Vue build layer.

### vs laravel-livewire

Choose laravel-vue (Inertia) when you want SPA-like experience with client-side
transitions, complex component state, rich interactivity, drag-and-drop builders,
and anything that benefits from Vue's Composition API and reactivity system.

Choose laravel-livewire when you want server-rendered simplicity: less
JavaScript, rapid prototyping, admin-facing tools, and CRUD apps where a full
Vue frontend is overhead.

Both share the same Laravel backend patterns. The difference is the frontend
delivery model.

---

## Architecture

```
Browser
  +-- Vue 3 (Composition API) via Inertia.js
        |-- Pages: server-driven routing, no client-side router
        |-- Components: reusable Vue components
        |-- Composables: shared stateful logic (like React hooks)
        +-- useForm(): Inertia form handling
              |
              v (Inertia protocol -- JSON props on XHR, full HTML on initial load)
              |
        Laravel 11 (Eloquent, Middleware, Service Providers)
              |-- Laravel Queues (async jobs)
              |-- Postgres 16 (data)
              |-- Redis 7 (cache, sessions, queue broker)
              |-- MeiliSearch (full-text search via Laravel Scout, optional)
              +-- MinIO (S3-compatible via Flysystem)
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Laravel 11 | Batteries-included PHP framework: ORM, queues, auth, payments, ecosystem |
| Frontend | Vue 3 (Composition API) | Reactive, component-driven UI with strong Laravel community support |
| API | Inertia.js protocol | Server-driven routing with SPA-like UX; no separate API to build or maintain |
| ORM | Eloquent | Expressive Active Record ORM with excellent migration system |
| Database | Postgres 16 | Standard across all stacks |
| Cache/Broker | Redis 7 | Standard across all stacks |
| Job Queue | Laravel Queues (Redis driver) | Native queue system with Horizon for monitoring |
| Auth | Laravel Sanctum (session-based) | httpOnly cookies, session-based, built into Laravel |
| Storage | MinIO (S3-compatible) | Standard across all stacks |
| Email | Mailpit (dev), Laravel Mail (prod) | Standard across all stacks |
| Search | MeiliSearch (optional) | Full-text search via Laravel Scout |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | `HasAuditTrail` trait | `created_by`, `updated_by` via auth user |
| Soft deletes | `SoftDeletes` trait (Laravel built-in) | `deleted_at` column, never call `->delete()` on business models |
| External IDs (no integer PKs) | `HasUuid` trait | UUID `external_id` column; never expose auto-increment IDs |
| API contract | Inertia.js protocol | `Inertia::render()` returns props; no GraphQL, no REST |
| MutationResult pattern | Redirects + session flash + validation errors | Inertia handles redirect-with-flash and error bags natively |
| Auth (session-based) | Laravel Sanctum | httpOnly cookies, server-side sessions |
| Permissions (group-based) | Spatie Laravel Permission | Roles assigned to groups, permissions checked via middleware |
| Background jobs | Laravel Queues + Horizon | Jobs in `app/Jobs/`, Redis driver, Horizon dashboard |
| Forms engine | `FormDefinition` model + Vue renderer | JSON Schema, server-side validation, Vue builder |
| Workflow engine | State machine service + Queue actions | JSON states/transitions, polymorphic relation |
| Feature toggles | `config/features.php` + env vars | Gate service providers and routes |
| Admin panel | Filament (free) or Nova (paid) | Filament is Livewire-based, works alongside Inertia frontend |
| Testing framework | Pest PHP | Feature tests hitting real database |
| Linter/Formatter | Laravel Pint (PHP), Prettier + ESLint (Vue) | `pint.json`, `.prettierrc`, `.eslintrc` |
| Package manager | Composer (PHP), npm (JS) | `composer.json`, `package.json` |
| Migrations | Laravel migrations | `php artisan migrate` |

---

## Pattern: Models & ORM

All business models extend the base `Model` class and use shared traits for
audit trails, soft deletes, and external identifiers.

**HasAuditTrail trait** -- tracks who created and updated records:
```php
// app/Traits/HasAuditTrail.php
namespace App\Traits;

trait HasAuditTrail
{
    public static function bootHasAuditTrail(): void
    {
        static::creating(function ($model) {
            if (auth()->check()) {
                $model->created_by = auth()->id();
                $model->updated_by = auth()->id();
            }
        });

        static::updating(function ($model) {
            if (auth()->check()) {
                $model->updated_by = auth()->id();
            }
        });
    }

    public function creator()
    {
        return $this->belongsTo(User::class, 'created_by');
    }

    public function updater()
    {
        return $this->belongsTo(User::class, 'updated_by');
    }
}
```

**HasUuid trait** -- external-facing identifier:
```php
// app/Traits/HasUuid.php
namespace App\Traits;

use Illuminate\Support\Str;

trait HasUuid
{
    public static function bootHasUuid(): void
    {
        static::creating(function ($model) {
            $model->uuid ??= (string) Str::uuid();
        });
    }

    public function getRouteKeyName(): string
    {
        return 'uuid';
    }
}
```

**Example business model** with all traits applied:
```php
// app/Models/Product.php
namespace App\Models;

use App\Traits\HasAuditTrail;
use App\Traits\HasUuid;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Product extends Model
{
    use HasAuditTrail;
    use HasUuid;
    use SoftDeletes;

    protected $fillable = ['name', 'price', 'category_id'];

    protected $casts = [
        'price' => 'decimal:2',
    ];

    public function category()
    {
        return $this->belongsTo(Category::class);
    }

    public function lineItems()
    {
        return $this->hasMany(LineItem::class);
    }
}
```

**Migration:**
```php
Schema::create('products', function (Blueprint $table) {
    $table->id();
    $table->uuid('uuid')->unique();
    $table->string('name');
    $table->decimal('price', 10, 2);
    $table->foreignId('category_id')->nullable()->constrained();
    $table->foreignId('created_by')->nullable()->constrained('users');
    $table->foreignId('updated_by')->nullable()->constrained('users');
    $table->timestamps();
    $table->softDeletes();
});
```

Never expose integer PKs. Use `uuid` in URLs and API responses. The
`getRouteKeyName` override makes Laravel route model binding use `uuid`
automatically.

---

## Pattern: API Layer

No separate API. Inertia.js is the bridge between Laravel controllers and Vue
pages. Controllers return `Inertia::render()` instead of Blade views. On the
initial page load, Laravel returns full HTML with embedded props. On subsequent
navigation, Inertia makes XHR requests and Laravel returns JSON props only.

**Resource controller with Inertia responses:**
```php
// app/Http/Controllers/ProductController.php
namespace App\Http\Controllers;

use App\Http\Requests\StoreProductRequest;
use App\Http\Requests\UpdateProductRequest;
use App\Models\Product;
use Inertia\Inertia;

class ProductController extends Controller
{
    public function __construct()
    {
        $this->middleware(['auth:sanctum']);
        $this->middleware('permission:products.view')->only(['index', 'show']);
        $this->middleware('permission:products.create')->only(['create', 'store']);
        $this->middleware('permission:products.edit')->only(['edit', 'update']);
        $this->middleware('permission:products.delete')->only('destroy');
    }

    public function index()
    {
        return Inertia::render('Products/Index', [
            'products' => Product::with('category')
                ->orderBy('created_at', 'desc')
                ->paginate(25),
        ]);
    }

    public function create()
    {
        return Inertia::render('Products/Create', [
            'categories' => Category::all(['id', 'uuid', 'name']),
        ]);
    }

    public function store(StoreProductRequest $request)
    {
        Product::create($request->validated());

        return redirect()
            ->route('products.index')
            ->with('success', 'Product created.');
    }

    public function show(Product $product)
    {
        return Inertia::render('Products/Show', [
            'product' => $product->load('category', 'creator'),
        ]);
    }

    public function edit(Product $product)
    {
        return Inertia::render('Products/Edit', [
            'product' => $product,
            'categories' => Category::all(['id', 'uuid', 'name']),
        ]);
    }

    public function update(UpdateProductRequest $request, Product $product)
    {
        $product->update($request->validated());

        return redirect()
            ->route('products.show', $product)
            ->with('success', 'Product updated.');
    }

    public function destroy(Product $product)
    {
        $product->delete(); // SoftDeletes handles deleted_at

        return redirect()
            ->route('products.index')
            ->with('success', 'Product deleted.');
    }
}
```

**Form request for validation:**
```php
// app/Http/Requests/StoreProductRequest.php
namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreProductRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // Handled by middleware
    }

    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'price' => ['required', 'numeric', 'min:0.01'],
            'category_id' => ['nullable', 'exists:categories,id'],
        ];
    }
}
```

Inertia handles the MutationResult pattern natively: successful mutations
redirect with flash data, validation failures return error bags that Inertia
surfaces automatically in `useForm()`.

---

## Pattern: Auth

Laravel Sanctum with session-based authentication. Sessions stored server-side,
delivered as httpOnly cookies. No JWTs for browser auth.

**Sanctum configuration:**
```php
// config/sanctum.php
return [
    'stateful' => explode(',', env(
        'SANCTUM_STATEFUL_DOMAINS',
        'localhost,localhost:3000,127.0.0.1'
    )),
    'guard' => ['web'],
    'expiration' => null, // Sessions expire via session lifetime
];
```

**Auth routes (Breeze scaffold or custom):**
```php
// routes/auth.php
use App\Http\Controllers\Auth\LoginController;
use App\Http\Controllers\Auth\RegisterController;

Route::middleware('guest')->group(function () {
    Route::get('login', [LoginController::class, 'create'])->name('login');
    Route::post('login', [LoginController::class, 'store']);
    Route::get('register', [RegisterController::class, 'create'])->name('register');
    Route::post('register', [RegisterController::class, 'store']);
});

Route::middleware('auth:sanctum')->group(function () {
    Route::post('logout', [LoginController::class, 'destroy'])->name('logout');
});
```

**Login controller:**
```php
// app/Http/Controllers/Auth/LoginController.php
namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Http\Requests\LoginRequest;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Inertia\Inertia;

class LoginController extends Controller
{
    public function create()
    {
        return Inertia::render('Auth/Login');
    }

    public function store(LoginRequest $request)
    {
        $request->authenticate();
        $request->session()->regenerate();

        return redirect()->intended(route('dashboard'));
    }

    public function destroy(Request $request)
    {
        Auth::guard('web')->logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect('/');
    }
}
```

**Middleware stack:**
```php
// bootstrap/app.php
->withMiddleware(function (Middleware $middleware) {
    $middleware->web(append: [
        \App\Http\Middleware\HandleInertiaRequests::class,
    ]);
    $middleware->statefulApi();
})
```

Session token stored as httpOnly cookie (Laravel's default). Server-side
revocation is instant. Rate limiting on auth endpoints via Laravel's built-in
`throttle` middleware.

---

## Pattern: Permissions

Spatie Laravel Permission. Group-based -- never user-based. No exceptions.

**Setup:**
```bash
composer require spatie/laravel-permission
php artisan vendor:publish --provider="Spatie\Permission\PermissionServiceProvider"
php artisan migrate
```

**Permission seeder:**
```php
// database/seeders/PermissionSeeder.php
namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Spatie\Permission\Models\Permission;
use Spatie\Permission\Models\Role;

class PermissionSeeder extends Seeder
{
    public function run(): void
    {
        $permissions = [
            'products.view', 'products.create', 'products.edit', 'products.delete',
            'orders.view', 'orders.create', 'orders.edit', 'orders.delete',
            'users.view', 'users.manage',
        ];

        foreach ($permissions as $permission) {
            Permission::firstOrCreate(['name' => $permission]);
        }

        $admin = Role::firstOrCreate(['name' => 'admin']);
        $admin->syncPermissions(Permission::all());

        $editor = Role::firstOrCreate(['name' => 'editor']);
        $editor->syncPermissions([
            'products.view', 'products.create', 'products.edit',
            'orders.view',
        ]);

        $viewer = Role::firstOrCreate(['name' => 'viewer']);
        $viewer->syncPermissions(['products.view', 'orders.view']);
    }
}
```

**User model setup:**
```php
// app/Models/User.php
use Spatie\Permission\Traits\HasRoles;

class User extends Authenticatable
{
    use HasRoles;
    // ...
}
```

**Middleware usage:**
```php
// routes/web.php
Route::middleware(['auth:sanctum', 'permission:products.view'])
    ->get('/products', [ProductController::class, 'index']);
```

**Checking in controllers:**
```php
// Direct check
if ($user->hasPermissionTo('products.edit')) {
    // ...
}

// Via middleware (preferred -- see controller constructor above)
$this->middleware('permission:products.view');
```

**Frontend permission guard (Vue):**
```vue
<!-- resources/js/Components/Can.vue -->
<script setup>
import { usePage } from '@inertiajs/vue3'

const props = defineProps({
  permission: { type: String, required: true },
})

const page = usePage()
const can = page.props.auth.permissions.includes(props.permission)
</script>

<template>
  <slot v-if="can" />
</template>
```

**Usage in Vue pages:**
```vue
<Can permission="products.create">
  <Link :href="route('products.create')">New Product</Link>
</Can>
```

**Sharing permissions via Inertia middleware:**
```php
// app/Http/Middleware/HandleInertiaRequests.php
public function share(Request $request): array
{
    return [
        ...parent::share($request),
        'auth' => [
            'user' => $request->user(),
            'permissions' => $request->user()
                ?->getAllPermissions()
                ->pluck('name')
                ->toArray() ?? [],
        ],
        'flash' => [
            'success' => $request->session()->get('success'),
            'error' => $request->session()->get('error'),
        ],
    ];
}
```

Assign roles to users via groups. Roles own permissions. Users never get
permissions directly.

---

## Pattern: Background Jobs

Laravel Queues with Redis driver. Jobs in `app/Jobs/`. Horizon for monitoring
when using Redis.

**Job definition:**
```php
// app/Jobs/ProcessInvoiceJob.php
namespace App\Jobs;

use App\Models\Invoice;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;

class ProcessInvoiceJob implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    public int $tries = 3;
    public int $backoff = 60;

    public function __construct(
        public readonly int $invoiceId
    ) {}

    public function handle(): void
    {
        $invoice = Invoice::findOrFail($this->invoiceId);
        $invoice->process();
    }

    public function failed(\Throwable $exception): void
    {
        // Log failure, notify admin, etc.
        logger()->error("Invoice processing failed: {$this->invoiceId}", [
            'exception' => $exception->getMessage(),
        ]);
    }
}
```

**Dispatching:**
```php
// From a controller or service
ProcessInvoiceJob::dispatch($invoice->id);

// With delay
ProcessInvoiceJob::dispatch($invoice->id)->delay(now()->addMinutes(5));

// On a specific queue
ProcessInvoiceJob::dispatch($invoice->id)->onQueue('invoices');
```

**Horizon setup (Redis driver):**
```php
// config/horizon.php
return [
    'environments' => [
        'production' => [
            'supervisor-1' => [
                'connection' => 'redis',
                'queue' => ['default', 'invoices', 'notifications'],
                'balance' => 'auto',
                'processes' => 10,
                'tries' => 3,
            ],
        ],
        'local' => [
            'supervisor-1' => [
                'connection' => 'redis',
                'queue' => ['default', 'invoices', 'notifications'],
                'balance' => 'simple',
                'processes' => 3,
                'tries' => 3,
            ],
        ],
    ],
];
```

Horizon dashboard at `/horizon`. Failed job handling via `php artisan
queue:failed` and `queue:retry`. Horizon provides metrics, recent jobs,
failed jobs, and queue throughput.

---

## Pattern: Forms Engine

JSON Schema definitions rendered at runtime. Same concept as other stacks.

**Backend models:**
```php
// app/Models/FormDefinition.php
namespace App\Models;

use App\Traits\HasAuditTrail;
use App\Traits\HasUuid;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class FormDefinition extends Model
{
    use HasAuditTrail;
    use HasUuid;
    use SoftDeletes;

    protected $fillable = ['name', 'slug', 'status', 'schema'];

    protected $casts = [
        'schema' => 'array',
        'status' => FormStatus::class,
    ];

    public function submissions()
    {
        return $this->hasMany(FormSubmission::class);
    }
}

// app/Enums/FormStatus.php
namespace App\Enums;

enum FormStatus: string
{
    case Draft = 'draft';
    case Published = 'published';
    case Archived = 'archived';
}
```

**Vue form renderer:**
```vue
<!-- resources/js/Components/DynamicForm.vue -->
<script setup>
import { useForm } from '@inertiajs/vue3'
import { computed } from 'vue'
import FieldRenderer from './FieldRenderer.vue'

const props = defineProps({
  definition: { type: Object, required: true },
  submitUrl: { type: String, required: true },
})

const fields = computed(() => props.definition.schema.fields || [])

const initialData = {}
fields.value.forEach(field => {
  initialData[field.name] = field.default ?? null
})

const form = useForm({ data: initialData })

function submit() {
  form.post(props.submitUrl)
}
</script>

<template>
  <form @submit.prevent="submit">
    <FieldRenderer
      v-for="field in fields"
      :key="field.name"
      :field="field"
      :model-value="form.data[field.name]"
      :error="form.errors[`data.${field.name}`]"
      @update:model-value="form.data[field.name] = $event"
    />
    <button type="submit" :disabled="form.processing">Submit</button>
  </form>
</template>
```

**Server-side validation via custom rule:**
```php
// app/Rules/ValidFormSubmission.php
namespace App\Rules;

use App\Models\FormDefinition;
use Closure;
use Illuminate\Contracts\Validation\ValidationRule;

class ValidFormSubmission implements ValidationRule
{
    public function __construct(
        private readonly FormDefinition $definition
    ) {}

    public function validate(string $attribute, mixed $value, Closure $fail): void
    {
        foreach ($this->definition->schema['fields'] as $field) {
            $fieldValue = $value[$field['name']] ?? null;

            if (($field['required'] ?? false) && blank($fieldValue)) {
                $fail("{$field['label']} is required.");
            }
        }
    }
}
```

Visual builder component in Vue with drag-and-drop field ordering, live
preview, and per-type configuration panels.

---

## Pattern: Workflow Engine

JSON-defined state machines attached to any model via polymorphic relationship.
Same concept as other stacks.

**Models:**
```php
// app/Models/WorkflowDefinition.php
namespace App\Models;

use App\Traits\HasAuditTrail;
use App\Traits\HasUuid;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class WorkflowDefinition extends Model
{
    use HasAuditTrail;
    use HasUuid;
    use SoftDeletes;

    protected $fillable = ['name', 'states', 'transitions'];

    protected $casts = [
        'states' => 'array',      // [{name, label, is_initial, is_final, color, form_slug}]
        'transitions' => 'array', // [{from, to, label, conditions[], actions[]}]
    ];
}

// app/Models/WorkflowInstance.php
class WorkflowInstance extends Model
{
    use HasAuditTrail;
    use HasUuid;

    protected $fillable = ['workflow_definition_id', 'workflowable_type',
                           'workflowable_id', 'current_state'];

    public function definition()
    {
        return $this->belongsTo(WorkflowDefinition::class, 'workflow_definition_id');
    }

    public function workflowable()
    {
        return $this->morphTo();
    }

    public function transitionLogs()
    {
        return $this->hasMany(TransitionLog::class);
    }
}
```

**Transition service:**
```php
// app/Services/WorkflowTransitionService.php
namespace App\Services;

use App\Jobs\WorkflowActionJob;
use App\Models\TransitionLog;
use App\Models\WorkflowInstance;
use Illuminate\Support\Facades\DB;

class WorkflowTransitionService
{
    public function transition(WorkflowInstance $instance, string $transitionName): bool
    {
        $transition = collect($instance->definition->transitions)
            ->first(fn ($t) => $t['from'] === $instance->current_state
                            && $t['to'] === $transitionName);

        if (! $transition) {
            return false;
        }

        if (! $this->conditionsMet($transition, $instance)) {
            return false;
        }

        DB::transaction(function () use ($instance, $transition) {
            $instance->update(['current_state' => $transition['to']]);

            TransitionLog::create([
                'workflow_instance_id' => $instance->id,
                'from_state' => $transition['from'],
                'to_state' => $transition['to'],
                'performed_by' => auth()->id(),
            ]);

            foreach ($transition['actions'] ?? [] as $action) {
                WorkflowActionJob::dispatch($instance->id, $action);
            }
        });

        return true;
    }

    private function conditionsMet(array $transition, WorkflowInstance $instance): bool
    {
        foreach ($transition['conditions'] ?? [] as $condition) {
            if (! ConditionEvaluator::evaluate($condition, auth()->user(), $instance->workflowable)) {
                return false;
            }
        }
        return true;
    }
}
```

**Condition types:** `user_has_role`, `field_equals`, `field_in`,
`is_authenticated`, `is_superuser`.
**Action types:** `notify_user`, `send_email`, `call_webhook`, `update_field`.

Queue jobs execute async actions. Transition logs provide an immutable audit
trail.

---

## Pattern: Feature Toggles

```php
// config/features.php
return [
    'forms' => env('FEATURE_FORMS', false),
    'workflows' => env('FEATURE_WORKFLOWS', false),
    'search' => env('FEATURE_SEARCH', false),
    'horizon' => env('FEATURE_HORIZON', false),
];
```

**Checking:**
```php
// In a service provider
if (config('features.forms')) {
    $this->loadRoutesFrom(base_path('routes/forms.php'));
    $this->loadMigrationsFrom(base_path('database/migrations/forms'));
}

// In a controller or service
if (config('features.search')) {
    // Use Scout search
}

// In a Blade/Vue layout
@if(config('features.forms'))
    <NavLink :href="route('forms.index')">Forms</NavLink>
@endif
```

**Sharing with frontend via Inertia:**
```php
// app/Http/Middleware/HandleInertiaRequests.php
'features' => [
    'forms' => config('features.forms'),
    'workflows' => config('features.workflows'),
    'search' => config('features.search'),
],
```

**Vue usage:**
```vue
<script setup>
import { usePage } from '@inertiajs/vue3'
const features = usePage().props.features
</script>

<template>
  <NavLink v-if="features.forms" :href="route('forms.index')">Forms</NavLink>
</template>
```

When disabled, routes are not registered, migrations can be skipped, and UI
links are hidden. Tied to Docker Compose profiles for optional services like
MeiliSearch and Horizon.

---

## Pattern: Admin

Filament (free, Livewire-based) for the admin panel. Runs alongside the
Inertia frontend without conflict -- Filament uses its own route group and
Livewire rendering.

**Setup:**
```bash
composer require filament/filament
php artisan filament:install --panels
```

**Resource registration:**
```php
// app/Filament/Resources/ProductResource.php
namespace App\Filament\Resources;

use App\Models\Product;
use Filament\Forms;
use Filament\Resources\Resource;
use Filament\Tables;

class ProductResource extends Resource
{
    protected static ?string $model = Product::class;
    protected static ?string $navigationIcon = 'heroicon-o-cube';

    public static function form(Forms\Form $form): Forms\Form
    {
        return $form->schema([
            Forms\Components\TextInput::make('name')->required(),
            Forms\Components\TextInput::make('price')
                ->numeric()->required()->prefix('$'),
            Forms\Components\Select::make('category_id')
                ->relationship('category', 'name'),
        ]);
    }

    public static function table(Tables\Table $table): Tables\Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('uuid')->label('ID')->searchable(),
                Tables\Columns\TextColumn::make('name')->searchable()->sortable(),
                Tables\Columns\TextColumn::make('price')->money()->sortable(),
                Tables\Columns\TextColumn::make('created_at')->dateTime()->sortable(),
                Tables\Columns\TextColumn::make('creator.name')->label('Created By'),
            ])
            ->filters([
                Tables\Filters\TrashedFilter::make(),
            ]);
    }
}
```

**Auth gating:**
```php
// app/Providers/Filament/AdminPanelProvider.php
->authMiddleware([
    Authenticate::class,
])
->authGuard('web')
```

Admin access restricted to users with the `admin` role. Filament provides its
own auth gate -- configure it to check Spatie roles.

---

## Pattern: Testing

Pest PHP (preferred) for expressive, modern test syntax. Feature tests hitting
a real database.

**Feature test (Inertia integration):**
```php
// tests/Feature/ProductTest.php
use App\Models\Product;
use App\Models\User;

beforeEach(function () {
    $this->user = User::factory()->create();
    $this->user->assignRole('editor');
});

test('index returns products page', function () {
    Product::factory()->count(3)->create();

    $this->actingAs($this->user)
        ->get(route('products.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Products/Index')
            ->has('products.data', 3)
        );
});

test('store creates a product in the database', function () {
    $this->actingAs($this->user)
        ->post(route('products.store'), [
            'name' => 'Widget',
            'price' => 9.99,
        ])
        ->assertRedirect(route('products.index'));

    $this->assertDatabaseHas('products', [
        'name' => 'Widget',
        'price' => 9.99,
        'created_by' => $this->user->id,
    ]);
});

test('store validates required fields', function () {
    $this->actingAs($this->user)
        ->post(route('products.store'), [])
        ->assertSessionHasErrors(['name', 'price']);
});
```

**Permission tests (allowed and denied):**
```php
test('viewer cannot create products', function () {
    $viewer = User::factory()->create();
    $viewer->assignRole('viewer');

    $this->actingAs($viewer)
        ->post(route('products.store'), [
            'name' => 'Widget',
            'price' => 9.99,
        ])
        ->assertForbidden();

    $this->assertDatabaseMissing('products', ['name' => 'Widget']);
});

test('editor can create products', function () {
    $this->actingAs($this->user)
        ->post(route('products.store'), [
            'name' => 'Widget',
            'price' => 9.99,
        ])
        ->assertRedirect();

    $this->assertDatabaseHas('products', ['name' => 'Widget']);
});
```

**Factory example:**
```php
// database/factories/ProductFactory.php
namespace Database\Factories;

use Illuminate\Database\Eloquent\Factories\Factory;

class ProductFactory extends Factory
{
    public function definition(): array
    {
        return [
            'name' => fake()->words(3, true),
            'price' => fake()->randomFloat(2, 1, 999),
            'category_id' => null,
        ];
    }
}
```

**Rules (universal):**
- Assert against database state, not hardcoded strings
- No empty test bodies
- Test both allowed and denied permission cases
- Integration tests via HTTP feature tests, not isolated model tests
- Real database -- never mock the database

---

## Pattern: Docker Infrastructure

| Service | Image/Build | Port | Health Check |
|---------|------------|------|-------------|
| Backend | PHP-FPM + Nginx (or Octane with FrankenPHP) | 8000 | `/up` |
| Vite Dev Server | Node.js (Vite HMR for Vue) | 5173 | HTTP check |
| Postgres | postgres:16 | 5432 | pg_isready |
| Redis | redis:7-alpine | 6379 | redis-cli ping |
| Queue Worker | Same image, `php artisan queue:work` entrypoint | -- | -- |
| Horizon | Same image, `php artisan horizon` entrypoint | -- | -- |
| MinIO | minio/minio | 9000/9001 | -- |
| Mailpit | axllent/mailpit | 8025/1025 | -- |
| MeiliSearch | getmeili/meilisearch (optional) | 7700 | -- |

The Vite dev server runs in a separate container during development for Vue
hot module replacement. In production, Vite builds static assets that are
served by Nginx alongside the PHP-FPM backend. The queue worker and Horizon
use the same Docker image with different entrypoints.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Laravel Pint (PHP style), Prettier (Vue/JS formatting), ESLint
  (Vue/JS linting)
- **Test job:** Pest PHP with Postgres + Redis services, feature tests against
  real database
- **Audit job:** `composer audit` for PHP dependency vulnerabilities, `npm
  audit` for JS dependency vulnerabilities
- **Build job:** `npm run build` to verify Vite asset compilation

CI must pass before merge. Tests run against a real database with seed data.

---

## Pattern: Security

**Session hardening:** Laravel's session driver handles token management.
httpOnly cookies, secure in production, sameSite lax. Configurable expiry via
`config/session.php`. CORS restricted to explicit origin whitelist via
`config/cors.php`. Rate limiting on auth endpoints via Laravel's built-in
`throttle` middleware.

**Authorization:** Permission middleware on every route group. Ownership checks
on mutations -- verify record belongs to current user's scope. Never trust
client-provided IDs alone.

**Input validation:** Form requests at controller boundary. Eloquent mass
assignment protection via `$fillable`. File upload validation: MIME whitelist,
size limits, filename sanitization via `Str::slug()`.

**SSRF protection:** URL validator on all outgoing HTTP requests (via
`Http::preventStrayRequests()` in tests, custom middleware in production).
Block private IPs, localhost, non-HTTP schemes.

**CSRF protection:** Laravel's built-in CSRF middleware. Inertia includes the
CSRF token automatically on all requests.

**Encryption:** `APP_KEY` for application-level encryption. Sensitive fields
encrypted at rest via `$casts` with `encrypted` type.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| PHP Formatting | Laravel Pint (PHP-CS-Fixer wrapper) | `pint.json` |
| PHP Max line length | 120 characters | `pint.json` |
| Vue/JS Formatting | Prettier | `.prettierrc` |
| Vue/JS Linting | ESLint | `.eslintrc.js` |
| Import sorting | Pint (PHP), ESLint (JS) | Configured in respective files |
| Pre-commit hooks | Husky + lint-staged | `.husky/`, `package.json` |

Run `./vendor/bin/pint` and `npm run lint` before committing. Follow Laravel
conventions: PSR-12 for PHP, single-file components for Vue, Composition API
with `<script setup>`.

---

## What Carries Over

### From Existing Templates (reusable as-is)

- Docker Compose infrastructure pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`
- CI pipeline structure (lint, test, audit jobs)

### Shared Concepts (same mental model, Laravel implementation)

- Permission model (group-based, Spatie roles map to the same pattern as
  Django's `config/permissions.py` and Rails' Pundit policies)
- Forms engine (JSON Schema definitions, same field types, same lifecycle:
  draft -> published -> archived)
- Workflow engine (same state machine pattern, same condition and action types)
- Audit trail pattern (`created_by`/`updated_by` via `auth()->user()`,
  equivalent to Django's `Tracking` model and Rails' `Auditable` concern)
- Agent shim pattern (same interface, PHP implementation)

### Shared Infrastructure (identical across all stacks)

- Docker Compose pattern (Postgres, Redis, MinIO, Mailpit)
- Health check pattern
- Feature toggle pattern (env-based)
- `.github/` templates (issues, PRs)
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`

### Needs Porting (same concept, new implementation)

- ORM traits and base model (Eloquent replaces Django ORM / Active Record)
- Session auth (Sanctum replaces auth1 app / Devise)
- Permission middleware (Spatie replaces custom permission system / Pundit)
- Job queue (Laravel Queues replaces Celery / Solid Queue)
- Admin panel (Filament replaces Django Admin / ActiveAdmin)
- Form builder (Vue replaces React / Stimulus widgets)
- Workflow builder (Vue replaces ReactFlow / Stimulus + Turbo)
- Inertia protocol (replaces GraphQL / HTML-over-the-wire)

---

## Build Order

### Phase 0: Scaffolding
- [ ] Laravel 11 app with Eloquent, Inertia.js, Vue 3
- [ ] Traits: HasAuditTrail, HasUuid (SoftDeletes is built-in)
- [ ] Docker Compose (PHP-FPM + Nginx, Vite, Postgres, Redis, MinIO, Mailpit)
- [ ] Health check endpoint (`/up`)
- [ ] Laravel Pint + ESLint + Prettier configuration

### Phase 1: Auth + Permissions
- [ ] Sanctum session auth (login, logout, registration)
- [ ] HandleInertiaRequests middleware (share auth, permissions, flash)
- [ ] User model with Spatie HasRoles trait
- [ ] Permission seeder (roles, permissions, default groups)
- [ ] Permission middleware on route groups
- [ ] Vue `Can` component for frontend permission guards
- [ ] Throttle middleware on auth endpoints

### Phase 2: Core Inertia CRUD
- [ ] Resource controllers with Inertia::render()
- [ ] Form requests for validation
- [ ] Vue pages (Index, Create, Show, Edit) with useForm()
- [ ] Layouts and reusable components
- [ ] Flash message handling
- [ ] Pagination via Inertia

### Phase 3: Forms Engine
- [ ] FormDefinition + FormSubmission models
- [ ] Field types + server-side validation (custom rule)
- [ ] Logic engine (conditions, calculations)
- [ ] DynamicForm Vue component (renderer)
- [ ] FormBuilder Vue component (visual builder, drag-and-drop)

### Phase 4: Workflow Engine
- [ ] WorkflowDefinition + WorkflowInstance + TransitionLog models
- [ ] WorkflowTransitionService (state machine)
- [ ] ConditionEvaluator + WorkflowActionJob
- [ ] Inertia CRUD + transition endpoints
- [ ] WorkflowBuilder Vue component

### Phase 5: Infrastructure + Polish
- [ ] File uploads (Flysystem + MinIO)
- [ ] Email service (Laravel Mail + Mailpit)
- [ ] In-app notifications
- [ ] Feature toggles (env-based, shared via Inertia)
- [ ] Laravel Queues + Horizon setup
- [ ] Filament admin panel
- [ ] MeiliSearch + Scout integration (optional)
- [ ] Seed data + examples
- [ ] CI pipeline (Pint, ESLint, Pest, composer audit, npm audit)
- [ ] README, CLAUDE.md, bootstrap.md
