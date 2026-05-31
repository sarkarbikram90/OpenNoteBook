# ─────────────────────────────────────────────
# OpenNotebook — Makefile
# ─────────────────────────────────────────────
.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

# ── Development ──────────────────────────────

.PHONY: dev
dev: ## Start all services with hot reload
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop all services
	$(COMPOSE) down

.PHONY: restart
restart: ## Restart all services
	$(COMPOSE) restart

.PHONY: logs
logs: ## Tail logs for all services
	$(COMPOSE) logs -f

# ── Testing ──────────────────────────────────

.PHONY: test
test: ## Run backend + frontend tests
	$(COMPOSE) exec api pytest --cov=app --cov-report=term-missing
	$(COMPOSE) exec frontend npm test -- --run

.PHONY: test-backend
test-backend: ## Run backend tests only
	$(COMPOSE) exec api pytest --cov=app --cov-report=term-missing -v

.PHONY: test-unit
test-unit: ## Run backend unit tests only
	python -m pytest backend/tests/integration/test_rag_pipeline.py -o addopts="" -v

.PHONY: test-integration
test-integration: ## Run backend integration tests only
	python -m pytest backend/tests/integration/test_api_integration.py -o addopts="" -v

.PHONY: test-frontend
test-frontend: ## Run frontend tests only
	cd frontend && npm test

# ── Linting ──────────────────────────────────

.PHONY: lint
lint: ## Run ruff + mypy + eslint
	$(COMPOSE) exec api ruff check app/
	$(COMPOSE) exec api mypy app/
	$(COMPOSE) exec frontend npx eslint src/

.PHONY: lint-fix
lint-fix: ## Auto-fix lint issues
	$(COMPOSE) exec api ruff check --fix app/
	$(COMPOSE) exec frontend npx eslint --fix src/

.PHONY: format
format: ## Format code
	$(COMPOSE) exec api ruff format app/

# ── Database ─────────────────────────────────

.PHONY: db-upgrade
db-upgrade: ## Run pending Alembic migrations
	$(COMPOSE) exec api alembic upgrade head

.PHONY: db-downgrade
db-downgrade: ## Rollback last migration
	$(COMPOSE) exec api alembic downgrade -1

.PHONY: db-revision
db-revision: ## Create a new migration (usage: make db-revision MSG="add users table")
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(MSG)"

# ── Data ─────────────────────────────────────

.PHONY: seed
seed: ## Populate with demo notebook + sources
	$(COMPOSE) exec api python -m app.scripts.seed

# ── Worker ───────────────────────────────────

.PHONY: worker-logs
worker-logs: ## Tail Celery worker output
	$(COMPOSE) logs -f worker

.PHONY: flower
flower: ## Open Celery Flower dashboard
	@echo "Flower dashboard: http://localhost:5555"
	$(COMPOSE) up -d flower

# ── Build & Deploy ───────────────────────────

.PHONY: build
build: ## Build all Docker images
	$(COMPOSE) build

.PHONY: build-prod
build-prod: ## Build production Docker images
	$(COMPOSE_PROD) build

.PHONY: push
push: ## Push images to Artifact Registry
	@echo "Pushing images to registry..."
	docker push $(REGISTRY)/opennotebook-api:$(TAG)
	docker push $(REGISTRY)/opennotebook-worker:$(TAG)
	docker push $(REGISTRY)/opennotebook-frontend:$(TAG)

.PHONY: deploy
deploy: ## Deploy to GKE via Helm
	helm upgrade --install opennotebook ./helm/opennotebook \
		--namespace opennotebook \
		--create-namespace \
		--values ./helm/opennotebook/values.yaml

# ── Cleanup ──────────────────────────────────

.PHONY: clean
clean: ## Stop services and remove volumes
	$(COMPOSE) down -v --remove-orphans

.PHONY: prune
prune: ## Remove all unused Docker resources
	docker system prune -af --volumes

# ── Help ─────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
