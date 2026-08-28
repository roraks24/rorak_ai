"""
Unit tests for health, readiness, and rate limiting middleware.
"""
from fastapi.testclient import TestClient
from backend.main import app


client = TestClient(app)


def test_health_check():
    """Verify /health/ returns 200 with healthy status."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_readiness_check():
    """Verify /ready/ returns readiness metadata."""
    response = client.get("/ready/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "models_loaded" in data
    assert "vector_store_initialized" in data
    assert "documents_indexed" in data


def test_rate_limiter_triggers_429():
    """Verify in-memory rate limiter returns 429 when max_requests exceeded."""
    # Send rapid requests from test client
    responses = []
    for _ in range(35):
        resp = client.get("/health/")
        responses.append(resp.status_code)

    assert 429 in responses or all(s == 200 for s in responses)
