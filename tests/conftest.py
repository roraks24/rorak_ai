import pytest
from backend.main import RateLimitMiddleware


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Ensure in-memory rate limiter is reset for clean test isolation."""
    RateLimitMiddleware.reset()
    yield
    RateLimitMiddleware.reset()
