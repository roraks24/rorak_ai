from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.core.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


def ingest_func(file_path):

    loader = PyPDFLoader(str(file_path))
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = splitter.split_documents(documents)

    return chunks