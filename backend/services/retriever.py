import logging
from typing import List
from langchain_core.documents import Document

from backend.rag import vector_store as vector_store_module
from backend.core.config import RETRIEVAL_K


logger = logging.getLogger(__name__)


def retriev_func(query: str) -> List[Document]:
    """
    Retrieve candidate chunks from the vector store based on query similarity.
    """
    if vector_store_module.vector_store is None:
        logger.info("Vector store is empty. No documents available for retrieval.")
        return []

    try:
        retriever = vector_store_module.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": RETRIEVAL_K
            }
        )
        results = retriever.invoke(query)
        logger.info("Retrieved %d candidate chunks for query: %.60s", len(results), query)
        return results
    except Exception:
        logger.exception("Error during vector retrieval for query.")
        return []


def context_func(results: List[Document]) -> str:
    """
    Format retrieved documents into structured context blocks.
    """
    if not results:
        return ""

    context_chunks = []
    for i, document in enumerate(results, start=1):
        source = document.metadata.get("source", "Unknown")
        page = document.metadata.get("page", "N/A")
        content = document.page_content.strip()

        context_chunks.append(
            f"--- Document Chunk {i} (Source: {source}, Page: {page}) ---\n{content}"
        )

    return "\n\n".join(context_chunks)