.PHONY: help install run-backend run-frontend test lint clean docker-build docker-run

help:
	@echo "Rorak AI — Developer Commands"
	@echo "============================="
	@echo "  make install        Install all backend dependencies"
	@echo "  make run-backend    Start FastAPI backend server with reload"
	@echo "  make run-frontend   Start static frontend server on port 3000"
	@echo "  make test           Run automated pytest test suite"
	@echo "  make docker-build   Build Docker container image"
	@echo "  make docker-run     Run container on port 8080"
	@echo "  make clean          Clean cache directories and temporary files"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

run-backend:
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	cd frontend && python -m http.server 3000

test:
	pytest -v

docker-build:
	docker build -t rorak-ai:latest .

docker-run:
	docker run -p 8080:8080 -e PORT=8080 --env-file .env rorak-ai:latest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf documents/.faiss_index
