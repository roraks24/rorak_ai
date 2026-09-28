import logging
import threading
import time
from pathlib import Path
import shutil
from typing import Optional, Dict, Any

from langchain_community.vectorstores import FAISS

from backend.rag.embeddings import embedding_model
from backend.core.config import DOCUMENTS_DIR


logger = logging.getLogger(__name__)

vector_store: Optional[FAISS] = None
_lock = threading.Lock()

FAISS_INDEX_DIR = DOCUMENTS_DIR / ".faiss_index"

# Stats tracking for health/readiness
_stats: Dict[str, Any] = {
    "files_found": 0,
    "file_names": [],
    "chunks_indexed": 0,
    "initialized": False,
    "init_duration_seconds": 0.0
}


def get_vector_store_stats() -> Dict[str, Any]:
    """Return runtime vector store metadata."""
    return dict(_stats)


def build_vector_store() -> Optional[FAISS]:
    """
    Build or rebuild the FAISS vector store from PDF files in DOCUMENTS_DIR.
    """
    global vector_store, _stats

    t0 = time.perf_counter()
    logger.info("Initializing vector store from document directory: %s", DOCUMENTS_DIR.resolve())

    if not DOCUMENTS_DIR.exists():
        logger.info(
            "Documents directory does not exist at %s. Starting with empty vector store.",
            DOCUMENTS_DIR.resolve()
        )
        with _lock:
            vector_store = None
            _stats.update({
                "files_found": 0,
                "file_names": [],
                "chunks_indexed": 0,
                "initialized": True,
                "init_duration_seconds": time.perf_counter() - t0
            })
        return vector_store

    pdf_files = list(DOCUMENTS_DIR.rglob("*.pdf"))
    pdf_names = [f.name for f in pdf_files]

    logger.info("Discovered %d PDF file(s) in %s: %s", len(pdf_files), DOCUMENTS_DIR.resolve(), pdf_names)

    if not pdf_files:
        logger.info("No PDF files found in %s. Starting with empty vector store.", DOCUMENTS_DIR.resolve())
        with _lock:
            vector_store = None
            _stats.update({
                "files_found": 0,
                "file_names": [],
                "chunks_indexed": 0,
                "initialized": True,
                "init_duration_seconds": time.perf_counter() - t0
            })
        return vector_store

    from backend.services.ingestion import ingest_func
    documents = []
    for file_path in pdf_files:
        try:
            chunks = ingest_func(file_path)
            documents.extend(chunks)
            logger.info("Ingested %s -> %d chunks created.", file_path.name, len(chunks))
        except Exception:
            logger.exception("Failed to ingest file: %s", file_path)

    with _lock:
        if documents:
            vector_store = FAISS.from_documents(
                documents,
                embedding_model
            )
            _save_index()
            duration = time.perf_counter() - t0
            _stats.update({
                "files_found": len(pdf_files),
                "file_names": pdf_names,
                "chunks_indexed": len(documents),
                "initialized": True,
                "init_duration_seconds": duration
            })
            logger.info(
                "Built vector store with %d chunks from %d files in %.2f seconds.",
                len(documents), len(pdf_files), duration
            )
        else:
            vector_store = None
            _stats.update({
                "files_found": len(pdf_files),
                "file_names": pdf_names,
                "chunks_indexed": 0,
                "initialized": True,
                "init_duration_seconds": time.perf_counter() - t0
            })
            logger.warning("No chunks were successfully extracted from discovered PDF files.")

    return vector_store


def add_documents(documents: list) -> None:
    """
    Add new document chunks to the active FAISS vector store.
    """
    global vector_store, _stats

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
        _stats["chunks_indexed"] = _stats.get("chunks_indexed", 0) + len(documents)

    logger.info("Added %d chunks to vector store (total indexed: %d).", len(documents), _stats["chunks_indexed"])


def clear_vector_store() -> None:
    """
    Clear all indexed document chunks and reset the vector store to empty state.
    Also removes any persisted disk index.
    """
    global vector_store, _stats

    with _lock:
        vector_store = None
        _stats.update({
            "files_found": 0,
            "file_names": [],
            "chunks_indexed": 0,
            "initialized": True,
            "init_duration_seconds": 0.0
        })
        if FAISS_INDEX_DIR.exists():
            try:
                shutil.rmtree(FAISS_INDEX_DIR, ignore_errors=True)
            except Exception:
                logger.warning("Failed to remove FAISS index directory: %s", FAISS_INDEX_DIR)

    logger.info("Vector store has been reset to an empty state.")


def _save_index() -> None:
    """Persist the FAISS index to container disk."""
    if vector_store is None:
        return
    try:
        FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(FAISS_INDEX_DIR))
        logger.info("Persisted FAISS index to %s", FAISS_INDEX_DIR.resolve())
    except Exception:
        logger.exception("Failed to save FAISS index to disk.")


def _load_index() -> bool:
    """Try to load a persisted FAISS index from container disk."""
    global vector_store, _stats
    index_file = FAISS_INDEX_DIR / "index.faiss"
    if index_file.exists():
        t0 = time.perf_counter()
        try:
            vector_store = FAISS.load_local(
                str(FAISS_INDEX_DIR),
                embedding_model,
                allow_dangerous_deserialization=True
            )
            duration = time.perf_counter() - t0
            _stats.update({
                "initialized": True,
                "init_duration_seconds": duration
            })
            logger.info("Loaded persisted FAISS index from disk in %.2f seconds.", duration)
            return True
        except Exception:
            logger.exception("Failed to load persisted FAISS index from disk. Will rebuild from PDFs.")
    return False


# On module load: try persisted index first, else build from PDFs in documents directory
if not _load_index():
    build_vector_store()