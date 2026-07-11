# Boilerworks — Development Process Mandate

This document is non-negotiable. Every Boilerworks template, every agent, every contributor follows this process. No exceptions. No shortcuts. We are in the business of building software the right way — tedious and meticulous.

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [Planning](#planning)
3. [Issue Management](#issue-management)
4. [The Build Cycle](#the-build-cycle)
5. [Agent Workflow](#agent-workflow)
6. [Pull Requests & Code Review](#pull-requests--code-review)
7. [Quality Gates](#quality-gates)
8. [Coding Standards](#coding-standards)
9. [Testing Standards](#testing-standards)
10. [Non-Negotiable Rules](#non-negotiable-rules)

---

## Philosophy

### Core Tenets

> *With thanks to Debian and Python for inspiration.*

- We will do whatever is necessary to ensure all services remain functioning in a secure and effective fashion.
- Do not, by any wilful or deliberate act, interfere with the work of another developer or jeopardize the integrity of systems or data.
- This is not your personal playground. Many things that are fine to do in your personal lab are not OK in a production environment.
- When in doubt, ask questions first, act second. Forgiveness is usually much harder to secure than permission.
- Explicit is better than implicit. Simple is better than complex. Complex is better than complicated.
- Readability counts — in code, comments, charts, and documentation.
- Special cases aren't special enough to break the rules. Although practicality beats purity.
- Errors should never pass silently. Unless explicitly silenced.
- In the face of ambiguity, refuse the temptation to guess.
- There should be one — and preferably only one — obvious way to do it. Although that way may not be obvious at first unless you're the one who defined it.
- Now is better than never. Although never is often better than right now.
- If the implementation is hard to explain, it's a bad idea.
- If the implementation is easy to explain, it may be a good idea.
- If it's worth doing, it's worth doing right.
- Namespaces are one honking great idea — let's do more of those!
- All alerts must require some form of human interaction, otherwise it's just signal noise.
- Anything important enough to page must require a human's immediate attention.

---

### Plan Top-Down, Build Bottom-Up

Every piece of work starts with the big picture and narrows to implementation:

1. **Architecture first.** Understand the system, the constraints, the dependencies. Know what you're building before you touch code.
2. **Reductive planning.** Start with the whole problem, then decompose. Break it into layers, break layers into modules, break modules into tasks. Each task should be the smallest meaningful unit of work.
3. **Build from the foundation.** Once planned, build bottom-up. Data models before API. API before frontend. Infrastructure before features. Each layer is solid before the next one starts.

### No Stubs, No Placeholders, No "We'll Fix It Later"

Every piece of code that gets merged is complete, tested, and reviewed. A half-built feature is worse than no feature — it's technical debt from day one. If a feature can't be completed in a single PR, break it into smaller features that CAN be completed.

### Break Problems Into Minimal Pieces

Large tasks fail. Small tasks succeed. The discipline is in the decomposition:

- A task should take hours, not days
- A task should touch one concern, not three
- A task should be reviewable in a single sitting
- If a task feels big, it's not broken down enough

---

## Planning

### Before Any Code Is Written

1. **Understand the requirement.** Read the issue. Read it again. If it's unclear, ask. Don't assume.
2. **Research.** Read the existing code. Understand the patterns. Know what's already built. Find what can be reused.
3. **Architect.** Design the solution at a high level. Identify the data model changes, API changes, frontend changes, and infrastructure changes.
4. **Decompose.** Break the solution into ordered tasks. Each task has a clear input, a clear output, and a clear way to verify it works.
5. **Document the plan.** Comment the plan on the issue BEFORE starting work. This is a checkpoint — it forces clear thinking and allows others (human or agent) to catch problems early.

### Reductive Planning in Practice

```
Goal: Add invoice management to the platform

Level 1 — Architecture:
  "Invoices need: data model, permissions, CRUD API, list/detail pages, PDF export"

Level 2 — Modules:
  "Data model: Invoice, InvoiceLineItem, InvoiceStatus"
  "API: queries (list, detail), mutations (create, update, send, void)"
  "Frontend: list page, detail page, create form, PDF download"
  "Jobs: PDF generation, email delivery"

Level 3 — Tasks (each is one PR):
  1. Invoice + InvoiceLineItem models, migration, admin
  2. Invoice permissions (view, create, edit, send, void)
  3. Invoice GraphQL types + list/detail queries
  4. Invoice create/update mutations
  5. Invoice send/void mutations + status transitions
  6. Invoice list page + data table
  7. Invoice detail page
  8. Invoice create form
  9. PDF generation job + download endpoint
  10. Email delivery on send

Each task is ordered. Each depends on the one before it.
Each is a single, reviewable PR.
```

---

## Issue Management

### Where Issues Live

- Every template repo has its own GitHub Project board
- Issues are filed in the repo they belong to
- Cross-repo work gets a tracking issue in the parent boilerworks repo

### Issue Structure

Every issue has:

- **Title:** Clear, imperative. "Add invoice data model" not "invoices"
- **Description:** What needs to be done, why, and acceptance criteria
- **Labels:** priority (P0/P1/P2/P3), type (feature/bug/chore/docs), size (S/M/L)
- **Project:** Assigned to the repo's project board
- **Sub-issues:** Large issues are broken into sub-issues, each linked and ordered
- **Blocking/blocked-by:** Dependencies between issues are explicit

### Issue Lifecycle

```
Backlog → Groomed → In Progress → In Review → Done
```

1. **Backlog:** Filed but not yet refined. May be vague.
2. **Groomed:** Requirements are clear, acceptance criteria defined, sub-issues created, priority set, dependencies mapped.
3. **In Progress:** Someone (human or agent) is actively working on it. The issue has a branch and a plan comment.
4. **In Review:** PR is open and under review.
5. **Done:** PR merged, CI passes, issue closed with summary comment.

### Priority Levels

| Priority | Meaning | SLA |
|----------|---------|-----|
| **P0** | Blocking other work. Critical bug. Security issue. | Now |
| **P1** | High value. On the current sprint/milestone. | This cycle |
| **P2** | Important but not urgent. Queued. | Next cycle |
| **P3** | Nice to have. Do when capacity allows. | Someday |

---

## The Build Cycle

Every piece of work follows this cycle. No exceptions.

```
1. Pick issue from backlog (highest priority, unblocked)
2. Read the issue thoroughly
3. Research: read relevant code, understand patterns, find reusable pieces
4. Groom: update issue with findings, clarify requirements, create sub-issues if needed
5. Comment plan on issue BEFORE starting code
6. Create branch from main
7. Implement (bottom-up, following existing patterns)
8. Write tests (both happy path and permission/error cases)
9. Run lint + tests locally, fix all issues
10. Comment learnings on issue DURING work (what you discovered, decisions made)
11. Open PR with clear description
12. Code review (another agent or human reviews)
13. Address review feedback (new commits, not amends)
14. Merge when approved + CI green
15. Comment summary on issue AFTER completion
16. Close issue
17. Pick next issue
```

### What "Done" Means

A task is done when ALL of these are true:

- [ ] Code is merged to main
- [ ] All tests pass (including new tests for the new code)
- [ ] Lint passes with zero warnings
- [ ] CI pipeline is green
- [ ] Issue has a plan comment, learnings comment, and summary comment
- [ ] PR description clearly explains what changed and why
- [ ] No TODOs, no stubs, no "fix later" comments in the merged code

---

## Agent Workflow

AI agents working on Boilerworks templates follow the same process as humans. No shortcuts because "it's an agent."

### Agent Picks Up an Issue

1. **Read the issue.** All of it. Comments, linked issues, acceptance criteria.
2. **Read the codebase.** Bootstrap.md, relevant modules, existing patterns. Don't guess — look.
3. **Update the issue** with a comment: "Picking this up. Here's my plan: ..."
4. **Groom if needed.** If the issue is unclear, ask for clarification in a comment. If it needs sub-issues, create them.

### Agent Works on the Issue

5. **Create a branch.** Named: `feature/issue-number-short-description` or `fix/issue-number-short-description`
6. **Implement following existing patterns.** Don't invent new patterns. Read bootstrap.md. Match what's already there.
7. **Write tests.** Every new feature gets tests. Every bug fix gets a regression test. Both allowed and denied permission cases.
8. **Run lint + tests.** Fix everything before opening a PR. Don't push broken code.
9. **Comment on the issue** with learnings, decisions, anything non-obvious discovered during implementation.

### Agent Opens a PR

10. **PR title:** Short, imperative. Under 70 characters.
11. **PR body:** Summary of changes, test plan, link to issue.
12. **Request review.** Another agent or human reviews the PR.

### Agent Reviews a PR (as reviewer)

13. **Read the diff.** All of it.
14. **Check against bootstrap.md conventions.** Does the code follow the patterns?
15. **Check tests.** Are they meaningful? Do they test the right things? Both happy path and error cases?
16. **Check for anti-patterns.** Exposed integer PKs, missing auth checks, hardcoded config, mocked database, missing soft deletes.
17. **Approve or request changes.** Be specific. "This mutation is missing an auth check at line 47" not "needs work."

### Agent Merges

18. **Only merge when:** CI is green AND review is approved AND no unresolved comments.
19. **Comment on the issue** with a summary of what was done.
20. **Close the issue.**
21. **Pick the next issue.**

---

## Pull Requests & Code Review

### PR Requirements

Every PR must have:

- Link to the issue it addresses
- Clear description of WHAT changed and WHY
- Test plan (how to verify the changes work)
- All CI checks passing
- At least one approving review

### Code Review Checklist

Reviewers check for:

- [ ] **Correctness:** Does it do what the issue asks?
- [ ] **Patterns:** Does it follow bootstrap.md conventions?
- [ ] **Auth:** Is there an auth check at the top of every new resolver/endpoint/action?
- [ ] **Permissions:** Are permission checks in place? Both server and client?
- [ ] **Soft deletes:** No hard deletes on business objects?
- [ ] **External IDs:** No integer PKs exposed in API responses?
- [ ] **Tests:** Are there tests? Do they assert against database state? Both allowed and denied cases?
- [ ] **Security:** No SSRF vectors, no plaintext secrets, no raw error details exposed?
- [ ] **Code style:** Lint passes? Formatting correct?
- [ ] **No extras:** No unrelated changes, no "while I'm here" refactors, no added docs/comments for unchanged code?

### Review Feedback Rules

- Be specific. Reference file and line number.
- Explain why, not just what. "Missing auth check" is better than "wrong." "Missing auth check — any unauthenticated request can access this data" is best.
- Blocking issues must be fixed before merge. Non-blocking suggestions are labeled as such.
- New commits to address feedback, never amend. The review trail matters.

---

## Quality Gates

### Before Merge

| Gate | What | Enforcement |
|------|------|-------------|
| **Lint** | Code style, formatting, import order | CI job, blocks merge |
| **Tests** | Full test suite against real database | CI job, blocks merge |
| **Build** | Application compiles/builds successfully | CI job, blocks merge |
| **Audit** | Dependency vulnerability scan | CI job, blocks on critical |
| **Review** | At least one approving review | Branch protection rule |

### Ongoing

| Gate | What | Frequency |
|------|------|-----------|
| **Dependency updates** | Keep dependencies current, no known vulnerabilities | Weekly |
| **Coverage** | Test coverage does not decrease | Per PR |
| **Performance** | No regressions in response times | Per release |
| **Security** | No new OWASP top 10 vulnerabilities introduced | Per PR |

---

## Coding Standards

### Per-Language Standards

Every language has a canonical style guide and toolchain. No debates, no custom configs — use the community standard.

| Language | Style Guide | Formatter | Linter | Package Manager | Env Isolation |
|----------|------------|-----------|--------|----------------|---------------|
| Python | PEP 8 | Ruff (format) | Ruff (check) | uv (preferred), pip as fallback | venv / virtualenv (mandatory) |
| TypeScript | Prettier + ESLint | Prettier | ESLint + @typescript-eslint | npm | node_modules (managed by npm) |
| Ruby | Ruby Style Guide | RuboCop (auto-correct) | RuboCop | Bundler | rbenv / asdf |
| PHP | PSR-12 | Laravel Pint | PHPStan / Larastan | Composer | N/A (managed by Composer) |
| Java | Google Java Style | google-java-format | Checkstyle + SpotBugs | Gradle or Maven | JDK managed by SDKMAN/asdf |
| Go | Effective Go | gofmt | golangci-lint | go modules | Built-in (GOPATH/modules) |
| Elixir | Elixir Style Guide | mix format | Credo + Dialyxir | Mix | Built-in (Mix) |
| Rust | Rust Style Guide | rustfmt | Clippy | Cargo | Built-in (Cargo) |
| Svelte | Prettier + svelte-check | Prettier | ESLint + svelte plugin | npm | node_modules |

### Python Specifics

- **Ruff replaces flake8, isort, and black.** One tool, faster, better. All Python templates use Ruff.
- **uv replaces pip.** Faster dependency resolution, better lockfiles, compatible with pip. Use `uv pip install`, `uv venv`, `uv sync`.
- **venv / virtualenv is mandatory.** Never install into system Python. Agents must create and activate a virtual environment before installing anything. Docker containers get their own env by default, but local development must use venv.
- **PEP 8 is the style.** No exceptions. Ruff enforces it. Max line length is configured per project (typically 140 for Django, 100 for FastAPI).

### Environment Rules

- **Docker / containers are non-negotiable.** Every template ships with Docker Compose. Every service runs in a container. Local development uses containers. CI uses containers. No "works on my machine."
- **Virtual environments are mandatory for local Python work.** Even inside Docker, Python deps go in a venv, not system-wide.
- **Node version management.** Use `.nvmrc` or `.node-version` to pin Node.js version. Agents respect this.
- **Lockfiles are committed.** `uv.lock`, `package-lock.json`, `Gemfile.lock`, `composer.lock` — always committed, always respected. No `--no-lock` shortcuts.

---

## Testing Standards

### Tests Must Be Meaningful

Tests exist to catch bugs and prevent regressions. They are not a checkbox exercise.

**What "meaningful" means:**
- Tests exercise real behavior through the API/endpoint layer, not isolated internals
- Tests assert against database state and response content, not hardcoded strings
- Tests cover the happy path AND the error/permission-denied path
- Tests for new features prove the feature works end-to-end
- Tests for bug fixes prove the bug is fixed and won't recur

**What is NOT meaningful:**
- Tests that always pass (hardcoded assertions, `assert True`)
- Tests with no assertions (empty test bodies)
- Tests that mock the database (hides real bugs)
- Tests that only check response status codes without verifying data
- Tests written purely to hit a coverage number without testing real behavior

### Coverage Targets

| Level | Target | Meaning |
|-------|--------|---------|
| **Acceptable** | 80%+ | Minimum bar. Core paths covered. |
| **Goal** | 90%+ | Solid coverage. Most edge cases covered. |
| **Ideal** | 95%+ | Comprehensive. Only trivial/unreachable code uncovered. |

**Exercise judgment.** 95% coverage with meaningful tests is better than 100% coverage with garbage tests. Don't write tests for the sake of numbers — write tests that would catch the bugs you'd actually ship.

Coverage does not decrease on any PR. If you add code, you add tests.

---

## Non-Negotiable Rules

These rules apply to every template, every agent, every contributor. They are not suggestions.

### Process

1. **Plan before you code.** Comment your plan on the issue before writing a single line.
2. **One PR per issue.** Don't batch unrelated changes.
3. **No merging without review.** Every PR gets reviewed. Period.
4. **No merging with failing CI.** Green pipeline or it doesn't merge.
5. **No stubs, no TODOs, no placeholders.** Every merged PR is complete.
6. **Comment on issues.** Plan before, learnings during, summary after.
7. **Close the loop.** Every issue gets closed with a summary when done.

### Code

8. **Follow bootstrap.md.** The conventions document is the law. Don't invent new patterns.
9. **Auth check on every endpoint.** First line of every resolver, controller action, or view handler.
10. **Group-based permissions only.** Never assign permissions to users directly.
11. **Soft deletes only.** Never hard-delete business objects.
12. **No integer PKs in APIs.** UUID, cuid, or equivalent.
13. **Test both allowed and denied.** Every permission-gated operation gets both tests.
14. **Real database in tests.** Never mock the database.
15. **Validate at boundaries.** All input validated at API entry points.

### Git

16. **No rebases.** New commits only.
17. **No co-authorship messages.** No AI attribution in commits, ever.
18. **No force pushes to main.** Branch protection enforced.
19. **Meaningful commit messages.** Explain why, not what.
20. **Branch naming:** `feature/`, `fix/`, `chore/` prefixes with issue number.
21. **Repos are always private.** Agents create private repos. Open-sourcing is a human decision, never an agent's.

### Documentation

22. **No local planning docs.** Plans go on GitHub issues, not in markdown files in the repo.
23. **bootstrap.md is the source of truth.** Keep it updated as the template evolves.
24. **Agent shims point to bootstrap.md.** Always.

---

## Summary

The process is simple:

**Plan meticulously. Build carefully. Review thoroughly. Ship confidently.**

Every shortcut creates debt. Every skipped test hides a bug. Every unreviewed PR introduces risk. The discipline is the product.
