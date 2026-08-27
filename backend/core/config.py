import os
import logging
from pathlib import Path

from dotenv import load_dotenv


# Project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env
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


# Storage
DOCUMENTS_DIR = BASE_DIR / "documents"


# Validation
if not GROQ_API_KEY:
    logging.warning(
        "GROQ_API_KEY is not set. "
        "Set it via environment variable or .env file. "
        "Chat features will not work."
    )
