import logging
import time
from collections import defaultdict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.logging import setup_logging  # noqa: F401 — triggers logging config
from backend.routes import chat, documents, health


logger = logging.getLogger(__name__)


# ── Simple in-memory rate limiter ──

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic per-IP rate limiter.
    Limits each IP to `max_requests` within a sliding `window_seconds` window.
    """

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if now - t < self.window_seconds
        ]

        if len(self.requests[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down."
            )

        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response


# ── App ──

app = FastAPI(
    title="Rorak",
    description="rorak.ai v1 - General LLM and Document RAG Assistant",
    version="1.0.0"
)

origins = [
    "https://rorak.tech",
    "https://www.rorak.tech",
    "https://rorak-9axk.web.app",
    "https://rorak-9axk.firebaseapp.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=30,
    window_seconds=60,
)


@app.get("/")
def root():
    return {
        "name": "Rorak",
        "version": "1.0.0",
        "status": "running"
    }


app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(health.router)

logger.info("Rorak API started successfully.")