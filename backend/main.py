import logging
import time

from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.config import LOG_LEVEL
from backend.core.logging import setup_logging
from backend.routes import (
    auth,
    chat,
    conversations,
    documents,
    health,
    memories,
    users,
    workspaces,
)
from backend.rag import vector_store as vector_store_module


# ============================================================
# LOGGING
# ============================================================

setup_logging(LOG_LEVEL)

logger = logging.getLogger("rorak.main")


# ============================================================
# RATE LIMITING MIDDLEWARE
# ============================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory per-IP sliding window rate limiter
    for basic application protection.
    """

    _instances: list = []

    def __init__(
        self,
        app,
        max_requests: int = 30,
        window_seconds: int = 60,
    ):
        super().__init__(app)

        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self.requests = defaultdict(list)

        RateLimitMiddleware._instances.append(
            self
        )

    @classmethod
    def reset(cls):
        """
        Reset rate limiter state.

        Primarily useful for test isolation.
        """

        for instance in cls._instances:
            instance.requests.clear()

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        client_ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        now = time.time()

        # --------------------------------------------------------
        # Remove timestamps outside the sliding window.
        # --------------------------------------------------------

        self.requests[client_ip] = [
            timestamp
            for timestamp in self.requests[client_ip]
            if now - timestamp < self.window_seconds
        ]

        # --------------------------------------------------------
        # Enforce request limit.
        # --------------------------------------------------------

        if (
            len(self.requests[client_ip])
            >= self.max_requests
        ):
            logger.warning(
                "Rate limit exceeded for IP: %s "
                "(%d requests in %ds)",
                client_ip,
                len(self.requests[client_ip]),
                self.window_seconds,
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": (
                            "Too many requests. "
                            "Please slow down and try again later."
                        ),
                    }
                },
                headers={
                    "Retry-After": str(
                        self.window_seconds
                    )
                },
            )

        self.requests[client_ip].append(
            now
        )

        response = await call_next(
            request
        )

        return response


# ============================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log request execution duration and status codes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        start_time = time.perf_counter()

        response = await call_next(
            request
        )

        duration_ms = (
            time.perf_counter()
            - start_time
        ) * 1000

        # Avoid log clutter for health polling.
        if request.url.path not in (
            "/health",
            "/health/",
        ):
            logger.info(
                "%s %s -> %d (%.2f ms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        return response


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    start_time = time.perf_counter()

    logger.info("=" * 60)
    logger.info(
        "Rorak V2.2 Backend starting up..."
    )
    logger.info("=" * 60)

    # --------------------------------------------------------
    # Vector store runtime status.
    # --------------------------------------------------------

    stats = (
        vector_store_module
        .get_vector_store_stats()
    )

    logger.info(
        "Vector store status: %d PDF file(s) found, "
        "%d chunks indexed.",
        stats.get(
            "files_found",
            0,
        ),
        stats.get(
            "chunks_indexed",
            0,
        ),
    )

    startup_duration = (
        time.perf_counter()
        - start_time
    )

    logger.info(
        "Rorak application ready in %.2f seconds.",
        startup_duration,
    )

    logger.info("=" * 60)

    yield

    logger.info(
        "Rorak Backend shutting down..."
    )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Rorak",
    description=(
        "Rorak AI V2.2 - Document RAG and "
        "Generative AI Assistant"
    ),
    version="2.2.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

origins = [
    "https://rorak.tech",
    "https://www.rorak.tech",
    "http://rorak.tech",
    "http://www.rorak.tech",

    "https://rorak-9axk.web.app",
    "https://rorak-9axk.firebaseapp.com",

    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:5173",
    "http://127.0.0.1:5173",

    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=(
        r"^https?://"
        r"([a-zA-Z0-9-]+\.)?"
        r"rorak\.tech$"
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# APPLICATION MIDDLEWARE
# ============================================================

app.add_middleware(
    RateLimitMiddleware,
    max_requests=30,
    window_seconds=60,
)

app.add_middleware(
    RequestLoggingMiddleware
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "name": "Rorak",
        "version": "2.2.0",
        "status": "running",
    }


# ============================================================
# ROUTES
# ============================================================

app.include_router(
    auth.router
)

app.include_router(
    health.router
)

app.include_router(
    chat.router
)

app.include_router(
    documents.router
)

app.include_router(
    workspaces.router
)

app.include_router(
    conversations.router
)

app.include_router(
    memories.router
)

app.include_router(
    users.router
)