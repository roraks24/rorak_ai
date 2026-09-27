import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# Project root (directory containing backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")


# API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()


# Model configuration
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


# RAG configuration
CHUNK_SIZE = int(
    os.getenv("CHUNK_SIZE", "500")
)

CHUNK_OVERLAP = int(
    os.getenv("CHUNK_OVERLAP", "50")
)

RETRIEVAL_K = int(
    os.getenv("RETRIEVAL_K", "10")
)

RERANK_TOP_K = int(
    os.getenv("RERANK_TOP_K", "3")
)


# Storage & upload limits
DOCUMENTS_DIR = BASE_DIR / "documents"
MAX_UPLOAD_SIZE_BYTES = int(
    os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024))  # 10 MB default
)
ALLOWED_EXTENSIONS = {".pdf"}


# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# Validation
if not GROQ_API_KEY:
    logging.warning(
        "GROQ_API_KEY is not configured in environment or .env. "
        "Generation features will be unavailable."
    )

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    logger.warning("DATABASE_URL is not configured")