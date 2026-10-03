.DEFAULT_GOAL := help
.PHONY: help install install-dev migrate run-backend run-frontend test up down clean

PYTHON ?= python
TORCH_CPU_INDEX := --extra-index-url https://download.pytorch.org/whl/cpu

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies (CPU-only PyTorch)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install $(TORCH_CPU_INDEX) -r requirements.txt

install-dev: ## Install runtime + test dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install $(TORCH_CPU_INDEX) -r requirements-dev.txt

migrate: ## Apply database migrations
	alembic upgrade head

run-backend: ## Start the API with auto-reload on :8000
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend: ## Serve the static frontend on :3000
	$(PYTHON) -m http.server 3000 --directory frontend

test: ## Run the test suite
	pytest -q

up: ## Start the full stack with Docker Compose
	docker compose up --build

down: ## Stop the Docker Compose stack
	docker compose down

clean: ## Remove caches and the local vector index
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); shutil.rmtree('documents/.faiss_index', ignore_errors=True)"
