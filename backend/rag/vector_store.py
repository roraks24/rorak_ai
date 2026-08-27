import logging
import threading
from pathlib import Path

from langchain_community.vectorstores import FAISS

from backend.rag.embeddings import embedding_model
from backend.services.ingestion import ingest_func
from backend.core.config import DOCUMENTS_DIR


logger = logging.getLogger(__name__)

vector_store = None
_lock = threading.Lock()

FAISS_INDEX_DIR = DOCUMENTS_DIR / ".faiss_index"


def build_vector_store():
    global vector_store

    if not DOCUMENTS_DIR.exists():
        logger.info(
            "Documents directory does not exist: %s. "
            "Starting with empty vector store.",
            DOCUMENTS_DIR
        )
        vector_store = None
        return vector_store

    files = list(DOCUMENTS_DIR.rglob("*.pdf"))

    if not files:
        logger.info("No PDF files found. Starting with empty vector store.")
        vector_store = None
        return vector_store

    documents = []

    for file in files:
        try:
            chunks = ingest_func(file)
            documents.extend(chunks)
        except Exception:
            logger.exception("Failed to ingest file: %s", file)

    with _lock:
        if documents:
            vector_store = FAISS.from_documents(
                documents,
                embedding_model
            )
            _save_index()
            logger.info(
                "Built vector store with %d chunks from %d files.",
                len(documents), len(files)
            )
        else:
            vector_store = None

    return vector_store


def add_documents(documents):
    global vector_store

    if not documents:
        return

    with _lock:
        if vector_store is None:
            vector_store = FAISS.from_documents(
                documents,
                embedding_model
            )
        else:
            vector_store.add_documents(documents)
        _save_index()

    logger.info("Added %d chunks to vector store.", len(documents))


def _save_index():
    """Persist the FAISS index to disk."""
    try:
        FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(FAISS_INDEX_DIR))
    except Exception:
        logger.exception("Failed to save FAISS index to disk.")


def _load_index():
    """Try to load a persisted FAISS index from disk."""
    global vector_store
    index_file = FAISS_INDEX_DIR / "index.faiss"
    if index_file.exists():
        try:
            vector_store = FAISS.load_local(
                str(FAISS_INDEX_DIR),
                embedding_model,
                allow_dangerous_deserialization=True
            )
            logger.info("Loaded persisted FAISS index from disk.")
            return True
        except Exception:
            logger.exception("Failed to load persisted FAISS index.")
    return False


# On module load: try persisted index first, else build from PDFs
if not _load_index():
    build_vector_store()