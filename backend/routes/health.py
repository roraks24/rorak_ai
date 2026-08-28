import logging
from fastapi import APIRouter

from backend.models.schemas import HealthResponse, ReadyResponse
from backend.rag import vector_store as vector_store_module
from backend.rag.embeddings import embedding_model
from backend.services.reranker import reranker


logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Health & Readiness"]
)


@router.get("/health/", response_model=HealthResponse)
def health_check():
    """
    Liveness probe: returns immediate 200 OK if service process is alive.
    Does not perform AI inference.
    """
    return HealthResponse(status="healthy")


@router.get("/ready/", response_model=ReadyResponse)
def readiness_check():
    """
    Readiness probe: checks if ML models and vector store are loaded and ready.
    """
    stats = vector_store_module.get_vector_store_stats()
    models_ready = (embedding_model is not None) and (reranker is not None)
    vector_store_ready = stats.get("initialized", False)

    return ReadyResponse(
        status="ready" if models_ready else "initializing",
        models_loaded=models_ready,
        vector_store_initialized=vector_store_ready,
        documents_indexed=stats.get("chunks_indexed", 0),
        details={
            "files_found": stats.get("files_found", 0),
            "file_names": stats.get("file_names", []),
            "init_duration_seconds": round(stats.get("init_duration_seconds", 0.0), 3)
        }
    )