# Boilerworks — Next.js Frontend Reference

The Boilerworks Next.js frontend is a complete, production-ready SPA that ships
with every GraphQL-backed template. It is backend-agnostic — it talks GraphQL
and doesn't care what serves it. This document is the reference for all stacks
that use Next.js as their frontend.


## Stacks Using This Frontend

- `django-nextjs`
- `nestjs-nextjs`
- `saleor-nextjs`
- `rails-nextjs`
- `spring-nextjs`
- `go-nextjs`


## Technology Stack

- **Next.js 16** — App Router, React 19, TypeScript
- **Apollo Client** — GraphQL queries, mutations, subscriptions
- **shadcn/ui** — Component library (Radix primitives + Tailwind CSS)
- **Tailwind CSS 4**
- **React Hook Form** — Form state management
- **@dnd-kit** — Drag-and-drop for builders
- **Recharts** — Dashboard charts
- **TanStack Table** — Data tables with server-side pagination
- **next-intl** — i18n (7 languages)
- **next-themes** — Dark mode


## Project Structure

```
frontend/ (or apps/web/ in monorepo stacks)
├── app/
│   ├── (app)/              # Authenticated routes (auth gate in layout)
│   │   ├── layout.tsx      # Auth check, sidebar, breadcrumbs
│   │   ├── dashboard/      # Dashboard with charts
│   │   ├── forms/          # Form management + builder
│   │   ├── workflows/      # Workflow management + builder
│   │   ├── settings/       # User/org settings
│   │   └── {domain}/       # Your domain pages go here
│   ├── (login)/            # Public routes
│   │   └── auth/           # Login page
│   └── global-error.tsx    # Sentry error boundary
│
├── components/
│   ├── ui/                 # shadcn/ui components (Button, Card, Dialog, etc.)
│   ├── forms/              # DynamicForm, FormBuilder, field-registry
│   ├── workflows/          # WorkflowBuilder (ReactFlow), TagInput
│   ├── data-table/         # DataTable, DataTableServer (TanStack)
│   ├── AppSidebar.tsx      # Main navigation sidebar
│   ├── Breadcrumbs.tsx     # Auto breadcrumbs from route
│   └── ThemeToggle.tsx     # Dark/light mode toggle
│
├── graphql/
│   └── {domain}/
│       ├── {domain}.types.ts       # TypeScript interfaces
│       ├── {domain}.queries.ts     # gql query constants (SCREAMING_SNAKE)
│       ├── {domain}.mutations.ts   # gql mutation constants
│       └── {domain}.hooks.ts       # useXxx() custom hooks
│
├── hooks/                  # Utility hooks
│   ├── useDebounce.ts
│   ├── useLocalStorage.ts
│   ├── useCopyToClipboard.ts
│   └── useConfirm.ts
│
├── lib/
│   ├── apollo/             # Apollo Client setup
│   │   ├── client.ts       # Client factory
│   │   ├── cache.ts        # Cache config
│   │   ├── error-link.ts   # Error handling (UNAUTHENTICATED -> redirect)
│   │   └── auth-link.ts    # Auth header injection
│   ├── routes.ts           # Route constants + labels
│   ├── permissions.ts      # PermissionSlug enum
│   └── utils.ts            # Shared utilities
│
├── messages/               # i18n translations (7 languages)
│   ├── en.json
│   ├── es.json
│   ├── fr.json
│   ├── de.json
│   ├── pt.json
│   ├── ja.json
│   └── zh.json
│
├── public/                 # Static assets
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```


## Wiring to a New Backend

When connecting this frontend to a new backend, only these things change:

1. **GraphQL endpoint URL** — env var `NEXT_PUBLIC_API_URL` or
   `NEXT_PUBLIC_GRAPHQL_URL`.
2. **Auth flow** — cookie name, login/callback route. Usually just env config.
3. **CORS origin** — the backend must allow the frontend's URL.

Everything else — components, hooks, pages, i18n, theme — is identical.


## Key Patterns

### GraphQL Hooks

Arrow functions, explicit types, explicit `fetchPolicy`. Hooks live in
`graphql/{domain}/{domain}.hooks.ts`. Always type the generic parameters on
`useQuery` and `useMutation`.

For `cache-and-network`, gate loading on `loading && !data` to avoid spinners
during background refetch. Never call `useQuery` in Server Components — use
`getClient().query()` instead.

```typescript
export const useProducts = () => {
  const { data, loading, error } = useQuery<ProductsData>(GET_PRODUCTS, {
    fetchPolicy: "cache-and-network",
  });
  return { products: data?.products ?? [], loading, error };
};

export const useCreateProduct = () =>
  useMutation<CreateProductData>(CREATE_PRODUCT, {
    refetchQueries: [GET_PRODUCTS],
  });
```

### Auth Gate

- `(app)/layout.tsx` checks for a valid session.
- An `UNAUTHENTICATED` GraphQL error triggers the Apollo error link, which
  redirects to the login page.
- Session is stored as an httpOnly cookie set by the backend.

### Permission Guards

Server Component:

```typescript
await requirePermission(PermissionSlug.ProductView);
```

Client Component:

```tsx
<PermissionGuard permission={PermissionSlug.ProductView}>
  <ProductList />
</PermissionGuard>
```

### Forms Engine

DynamicForm reads a JSON schema. The field-registry maps field types to
widgets. React Hook Form manages state.

FormBuilder provides @dnd-kit drag-and-drop editing with a live preview and
per-type config panels.

21+ field types: `text`, `textarea`, `number`, `email`, `phone`, `url`, `date`,
`time`, `datetime`, `select`, `multi_select`, `radio`, `checkbox`, `toggle`,
`file`, `image`, `rich_text`, `rating`, `slider`, `color`, `signature`.

### Workflow Builder

- ReactFlow canvas for visual state machine editing.
- Click-to-edit panels for states and transitions.
- Conditions/actions editors with TagInput.
- Form picker to attach forms to states.
- Role assignment for states.

### Data Tables

- TanStack Table with server-side pagination.
- Sortable, filterable columns.
- Row selection and bulk actions.
- Export to CSV.

### i18n

- next-intl with 7 languages: en, es, fr, de, pt, ja, zh.
- Translation files in `messages/{locale}.json`.
- `useTranslations()` hook in components.

### Dark Mode

- next-themes provider in root layout.
- `ThemeToggle` component in the header.
- All shadcn/ui components support dark mode via CSS variables.


## Adding a New Domain Page

1. Create `graphql/{domain}/` with types, queries, mutations, and hooks files.
2. Create `app/(app)/{domain}/page.tsx` — list page.
3. Create `app/(app)/{domain}/[id]/page.tsx` — detail page.
4. Create `app/(app)/{domain}/new/page.tsx` — create page.
5. Add the route to the sidebar in `components/AppSidebar.tsx`.
6. Add the route label in `lib/routes.ts`.
