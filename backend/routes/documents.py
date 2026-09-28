import logging
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.core.config import (
    ALLOWED_EXTENSIONS,
    DOCUMENTS_DIR,
    MAX_UPLOAD_SIZE_BYTES,
)
from backend.core.database import get_db
from backend.models.schemas import (
    APIErrorResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    Pagination,
)
from backend.rag.vector_store import add_documents, clear_vector_store
from backend.services.document_service import DocumentService
from backend.services.exceptions import (
    DocumentNotFound,
    ValidationError,
)
from backend.services.ingestion import ingest_func


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Bad Request / Invalid File"},
        413: {"model": APIErrorResponse, "description": "File Too Large"},
        500: {"model": APIErrorResponse, "description": "Processing Failure"},
    },
)
def upload_document(
    file: UploadFile = File(...),
    workspace_id: Optional[UUID] = Query(None, description="Optional workspace ID for V2 persistence"),
    db: Session = Depends(get_db),
):
    """
    Validate, ingest, and index an uploaded PDF document into the vector store.
    Auto-deletes the raw PDF file from disk immediately after processing.
    When workspace_id is provided, also creates durable database records.
    """
    # 1. Filename presence check
    if not file.filename or not file.filename.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "INVALID_FILE",
                    "message": "No file was provided."
                }
            },
        )

    safe_name = Path(file.filename).name.strip()
    file_ext = Path(safe_name).suffix.lower()

    # 2. Extension validation
    if file_ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": f"Unsupported file type '{file_ext}'. Only PDF files are supported."
                }
            },
        )

    # 3. Read and check file size
    try:
        content = file.file.read()
        file_size = len(content)

        if file_size == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "EMPTY_FILE",
                        "message": "The uploaded PDF file is empty (0 bytes)."
                    }
                },
            )

        if file_size > MAX_UPLOAD_SIZE_BYTES:
            max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"File exceeds maximum allowed size of {max_mb:.0f} MB."
                    }
                },
            )

        # 4. Save file temporarily to DOCUMENTS_DIR for parser
        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        file_path = DOCUMENTS_DIR / f"temp_{timestamp}_{safe_name}"

        with open(file_path, "wb") as f_out:
            f_out.write(content)

    except Exception:
        logger.exception("Failed to write uploaded file to disk: %s", safe_name)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "DOCUMENT_PROCESSING_ERROR",
                    "message": "Failed to save uploaded file."
                }
            },
        )

    # 5. Ingestion, Indexing, and Auto-deletion
    try:
        chunks = ingest_func(file_path)

        if not chunks:
            # File may be image-only / scanned or corrupted
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "EMPTY_EXTRACTED_CONTENT",
                        "message": "No readable text content could be extracted from this PDF. "
                                   "Scanned or image-only PDFs are not supported in V1."
                    }
                },
            )

        add_documents(chunks)

        # If workspace_id is provided, persist via DocumentService
        if workspace_id:
            try:
                service = DocumentService(db)
                service.create_document(
                    workspace_id=workspace_id,
                    filename=safe_name,
                    original_filename=file.filename,
                    file_type="pdf",
                    file_size=file_size,
                    page_count=len(chunks),
                )
            except Exception as db_err:
                logger.warning("Could not persist document row to DB: %s", db_err)

        logger.info("Successfully ingested %s: %d chunks added to vector store.", safe_name, len(chunks))

        return DocumentUploadResponse(
            message="Document uploaded and indexed successfully!",
            filename=safe_name,
            chunks_created=len(chunks),
        )

    except Exception:
        logger.exception("Failed to parse and index PDF: %s", safe_name)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "CORRUPTED_PDF",
                    "message": "Failed to process PDF. The file may be corrupt or encrypted."
                }
            },
        )
    finally:
        # Auto-delete the temporary file from disk immediately after processing
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info("Auto-deleted temporary uploaded file: %s", file_path.name)
            except Exception:
                logger.warning("Failed to auto-delete file: %s", file_path)


@router.delete("/clear")
@router.post("/clear")
def clear_all_documents():
    """
    Clear all uploaded document chunks and reset the active vector store to empty state.
    """
    clear_vector_store()
    return {
        "status": "cleared",
        "message": "All documents and vector store indexes have been cleared."
    }


@router.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    return {"database": "connected"}


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    responses={
        404: {"model": APIErrorResponse, "description": "Document Not Found"},
    },
)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    try:
        return service.get_document(document_id)
    except DocumentNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/",
    response_model=DocumentListResponse,
)
def list_documents(
    workspace_id: UUID = Query(..., description="Workspace ID to list documents for"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    try:
        documents, total = service.get_workspace_documents(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return DocumentListResponse(
            documents=documents,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.delete(
    "/{document_id}",
    responses={
        404: {"model": APIErrorResponse, "description": "Document Not Found"},
    },
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    try:
        service.delete_document(document_id)
        return {"status": "deleted", "message": f"Document {document_id} deleted."}
    except DocumentNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )