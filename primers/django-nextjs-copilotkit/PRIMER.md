# Boilerworks Django + Next.js + CopilotKit -- Primer

> django-nextjs with an agentic in-app copilot pre-wired. CopilotKit provides
> the copilot UI in the Next.js frontend; a Pydantic AI agent served from
> Django over the AG-UI protocol provides the intelligence, with the forms
> and workflow engines as its action surface. Choose this when the app should
> ship with an in-app AI copilot from day one.

**Status:** Done
**Repo:** `ConflictHQ/boilerworks-django-nextjs-copilotkit`
**Sibling variant:** [django-nextjs](../django-nextjs/PRIMER.md) (the base -- everything except the copilot layer is identical)

---

## Table of Contents

1. [When to Choose This Stack](#when-to-choose-this-stack)
2. [Architecture](#architecture)
3. [Stack Mapping (Delta)](#stack-mapping-delta)
4. [Pattern: The Copilot Agent](#pattern-the-copilot-agent)
5. [Pattern: Agent Tools](#pattern-agent-tools)
6. [Pattern: Copilot Auth](#pattern-copilot-auth)
7. [Pattern: Human-in-the-Loop](#pattern-human-in-the-loop)
8. [Pattern: Frontend Copilot Surface](#pattern-frontend-copilot-surface)
9. [Pattern: Testing the Copilot](#pattern-testing-the-copilot)
10. [Configuration](#configuration)
11. [What Carries Over](#what-carries-over)
12. [Build Order](#build-order)

Everything not listed here -- models, GraphQL, auth, permissions, background
jobs, forms engine, workflow engine, feature toggles, admin, Docker, CI/CD,
security, code style -- is inherited unchanged from the base:
read [django-nextjs/PRIMER.md](../django-nextjs/PRIMER.md) first.

---

## When to Choose This Stack

### Ideal For

- Apps that should ship with an in-app AI copilot from day one -- chat
  surface, generative UI, agent actions wired to real business objects.
- Teams that want the copilot's intelligence in Python, next to the ORM,
  permissions, and Celery -- not in a separate Node service.
- Products where the copilot must respect the same auth and group-based
  permissions as the human user it assists.

### Not Ideal For

- Apps with no copilot requirement -- use django-nextjs; this variant adds
  an LLM dependency and an extra frontend provider for no benefit.
- Copilots that must run without a Python backend -- CopilotKit's Node
  runtime alone may suffice there.

### vs django-nextjs

The only delta is the copilot layer. If the copilot requirement appears
mid-project on a django-nextjs codebase, port `backend/copilot/` and the
frontend copilot module across -- both are deliberately isolated for exactly
that move.

---

## Architecture

```
Browser
  +-- Next.js 16 (App Router, React 19, TypeScript)
        |-- CopilotKit provider + sidebar (@copilotkit/react-core, react-ui)
        |-- useCopilotReadable: page context -> agent
        |-- Generative UI: tool results rendered as components
        +-- /api/copilotkit (Next.js route: CopilotRuntime bridge,
              |              forwards session cookies)
              v
        POST /app/copilot/agui/  (Django async view, session-auth gated)
              |
              v
        Pydantic AI agent (AG-UI protocol, Anthropic model)
              |-- deps: request.user
              +-- tools -> forms engine, workflow engine, scoped queries
                    (every tool re-checks group permissions)
```

The agent lives **in the Django process**. No separate agent service, no
Node-side intelligence: the Next.js API route is a thin protocol bridge.
Tool calls execute with direct ORM access under the calling user's
permissions, and workflow transitions fire the engine's own conditions,
actions, and audit trail.

### Key Technology Choices (Delta)

| Layer | Technology | Why |
|-------|-----------|-----|
| Copilot UI | CopilotKit 1.63 (React) | Production chat + generative UI + HITL primitives; headless option |
| Agent protocol | AG-UI | Open protocol; decouples UI from agent; ports to fastapi-nextjs |
| Agent framework | pydantic-ai-slim 2.12 (`[anthropic,ag-ui]`) | Python-native, typed deps/tools; `pydantic_ai.ui.ag_ui.AGUIAdapter` slots into a Django async view |
| Model | Anthropic Claude (configurable) | `COPILOT_MODEL` env (default `anthropic:claude-sonnet-5`); provider-agnostic via Pydantic AI |

One deployment note: SSE responses are buffered under WSGI `runserver` (the
copilot works, but replies arrive complete). Serve `config/asgi.py` under
uvicorn/daphne for token-by-token streaming.

---

## Stack Mapping (Delta)

| Universal Concept | This Stack | Notes |
|-------------------|-----------|-------|
| Copilot agent | `copilot` app, Pydantic AI | Agent + tools + deps in `backend/copilot/` |
| Agent endpoint | `POST /app/copilot/agui/` | Django async view, SSE streaming, session auth |
| Copilot UI | `frontend/copilot/` | Provider, sidebar, generative UI, HITL components |
| UI <-> agent bridge | `/api/copilotkit` route | CopilotRuntime + AG-UI HttpAgent, cookie forwarding |
| Copilot feature flag | `config/features.py` | Same toggle pattern as every other feature |

---

## Pattern: The Copilot Agent

One agent, defined once, with typed deps carrying the authenticated user:

```python
# backend/copilot/agent.py (shape; see repo for the real thing)
@dataclass
class CopilotDeps:
    user: AbstractBaseUser  # the authenticated Django user -- never anonymous

def build_agent(model=None) -> Agent[CopilotDeps]:
    agent = Agent(
        model or _configured_model(),   # lazy AnthropicModel; tests inject TestModel
        deps_type=CopilotDeps,
        system_prompt=SYSTEM_PROMPT,
        retries=2,
    )
    for tool in TOOLS:
        agent.tool(tool)
    return agent
```

The Django async view (`copilot/views.py`) authenticates the request
(401 before any model work), rate-limits it, parses the body with
`AGUIAdapter.build_run_input`, and streams
`adapter.encode_stream(adapter.run_stream(deps=CopilotDeps(user=user)))`
back as a `StreamingHttpResponse`. No ASGI mount, no Starlette -- the
platform's session middleware and `request.user` apply natively.

---

## Pattern: Agent Tools

Tools are thin wrappers over existing engines -- no new business logic
(v0 = scaffolding, zero business logic). Every tool:

1. Re-checks the calling user's group-based permissions
   (`P.PERMISSION.check(ctx.deps.user)` -- same pattern as GraphQL).
2. Returns permission-denied as a *tool result*, not an exception, so the
   agent can explain rather than crash.
3. Speaks external IDs only (`guid`/slug) -- never integer PKs.

Shipped tools (six): `list_form_definitions`, `get_form_definition`,
`draft_form_definition` (drafts land unpublished in the versioned
lifecycle), `list_workflow_states`, `list_available_transitions`,
`execute_workflow_transition` (HITL-gated, below).

Adding a domain tool = a sync implementation + async wrapper pair in
`backend/copilot/agent.py`, added to the `TOOLS` tuple: permission check
first, engine call, typed dict return. If the frontend should render the
result, mirror the tool name in `frontend/copilot/config.ts`
(`COPILOT_TOOL_*`) -- a name mismatch means the render silently never fires.

---

## Pattern: Copilot Auth

Session auth end to end -- the copilot has no auth mechanism of its own:

- The browser talks to the Next.js `/api/copilotkit` route on the app's own
  origin; its httpOnly cookies ride along automatically.
- The route builds a per-request runtime and authenticates the
  server-to-server hop to Django's `/app/copilot/agui/` with
  `Authorization: Session <key>` read from the `backend_jwt` cookie -- the
  same credential the Apollo clients send. (Django's own session cookie
  lives on the backend origin and never reaches the Next.js route, so
  cookie forwarding alone cannot authenticate; this bites every
  split-origin Django+SPA setup.)
- `Auth0SessionMiddleware` resolves the user exactly as it does for
  GraphQL; anonymous requests are rejected with 401 before any model call,
  and the endpoint is rate-limited.
- Tools re-check permissions per call: the agent can only do what the
  logged-in user can do. Test both the allowed and the denied case for
  every permission-gated tool.

---

## Pattern: Human-in-the-Loop

Mutating actions with consequences (workflow transitions) never execute on
the agent's first attempt:

1. `execute_workflow_transition` without `confirmed=true` returns a
   `confirmation_required` payload describing exactly what would happen
   (workflow name, from/to state labels) and changes nothing.
2. The agent then calls `confirm_workflow_transition` -- a **frontend** tool
   registered by CopilotKit (`renderAndWaitForResponse`) that renders the
   approve/deny card and returns `{approved: true|false}`. The frontend tool
   name is deliberately distinct from every backend tool name: AG-UI
   advertises frontend tools into the same toolset, and a duplicate name is
   a hard error in pydantic-ai.
3. Only on `approved: true` does the agent re-call the backend tool with
   `confirmed=true`; the transition executes through the workflow engine's
   own path, so conditions, actions, and the immutable TransitionLog fire.

The unconfirmed call must not change database state -- that invariant is
tested. Know the boundary: this is a *cooperative* gate (the model follows
the protocol; the server verifies permissions, not approval provenance).
If the gate must be adversarially robust -- e.g. tool results can carry
untrusted text -- upgrade to pydantic-ai's native `requires_approval`
deferred-tool flow, which enforces approval at the protocol level.

---

## Pattern: Frontend Copilot Surface

- `<CopilotKit>` provider joins the existing provider composition in the app
  layout; the sidebar renders only for authenticated users and only when the
  feature flag is on.
- Styling: CopilotKit's CSS is overridden with the template's Tailwind/shadcn
  tokens -- the sidebar looks native, not embedded.
- `useCopilotReadable` exposes page context (e.g. the dashboard's current
  data) so the agent answers about what the user is looking at.
- Generative UI: tool results render as components (a drafted form definition
  renders as a summary card linking to the form builder), via CopilotKit's
  render hooks.
- All user-facing strings go through next-intl like the rest of the app.

---

## Pattern: Testing the Copilot

- **No live LLM calls in tests.** Pydantic AI's `TestModel`/`FunctionModel`
  drive the agent deterministically.
- **Real database, as always.** Tool tests assert against DB state.
- Required cases per permission-gated tool: allowed, denied.
- Required HITL cases: unconfirmed call changes nothing; confirmed call
  executes and writes the audit trail.
- Endpoint: anonymous request rejected before any agent work.
- Frontend: vitest covers the bridge route wiring (cookie forwarding) and
  the approve/deny HITL component in both states.

---

## Configuration

| Variable | Where | Purpose |
|----------|-------|---------|
| `ANTHROPIC_API_KEY` | `backend/config/example.env` | Model provider credential (unset → endpoint returns 503, rest of the app unaffected) |
| `COPILOT_MODEL` | `backend/config/example.env` | Pydantic AI model id; default `anthropic:claude-sonnet-5` |
| `FEATURE_COPILOT` | `config/features.py` | Disable to run as plain django-nextjs; the copilot also requires the forms + workflows features |
| `NEXT_PUBLIC_COPILOT_ENABLED` | `frontend/.env.example` | Frontend flag gating the sidebar |
| `NEXT_PUBLIC_COPILOTKIT_API_KEY` | `frontend/.env.local` | Optional CopilotKit Cloud key for dev extras; never required |

Without an API key, the rest of the template runs unaffected -- the copilot
is additive, feature-flagged, and off the critical path.

---

## What Carries Over

### From django-nextjs

Everything. This template *is* django-nextjs plus `backend/copilot/`, the
frontend copilot module, and their wiring. See the base primer's
[What Carries Over](../django-nextjs/PRIMER.md#what-carries-over).

### From this template to other stacks

The copilot layer is designed to port:

- **fastapi-nextjs:** the Pydantic AI agent, tools pattern, and AG-UI
  endpoint move almost as-is (FastAPI is ASGI-native); the frontend module
  moves unchanged.
- **Any Next.js stack:** the frontend copilot module is backend-agnostic --
  it needs an AG-UI endpoint, nothing Django-specific.

### Needs porting for non-Python backends

The agent itself (AG-UI has first-party support in several ecosystems;
tools must be rewritten against that stack's ORM and permission layer).

---

## Build Order

This stack is **Done**. Phases 0-5 inherited complete from django-nextjs;
the copilot layer was built on top:

- **Phase 6 -- Copilot backend:** `copilot` app, Pydantic AI agent, AG-UI
  endpoint with session-auth gate, engine tools with permission checks,
  HITL transition gating, TestModel-driven tests.
- **Phase 7 -- Copilot frontend:** CopilotKit provider + sidebar, runtime
  bridge route with cookie forwarding, readable context, generative UI,
  HITL approve/deny, i18n, vitest.
