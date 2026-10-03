# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    PORT=8000

WORKDIR /app

RUN useradd --create-home --uid 1000 rorak

# CPU-only PyTorch keeps the image size reasonable.
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY backend ./backend

RUN mkdir -p documents "$HF_HOME" && chown -R rorak:rorak /app
USER rorak

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health/' % os.getenv('PORT', '8000'), timeout=4)" || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]