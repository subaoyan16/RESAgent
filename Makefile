.PHONY: help install dev dev-backend dev-frontend test test-unit test-integration test-eval
.PHONY: lint format build run clean db-init db-reset chroma-reset setup

.DEFAULT_GOAL := help

help: ## Show all available targets
	@echo "ResAgent Development Makefile"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python and frontend dependencies
	pip install -r requirements.txt
	pip install -e ".[dev]"
	@if [ -f frontend/package.json ]; then \
		cd frontend && npm install; \
	fi

dev: ## Start development environment with Docker Compose
	docker-compose up -d

dev-backend: ## Start backend dev server with hot reload
	uvicorn resagent.app:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests only
	pytest tests/unit -v --cov=resagent --cov-report=term-missing

test-integration: ## Run integration tests only
	pytest tests/integration -v

test-eval: ## Run evaluation benchmarks
	pytest tests/eval -v

lint: ## Run linters (ruff + mypy + frontend)
	ruff check resagent/ tests/
	mypy resagent/ --no-error-summary
	@if [ -f frontend/package.json ]; then \
		cd frontend && npm run lint; \
	fi

format: ## Format code with ruff and prettier
	ruff format resagent/ tests/
	@if [ -f frontend/package.json ]; then \
		cd frontend && npm run format; \
	fi

build: ## Build Docker image
	docker build -t resagent:latest .

run: ## Start production services with Docker Compose
	docker-compose -f docker-compose.prod.yml up -d

clean: ## Remove cache, build artifacts, and temporary files
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf *.egg-info dist build
	rm -rf .nuxt .output frontend/.nuxt frontend/.output
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

db-init: ## Initialize the database schema
	python -m resagent.scripts.db_init

db-reset: ## Reset the database (drop all tables and re-create)
	python -m resagent.scripts.db_reset

chroma-reset: ## Clear Chroma vector store data
	rm -rf data/chroma/*
	touch data/chroma/.gitkeep

setup: install db-init ## Full project setup (install + db-init)
	@echo ""
	@echo "========================================"
	@echo "  ✅ ResAgent ready"
	@echo "========================================"
