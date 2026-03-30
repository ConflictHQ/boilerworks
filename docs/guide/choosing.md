# Choosing a Template

## By what you're building

| If you're building... | Use |
|----------------------|-----|
| SaaS with user accounts, teams, billing | Full |
| Internal tool / admin app | Full |
| Public API for developers | Micro |
| Microservice in a larger system | Micro |
| Marketing site or landing page | Edge |
| Globally distributed API | Edge |

## By your team's stack

| Team knows... | Reach for |
|--------------|-----------|
| Python | `django-nextjs`, `django-micro`, `fastapi-micro` |
| Ruby | `rails-nextjs`, `rails-hotwire`, `rails-micro` |
| TypeScript (Node) | `nestjs-nextjs`, `nestjs-micro`, `express-micro` |
| PHP | `laravel-vue`, `laravel-micro` |
| Java / Kotlin | `spring-angular`, `spring-micro` |
| Go | `go-nextjs`, `go-micro` |
| Elixir | `phoenix-liveview`, `phoenix-micro` |
| Rust | `rust-micro` |
| Full-stack JS (no separate backend) | `remix-full`, `sveltekit-full`, `remix-edge`, `sveltekit-edge` |

## By frontend preference

| Frontend | Full templates |
|----------|---------------|
| Next.js (React) | `django-nextjs`, `rails-nextjs`, `nestjs-nextjs`, `go-nextjs` |
| Vue (Inertia) | `laravel-vue` |
| Angular | `spring-angular` |
| Hotwire (server-rendered) | `rails-hotwire` |
| LiveView (server-rendered) | `phoenix-liveview` |
| Remix | `remix-full`, `remix-edge` |
| SvelteKit | `sveltekit-full`, `sveltekit-edge` |

## Crown jewels

**`django-nextjs`** — the reference implementation. Every pattern in the catalogue was refined here first. Django 5 backend with Strawberry GraphQL, Next.js 16 frontend with Apollo Client. If you're unsure, start here.

**`rails-hotwire`** — the most opinionated Rails stack. Hotwire (Turbo + Stimulus) + Tailwind CSS 4 + Pundit + Solid Queue. Zero JavaScript build complexity, full interactivity.

**`fastapi-micro`** — async-native Python API. The fastest way to ship a Python microservice that can handle real load.
