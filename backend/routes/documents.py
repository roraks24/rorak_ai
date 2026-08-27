import logging
from pathlib import Path
import shutil

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.core.config import DOCUMENTS_DIR
from backend.models.schemas import DocumentUploadResponse
from backend.services.ingestion import ingest_func
from backend.rag.vector_store import add_documents


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse
)
def upload_document(
    file: UploadFile = File(...)
):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file provided"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_filename = Path(file.filename).name
    file_path = DOCUMENTS_DIR / safe_filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer
            )

        chunks = ingest_func(file_path)
        add_documents(chunks)

        logger.info(
            "Uploaded %s: %d chunks created",
            safe_filename, len(chunks)
        )

        return DocumentUploadResponse(
            message="Document uploaded successfully!",
            filename=safe_filename,
            chunks_created=len(chunks)
        )

    except Exception as e:
        logger.exception("Failed to process uploaded file: %s", safe_filename)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )