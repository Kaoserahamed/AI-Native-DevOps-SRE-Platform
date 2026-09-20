# Canonical verification entry points. CI runs exactly these targets, and docs/03-local-development.md
# documents the equivalent commands for Windows shells where `make` is unavailable.
SHELL := /bin/sh
UV ?= uv
COV_FAIL_UNDER ?= 90
FAST_MARKERS := not integration and not e2e and not chaos and not slow
PYTEST := $(UV) run pytest --cov-fail-under=$(COV_FAIL_UNDER)

.DEFAULT_GOAL := help

.PHONY: help bootstrap format format-check lint typecheck test test-integration test-agent-eval \
        policy verify frontend frontend-smoke build-images clean

APP_VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo 0.0.0)
VCS_REF ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
IMAGE_TAG ?= $(APP_VERSION)

help: ## Show the available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Install the locked toolchain and the git hooks
	$(UV) sync --frozen --all-extras
	$(UV) run pre-commit install

format: ## Apply formatting to Python sources
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format-check: ## Verify formatting without modifying files
	$(UV) run ruff format --check .

lint: ## Run the linter (ruff)
	$(UV) run ruff check .

typecheck: ## Run strict static type checks (mypy)
	$(UV) run mypy

test: ## Run the fast test tiers (unit + contract)
	$(PYTEST) -m "$(FAST_MARKERS)"

test-integration: ## Run integration tests against ephemeral services
	$(PYTEST) -m "integration"

test-agent-eval: ## Run the agent evaluation and regression suite
	$(PYTEST) -m "agent_eval"

policy: ## Validate repository governance policy
	$(UV) run python scripts/check_repo_policy.py

frontend: ## Lint, format-check, type-check and test the TypeScript workspaces
	npm run --silent verify

frontend-smoke: ## Build the demo frontend and smoke-test the standalone production artifact
	npm run --silent test:frontend:smoke

build-images: ## Build the demo application images (requires Docker; scanning/publishing runs in CI)
	docker build -f services/demo_api/Dockerfile \
		--build-arg APP_VERSION=$(APP_VERSION) --build-arg VCS_REF=$(VCS_REF) \
		-t demo-api:$(IMAGE_TAG) .
	docker build -f apps/demo-app/frontend/Dockerfile \
		--build-arg APP_VERSION=$(APP_VERSION) --build-arg VCS_REF=$(VCS_REF) \
		-t demo-frontend:$(IMAGE_TAG) .

verify: policy format-check lint typecheck test frontend ## Run every fast gate CI enforces on a pull request

clean: ## Remove local caches and build output
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
