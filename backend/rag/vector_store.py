from langchain_community.vectorstores import FAISS
from backend.rag.embeddings import embedding_model 
from backend.services.ingestion import ingest_func

documents = ingest_func()

vector_store = FAISS.from_documents(
    documents,
    embedding_model
)