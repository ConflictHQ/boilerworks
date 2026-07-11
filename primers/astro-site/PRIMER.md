# Boilerworks Astro Site -- Primer

> Astro on Cloudflare Pages. Content-first site with islands
> architecture -- static HTML by default, interactive components only
> where needed. Choose this for blogs, docs, marketing sites, and
> landing pages.

**Status:** Planned (Tier 3)
**Repo:** `ConflictHQ/boilerworks-astro-site`
**Sibling variant:** None

## Table of Contents

1. [When to Choose This Stack](#when-to-choose-this-stack)
2. [Architecture](#architecture)
3. [Stack Mapping](#stack-mapping)
4. [Pattern: Content Collections](#pattern-content-collections)
5. [Pattern: Islands Architecture](#pattern-islands-architecture)
6. [Pattern: API Layer](#pattern-api-layer)
7. [Pattern: Auth](#pattern-auth)
8. [Pattern: Permissions](#pattern-permissions)
9. [Pattern: Background Jobs](#pattern-background-jobs)
10. [Pattern: Forms Engine](#pattern-forms-engine)
11. [Pattern: Workflow Engine](#pattern-workflow-engine)
12. [Pattern: Feature Toggles](#pattern-feature-toggles)
13. [Pattern: Admin](#pattern-admin)
14. [Pattern: Testing](#pattern-testing)
15. [Pattern: Docker Infrastructure](#pattern-docker-infrastructure)
16. [Pattern: CI/CD](#pattern-cicd)
17. [Pattern: Security](#pattern-security)
18. [Code Style & Enforcement](#code-style--enforcement)
19. [What Carries Over](#what-carries-over)
20. [Build Order](#build-order)

---

## When to Choose This Stack

### Ideal For

- Content-heavy sites: blogs, documentation, marketing pages, landing
  pages. Astro ships zero JavaScript by default -- pages are pure HTML
  until you opt into interactivity.
- Multi-framework teams. Astro's islands architecture lets you use
  Svelte, React, or Vue for interactive components without committing
  to one framework for the whole site.
- Sites where performance and SEO are paramount. Static-first with
  optional SSR per route means fast TTFB and perfect Lighthouse scores.

### Not Ideal For

- Apps with lots of interactivity (dashboards, real-time features,
  complex forms). Astro is built for content, not applications.
  Use sveltekit-full, remix-full, or nuxt-full instead.
- Sites that need user auth on every page. Astro can do SSR, but it's
  not its strength. Use a full-stack template.
- Teams that want a single framework everywhere. Astro's islands are
  powerful but add conceptual overhead if you only use one framework.

---

## Architecture

```
Browser
  |
  v (HTTPS)
  |
Astro (Cloudflare Pages)
  |-- .astro pages (static HTML, SSG by default)
  |-- Islands (Svelte/React/Vue components, hydrated on demand)
  |-- Content Collections (Markdown/MDX)
  |-- SSR opt-in per route (@astrojs/cloudflare)
  |-- R2 (optional, for dynamic assets)
  +-- Tailwind CSS
```

### Key Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | Astro | Content-first, zero JS by default, islands architecture |
| Content | Content Collections (Markdown/MDX) | Type-safe content with schema validation |
| Islands | Svelte, React, or Vue (pick per component) | Interactive components only where needed |
| Rendering | SSG by default, SSR opt-in | Best performance for content sites |
| Database | None by default | Content from files; optional D1/Turso for dynamic features |
| Storage | Cloudflare R2 (optional) | S3-compatible for dynamic assets |
| Styling | Tailwind CSS | Utility-first, tree-shaken |
| Deploy | Cloudflare Pages | `@astrojs/cloudflare` adapter |

---

## Stack Mapping

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Base model (audit trails) | N/A (content from files) | Optional D1 for dynamic features |
| Soft deletes | N/A | Content is version-controlled in git |
| External IDs (no integer PKs) | Slug-based | Content addressed by slug |
| API contract | SSR endpoints or static JSON | Minimal API surface |
| MutationResult pattern | N/A (mostly read-only) | Optional for SSR endpoints |
| Auth | N/A by default | Optional Cloudflare Access for gated content |
| Permissions | N/A | Content site, no user permissions |
| Background jobs | N/A | Static site, no background work |
| Forms engine | N/A | External form service or SSR endpoint |
| Workflow engine | N/A | Content site |
| Feature toggles | Env vars | Build-time or runtime (SSR) |
| Admin panel | N/A | Content managed in git/CMS |
| Testing framework | vitest + Playwright | Unit + E2E |
| Linter/Formatter | Prettier + ESLint | Standard |
| Package manager | npm or pnpm | `package.json` |
| Migrations | N/A | No database by default |

---

## Pattern: Content Collections

Astro's Content Collections provide type-safe content with schema
validation via the content layer API.

```typescript
// src/content.config.ts
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
```

```astro
---
// src/pages/blog/[slug].astro
import { getCollection, render } from "astro:content";

export async function getStaticPaths() {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return posts.map((post) => ({ params: { slug: post.id }, props: { post } }));
}

const { post } = Astro.props;
const { Content } = await render(post);
---
<article>
  <h1>{post.data.title}</h1>
  <time>{post.data.pubDate.toLocaleDateString()}</time>
  <Content />
</article>
```

---

## Pattern: Islands Architecture

Interactive components are hydrated only where needed. Everything else
is static HTML.

```astro
---
// src/pages/index.astro
import SearchWidget from "../components/SearchWidget.svelte";
import Newsletter from "../components/Newsletter.tsx";
---
<html>
  <body>
    <h1>Welcome</h1>
    <p>This is static HTML. No JavaScript shipped for this text.</p>

    <!-- Svelte component, hydrated on visible -->
    <SearchWidget client:visible />

    <!-- React component, hydrated on idle -->
    <Newsletter client:idle />
  </body>
</html>
```

**Hydration directives:**
- `client:load` -- hydrate immediately on page load
- `client:idle` -- hydrate when browser is idle
- `client:visible` -- hydrate when component enters viewport
- `client:media` -- hydrate when media query matches
- No directive -- rendered as static HTML, zero JavaScript

---

## Pattern: API Layer

Mostly read-only. For dynamic features, use SSR endpoints.

```typescript
// src/pages/api/subscribe.ts (SSR endpoint)
export const prerender = false;

export async function POST({ request, locals }: APIContext) {
  const body = await request.json();
  // Validate and process...
  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
}
```

---

## Pattern: Auth

N/A by default. For gated content, use Cloudflare Access or a simple
API-key check on SSR endpoints.

---

## Pattern: Permissions

N/A. Content sites do not need a permission system.

---

## Pattern: Background Jobs

N/A. Content sites do not need background jobs.

---

## Pattern: Forms Engine

N/A. Use an external form service (Formspree, Netlify Forms) or a
simple SSR endpoint for contact forms.

---

## Pattern: Workflow Engine

N/A.

---

## Pattern: Feature Toggles

Environment variables for build-time toggles.

```typescript
// astro.config.mjs
const showBlog = import.meta.env.FEATURE_BLOG !== "false";
```

---

## Pattern: Admin

N/A. Content is managed in git (Markdown/MDX files) or via an external
CMS with a content layer loader.

---

## Pattern: Testing

vitest for component/integration tests, Playwright for E2E.

```typescript
// tests/e2e/blog.test.ts
import { test, expect } from "@playwright/test";

test("blog index lists published posts", async ({ page }) => {
  await page.goto("/blog");
  const posts = page.locator("article");
  await expect(posts).not.toHaveCount(0);
});

test("blog post renders content", async ({ page }) => {
  await page.goto("/blog");
  const firstLink = page.locator("article a").first();
  await firstLink.click();
  await expect(page.locator("h1")).toBeVisible();
  await expect(page.locator("article")).toBeVisible();
});

test("draft posts are not listed", async ({ page }) => {
  await page.goto("/blog");
  await expect(page.locator("text=Draft Post")).not.toBeVisible();
});
```

**Rules (universal):**
- No empty test bodies
- Test real rendered output, not implementation details
- E2E tests verify the user-visible result

---

## Pattern: Docker Infrastructure

**NOTE:** No Docker in production. Cloudflare Pages deploys via Wrangler
or git integration.

Local development uses `astro dev`. No Docker needed.

---

## Pattern: CI/CD

GitHub Actions pipeline:

- **Lint job:** Prettier + ESLint
- **Build job:** `astro build` (catches type errors, broken links)
- **Test job:** vitest + Playwright
- **Deploy job:** Cloudflare Pages (Wrangler or git integration)
- **Audit job:** `npm audit`

---

## Pattern: Security

**Content Security Policy:** Set via Cloudflare Pages headers config or
`_headers` file.

**No user input by default.** Static sites have minimal attack surface.

**SSR endpoints (if used):** Input validation, rate limiting via
Cloudflare rules.

**Subresource Integrity:** For any external scripts or styles.

---

## Code Style & Enforcement

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | Prettier + prettier-plugin-astro | `.prettierrc` |
| Linting | ESLint + eslint-plugin-astro | `eslint.config.js` |
| Type checking | `astro check` | `tsconfig.json` |

---

## What Carries Over

### Shared Infrastructure (adapted for edge)

- `.github/` templates, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`
- Prettier + ESLint configuration patterns

### Needs Building (new for astro-site)

- Astro scaffold with @astrojs/cloudflare adapter
- Content Collection schemas and example content
- Islands examples (Svelte, React, or Vue component)
- Tailwind CSS integration
- Playwright E2E test suite
- CI pipeline with build + deploy

---

## Build Order

### Phase 0: Scaffolding
- [ ] Astro project, TypeScript, @astrojs/cloudflare
- [ ] Tailwind CSS, Prettier + ESLint + astro plugins
- [ ] Content Collections config with example schema
- [ ] Base layout, navigation, footer

### Phase 1: Content
- [ ] Blog collection with example posts (Markdown/MDX)
- [ ] Blog index page with pagination
- [ ] Blog post page with metadata
- [ ] Tag listing and filtering
- [ ] RSS feed

### Phase 2: Islands + Interactivity
- [ ] Island framework integration (Svelte, React, or Vue)
- [ ] Search component (client:visible)
- [ ] Contact form (SSR endpoint or external service)
- [ ] Theme toggle, mobile nav, or other interactive widgets

### Phase 3: Infrastructure + Polish
- [ ] SEO (sitemap, OpenGraph, structured data)
- [ ] Image optimization (@astrojs/image)
- [ ] Performance audit (Lighthouse)
- [ ] Playwright E2E tests
- [ ] CI pipeline (lint, build, test, deploy)
- [ ] README, CLAUDE.md
