from langchain_community.vectorstores import FAISS

from backend.rag.embeddings import embedding_model
from backend.services.ingestion import ingest_func
from backend.core.config import DOCUMENTS_DIR


def build_vector_store():

    files = list(DOCUMENTS_DIR.rglob("*.pdf"))

    documents = []

    for file in files:
        chunks = ingest_func(file)
        documents.extend(chunks)

    if not documents:
        raise ValueError(
            "No PDF documents found to build the vector store."
        )

    return FAISS.from_documents(
        documents,
        embedding_model
    )


vector_store = build_vector_store()


def add_documents(documents):

    vector_store.add_documents(documents)