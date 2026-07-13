.PHONY: lint format test build install clean

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

test-fast:
	uv run pytest -x --no-cov

build:
	uv build

install:
	uv sync

clean:
	rm -rf dist/ .pytest_cache/ .coverage htmlcov/ __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# ----------------------------------------------------------------------------
# Metarepo operations (#24)
# ----------------------------------------------------------------------------
#
# This repo is also the boilerworks METAREPO: every boilerworks-* template repo
# is pinned as a git submodule under templates/. Conventions (internal metarepo pattern):
# - Aggregate targets iterate $(SUBMODULES); single-submodule targets take
#   SUB=<short-name> (the templates/ directory basename).
# - Eight submodules are PRIVATE repos (django-internal, hugo-be, mobile,
#   mobile-e2e, new-cms, site, storybook, typeforms): bootstrap/pin warn and
#   continue when unauthenticated instead of hard-failing.
# - Push order is law: submodules FIRST, then the metarepo, so a pinned SHA
#   never references an unpushed commit.

SUBMODULES := \
	templates/astro-site \
	templates/cherrypy-micro \
	templates/django-htmx \
	templates/django-internal \
	templates/django-micro \
	templates/django-nextjs \
	templates/fastapi-htmx \
	templates/fastapi-micro \
	templates/fastapi-nextjs \
	templates/go-htmx \
	templates/go-micro \
	templates/go-nextjs \
	templates/hono-micro \
	templates/hugo-be \
	templates/laravel-livewire \
	templates/laravel-vue \
	templates/mobile \
	templates/mobile-e2e \
	templates/nestjs-micro \
	templates/nestjs-nextjs \
	templates/new-cms \
	templates/nuxt-full \
	templates/opscode \
	templates/phoenix-liveview \
	templates/rails-hotwire \
	templates/rails-nextjs \
	templates/react-native-expo \
	templates/remix-full \
	templates/rust-micro \
	templates/saleor-nextjs \
	templates/site \
	templates/spring-angular \
	templates/spring-nextjs \
	templates/storybook \
	templates/sveltekit-full \
	templates/typeforms

.PHONY: bootstrap
bootstrap:  ## Init/update each submodule to its pinned SHA (private-repo failures warn, not fail).
	@for sub in $(SUBMODULES); do \
	  git submodule update --init $$sub \
	    || echo "WARN: could not init $$sub (private repo? skipping)"; \
	done
	@echo ""; echo "Workspace ready. Submodules:"; git submodule status | sed 's/^/  /'

.PHONY: pin
pin:  ## Force initialized submodules back to the SHAs the metarepo references.
	@for sub in $(SUBMODULES); do \
	  git submodule update --init $$sub \
	    || echo "WARN: could not pin $$sub (private repo? skipping)"; \
	done

.PHONY: sync
sync:  ## Pull tip of every initialized submodule (--remote --merge); review before re-pinning.
	@for sub in $(SUBMODULES); do \
	  test -e $$sub/.git || continue; \
	  echo "==> sync: $$sub"; \
	  git submodule update --remote --merge $$sub || exit 1; \
	done
	@echo "Review each submodule diff before staging the metarepo update."

.PHONY: all-status
all-status:  ## git status for the metarepo + each initialized submodule.
	@echo "=== metarepo ==="; git status --short
	@for sub in $(SUBMODULES); do \
	  test -e $$sub/.git || continue; \
	  echo "=== $$sub ==="; \
	  ( cd $$sub && git status --short ); \
	done

.PHONY: all-push
all-push:  ## Push each initialized submodule FIRST, then the metarepo (push order is law).
	@for sub in $(SUBMODULES); do \
	  test -e $$sub/.git || continue; \
	  echo "==> pushing $$sub"; \
	  ( cd $$sub && git push ) || exit 1; \
	done
	@echo "==> pushing metarepo"
	git push

.PHONY: all-test
all-test:  ## Aggregate template test run — intentionally a no-op for now (each template's own CI owns its suite).
	@echo "all-test: template suites run in their own CI; nothing aggregated yet."

# Single-submodule git ops: make sub-status SUB=django-nextjs
.PHONY: _require-sub sub-status sub-pull sub-push
_require-sub:
	@test -n "$(SUB)" || (echo "usage: make sub-<status|pull|push> SUB=<short-name>"; exit 2)

sub-status: _require-sub  ## git status for one submodule (SUB=<short-name>).
	git -C templates/$(SUB) status --short

sub-pull: _require-sub  ## Fast-forward one submodule to its remote tip (SUB=<short-name>).
	git -C templates/$(SUB) pull --ff-only

sub-push: _require-sub  ## Push one submodule (SUB=<short-name>).
	git -C templates/$(SUB) push

# ----------------------------------------------------------------------------
# Brain node (#25)
# ----------------------------------------------------------------------------
#
# This repo is also a federated BRAIN NODE: scripts/gen-brain.py compiles the
# structured sources under app/ into app/brain.json (the tracked artifact a
# parent aggregator consumes at the pinned SHA). See bootstrap.md, "The brain".

.PHONY: kg
kg:  ## Regenerate app/knowledge_graph.json from boilerworks/data/templates.yaml.
	uv run python scripts/gen-template-kg.py

.PHONY: brain
brain: kg  ## Compile app/brain.json from the app/ sources (gen-brain.py; deterministic).
	uv run python scripts/gen-brain.py

.PHONY: brain-db
brain-db: brain  ## Seed the derived SQLite query cache app/brain.db (+FTS5; gitignored).
	uv run python scripts/brain-sqlite.py build

.PHONY: check-brain
check-brain:  ## Validate app/brain.json (provenance, integrity, canonical ordering).
	uv run python scripts/check-brain.py

.PHONY: aggregate-brain
aggregate-brain: brain  ## Recompile own brain, then fold submodule sub-brains in (master-brain mode: own ids stay bare; skips templates without app/brain.json).
	uv run python scripts/aggregate-brains.py --include-self $(SUBMODULES)

.PHONY: migrate-brain
migrate-brain:  ## Migrate app/brain.json to the current envelope version. BRAIN forwards a path.
	uv run python scripts/migrate-brain.py $(BRAIN)
