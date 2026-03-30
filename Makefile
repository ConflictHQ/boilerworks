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
