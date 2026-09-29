import logging
from pathlib import Path
from typing import List

import pypdf
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.core.config import CHUNK_SIZE, CHUNK_OVERLAP


logger = logging.getLogger(__name__)


def _extract_with_pypdf_reader(file_path: Path) -> List[Document]:
    """
    Fallback reader using pypdf.PdfReader with plain and layout extraction modes.
    Extracts text, annotations, and form field streams.
    """
    docs: List[Document] = []
    source_name = Path(file_path).name

    try:
        reader = pypdf.PdfReader(str(file_path))
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            text = ""

            # Strategy A: Standard extraction
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            # Strategy B: Layout mode extraction
            if not text.strip():
                try:
                    text = page.extract_text(extraction_mode="layout") or ""
                except Exception:
                    pass

            # Strategy C: Check annotations / form contents
            if not text.strip():
                try:
                    if "/Annots" in page:
                        annot_texts = []
                        for annot in page["/Annots"]:
                            obj = annot.get_object() if hasattr(annot, "get_object") else annot
                            if isinstance(obj, dict) and "/Contents" in obj:
                                annot_texts.append(str(obj["/Contents"]))
                        if annot_texts:
                            text = " ".join(annot_texts)
                except Exception:
                    pass

            if text and text.strip():
                docs.append(
                    Document(
                        page_content=text.strip(),
                        metadata={"source": source_name, "page": page_num}
                    )
                )
    except Exception as e:
        logger.warning("pypdf direct fallback reader encountered an issue for %s: %s", source_name, e)

    return docs


def ingest_func(file_path) -> List[Document]:
    """
    Load, extract, and split text from a PDF file using robust multi-strategy extraction.
    Returns a list of chunked Document objects.
    """
    path_obj = Path(file_path)
    documents: List[Document] = []

    # 1. Primary extraction via PyPDFLoader
    try:
        loader = PyPDFLoader(str(path_obj))
        loaded_docs = loader.load()
        # Keep documents that have non-empty text content
        documents = [d for d in loaded_docs if d.page_content and d.page_content.strip()]
    except Exception as e:
        logger.warning("PyPDFLoader failed for %s: %s. Trying fallback extraction.", path_obj.name, e)
        documents = []

    # 2. Secondary fallback extraction if PyPDFLoader returned 0 usable text
    if not documents:
        logger.info("Using multi-strategy pypdf fallback extraction for %s.", path_obj.name)
        documents = _extract_with_pypdf_reader(path_obj)

    if not documents:
        logger.warning("No readable text content found in %s across all extraction strategies.", path_obj.name)
        return []

    # 3. Text chunking
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = splitter.split_documents(documents)
    logger.info("Successfully split %s (%d pages) into %d chunks.", path_obj.name, len(documents), len(chunks))

    return chunks
