from langchain_community.vectorstores import FAISS

from backend.rag.embeddings import embedding_model
from backend.services.ingestion import ingest_func
from backend.core.config import DOCUMENTS_DIR


vector_store = None


def build_vector_store():
    global vector_store

    files = list(DOCUMENTS_DIR.rglob("*.pdf"))

    documents = []

    for file in files:
        chunks = ingest_func(file)
        documents.extend(chunks)

    if documents:
        vector_store = FAISS.from_documents(
            documents,
            embedding_model
        )
    else:
        vector_store = None

    return vector_store


def add_documents(documents):
    global vector_store

    if not documents:
        return

    if vector_store is None:
        vector_store = FAISS.from_documents(
            documents,
            embedding_model
        )
    else:
        vector_store.add_documents(documents)


build_vector_store()