# Boilerworks — Open Source Release Checklist

Pre-release checklist for every template. No template ships until every item is checked.

---

## Per-Template Checklist (repeat for each of 27 templates)

### Security

- [ ] `gh api repos/ConflictHQ/boilerworks-{template}/vulnerability-alerts -X PUT` — enable vulnerability alerts
- [ ] Enable Dependabot security updates (`.github/dependabot.yml` in each repo)
- [ ] Run dependency audit (`npm audit`, `pip-audit`, `bundle audit`, `cargo audit`, `composer audit`, `mix deps.audit` — per stack)
- [ ] Fix any critical/high vulnerabilities before release
- [ ] No real secrets in repo (grep for API keys, tokens, passwords that aren't clearly dev defaults)
- [ ] All `.env` files are dev-only with comment headers: `# Development defaults. Never use in production.`
- [ ] `.env` is in `.gitignore`

### Branding (human spot-check)

- [ ] Boilerworks logo present or referenced in README
- [ ] Color scheme matches Boilerworks dark theme
- [ ] No "Conflict" branding visible to users (internal org name, not product name)
- [ ] README header is clean and professional

### LICENSE

- [ ] MIT License present
- [ ] Copyright holder is correct (decide: "Boilerworks Contributors" or "Conflict LLC")
- [ ] Consistent across all templates

### Documentation

- [ ] README.md — stack, getting started, endpoints, commands. First impression is clear.
- [ ] CLAUDE.md — real stack info, not placeholder
- [ ] AGENTS.md — points to bootstrap.md
- [ ] bootstrap.md — real conventions (50+ lines)
- [ ] CONTRIBUTING.md — PR process, code style, tests
- [ ] CODE_OF_CONDUCT.md — Contributor Covenant
- [ ] SECURITY.md — vulnerability reporting process

### Code Quality

- [ ] Lint passes (stack-appropriate: Ruff, ESLint, RuboCop, golangci-lint, clippy, Pint, Credo, etc.)
- [ ] Tests pass
- [ ] No TODOs, FIXMEs, stubs, or placeholder code
- [ ] No `.build-complete` markers (internal only)
- [ ] No internal build docs (BUILD_SPEC.md, etc.)

### CI/CD

- [ ] `.github/workflows/ci.yml` present and working
- [ ] Lint job
- [ ] Test job (with real database service)
- [ ] Build job
- [ ] Audit job (dependency vulnerabilities)

### Dependabot

Each template repo gets `.github/dependabot.yml`:

```yaml
version: 2
updates:
  # For npm/yarn/pnpm
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10

  # For pip/uv (Python)
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10

  # For GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
```

Adapt `package-ecosystem` per stack:
- Python: `pip`
- Node/TypeScript: `npm`
- Ruby: `bundler`
- PHP: `composer`
- Go: `gomod`
- Rust: `cargo`
- Elixir: `mix`
- Java: `gradle` or `maven`

---

## Root Boilerworks Repo Checklist

### Files to Remove Before Public Release

- [x] `META_BUILD.md` — deleted
- [x] `WAVE5_FIXES.md` — deleted
- [x] `FINAL_FIXES.md` — deleted
- [x] `LAST_THREE_FIXES.md` — deleted
- [x] `BUILD_SPEC.md` (in fastapi-micro) — deleted
- [x] All `.build-complete` markers — deleted
- [ ] `BOILERWORKS-CONTEXT.md` — contains internal strategy notes. Either delete or create a public-safe version with only Boilerworks-scoped content.

### Files to Keep

- `primers/CATALOGUE.md` — public-facing, no internal references
- `primers/PROCESS.md` — development philosophy and standards
- `primers/PRIMER_TEMPLATE.md` — template structure
- `primers/NEXTJS_FRONTEND.md` — shared frontend reference
- `primers/*/PRIMER.md` — all per-stack primers
- Logo files in `logos/`

### boilerworks-django-internal

- [ ] Decide: rename to public-friendly name, or exclude from public release
- [ ] If keeping: scrub any Conflict-specific code or references

### Git Remotes

- [ ] Decide public GitHub org name (ConflictHQ? BoilerworksHQ? boilerworks-templates?)
- [ ] Transfer or fork all 27 repos to public org
- [ ] Update all remote URLs

---

## Human Review Pass (before flipping repos to public)

For each template, the human does a live check:

- [ ] `docker compose up -d` (or `wrangler dev` for edge) — does it boot?
- [ ] Hit the health endpoint — does it respond?
- [ ] Log in with seed credentials — does auth work?
- [ ] Create/edit/delete a record — does CRUD work?
- [ ] Check the admin panel (if applicable) — does it load?
- [ ] Visual spot-check: Boilerworks theme/colors/logo correct?
- [ ] Read the README as a stranger — would you know what to do?

---

## Release Sequence

1. Clean up root repo (remove internal docs, handle CONTEXT.md)
2. Add Dependabot config to all 27 template repos
3. Run security audit on all templates, fix critical/high findings
4. Update LICENSE copyright holder across all templates
5. Human live-check each template (boot, auth, CRUD, branding)
6. Build the CLI (`boilerworks init`)
7. Flip repos from private to public
8. Ship announcement
