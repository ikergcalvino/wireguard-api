.PHONY: help install run install-dev dev lint format test type check clean build up down logs

# Listen address for `make run`; uvicorn reads them from the environment, as in Docker.
UVICORN_HOST ?= 0.0.0.0
UVICORN_PORT ?= 8000
export UVICORN_HOST UVICORN_PORT

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Native / Bare metal
# ---------------------------------------------------------------------------

install: ## Install the application
	pip install .

run: ## Run the API server on UVICORN_HOST:UVICORN_PORT (default 0.0.0.0:8000)
	uvicorn api.main:app

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

install-dev: ## Install with dev dependencies (editable)
	pip install --upgrade "pip>=25.1"
	pip install -e . --group dev

dev: ## Run with hot reload (localhost only)
	uvicorn api.main:app --reload --host 127.0.0.1

lint: ## Run linter and format check
	ruff check .
	ruff format --check .

format: ## Auto-format code
	ruff format .

test: ## Run tests with coverage
	pytest

type: ## Run type checker
	ty check

check: lint type test ## Run all checks (lint + type + test)

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

build: ## Build Docker image
	docker compose build

up: ## Start container (build + detach)
	docker compose up -d --build

down: ## Stop container
	docker compose down

logs: ## Follow container logs
	docker compose logs -f wireguard-api
