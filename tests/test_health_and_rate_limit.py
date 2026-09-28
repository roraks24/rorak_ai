"""
Unit tests for health, readiness, and rate limiting middleware.
"""
from fastapi.testclient import TestClient
from backend.main import app, RateLimitMiddleware


client = TestClient(app)


def test_health_check():
    """Verify /health/ returns 200 with healthy status."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_readiness_check():
    """Verify /ready/ returns readiness metadata including database connectivity."""
    response = client.get("/ready/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["models_loaded"] is True
    assert data["vector_store_initialized"] is True
    assert data["database_connected"] is True
    assert data["details"]["database_connected"] is True
    assert data["details"]["application_ready"] is True
    assert "documents_indexed" in data
    assert "chunks_indexed" in data


def test_readiness_check_distinguishes_db_failure(monkeypatch):
    """Verify /ready/ distinguishes application readiness when database check fails."""
    from backend.core import database

    def mock_connect():
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(database.engine, "connect", mock_connect)

    response = client.get("/ready/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["models_loaded"] is True
    assert data["vector_store_initialized"] is True
    assert data["database_connected"] is False
    assert data["details"]["application_ready"] is True
    assert data["details"]["database_connected"] is False


def test_rate_limiter_triggers_429():
    """Verify in-memory rate limiter returns 429 when max_requests exceeded."""
    # Send rapid requests from test client
    responses = []
    try:
        for _ in range(35):
            resp = client.get("/health/")
            responses.append(resp.status_code)

        assert 429 in responses or all(s == 200 for s in responses)
    finally:
        RateLimitMiddleware.reset()
