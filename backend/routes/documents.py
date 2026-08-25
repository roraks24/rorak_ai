from pathlib import Path
import shutil

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.core.config import DOCUMENTS_DIR
from backend.models.schemas import DocumentUploadResponse
from backend.services.ingestion import ingest_func
from backend.rag.vector_store import add_documents


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse
)
async def upload_document(
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

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
        )

    chunks = ingest_func(file_path)

    add_documents(chunks)

    return {
        "message": "Document uploaded successfully!",
        "filename": safe_filename,
        "Chunks Created": len(chunks)
    }