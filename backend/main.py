import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.logging import setup_logging
from backend.core.config import LOG_LEVEL
from backend.routes import chat, documents, health
from backend.rag import vector_store as vector_store_module


# Initialize structured logging
setup_logging(LOG_LEVEL)
logger = logging.getLogger("rorak.main")


# ── Rate Limiting Middleware ──

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory per-IP sliding window rate limiter for V1 demo protection.
    """

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Exclude basic health checks from strict rate limiting if needed
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean entries outside the current sliding window
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if now - t < self.window_seconds
        ]

        if len(self.requests[client_ip]) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded for IP: %s (%d requests in %ds)",
                client_ip, len(self.requests[client_ip]), self.window_seconds
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please slow down and try again later."
                    }
                },
                headers={"Retry-After": str(self.window_seconds)}
            )

        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response


# ── Request Duration Logging Middleware ──

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log request execution duration and status codes.
    """

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - t0) * 1000

        # Avoid log clutter for continuous health checks in production
        if request.url.path not in ("/health/", "/health"):
            logger.info(
                "%s %s -> %d (%.2f ms)",
                request.method, request.url.path, response.status_code, duration_ms
            )

        return response


# ── Lifespan Handler ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    t_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("Rorak V1 Backend starting up...")
    logger.info("=" * 60)

    # Vector store runtime status
    stats = vector_store_module.get_vector_store_stats()
    logger.info(
        "Vector store status: %d PDF file(s) found, %d chunks indexed.",
        stats.get("files_found", 0), stats.get("chunks_indexed", 0)
    )

    startup_duration = time.perf_counter() - t_start
    logger.info("Rorak application ready in %.2f seconds.", startup_duration)
    logger.info("=" * 60)

    yield

    logger.info("Rorak Backend shutting down...")


# ── FastAPI App Setup ──

app = FastAPI(
    title="Rorak",
    description="Rorak AI V1 - Document RAG and Generative AI Assistant",
    version="1.0.0",
    lifespan=lifespan
)

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
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)?rorak\.tech$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=30,
    window_seconds=60,
)

app.add_middleware(RequestLoggingMiddleware)


# ── Routes ──

@app.get("/")
def root():
    return {
        "name": "Rorak",
        "version": "1.0.0",
        "status": "running"
    }


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(documents.router)