import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.db.document import Document
from backend.models.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    IngestionJobResponse,
    Pagination,
    RenameDocumentRequest,
)
from backend.services.document_service import DocumentService
from backend.services.exceptions import (
    DocumentNotFound,
    IngestionError,
    ValidationError,
)


logger = logging.getLogger(__name__)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


# ============================================================
# UPLOAD DOCUMENT
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: UUID = Query(
        ...,
        description="Workspace that will own the document",
    ),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload and ingest a document into a workspace.

    Current V2.2 implementation supports PDF documents.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    original_filename = Path(
        file.filename
    ).name

    extension = Path(
        original_filename
    ).suffix.lower()

    if extension != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    service = DocumentService(db)

    temporary_path: Path | None = None

    try:
        # --------------------------------------------------------
        # Save uploaded file to a temporary location.
        # --------------------------------------------------------

        with NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name
            )

            total_size = 0

            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                temporary_file.write(
                    chunk
                )

                total_size += len(
                    chunk
                )

        # --------------------------------------------------------
        # Delegate complete ingestion workflow to the service.
        # --------------------------------------------------------

        document, job, chunk_count = (
            service.ingest_document(
                workspace_id=workspace_id,
                file_path=temporary_path,
                original_filename=original_filename,
                file_size=total_size,
            )
        )

        return DocumentUploadResponse(
            document=_document_response(
                document
            ),
            ingestion_job=IngestionJobResponse.model_validate(
                job
            ),
            chunk_count=chunk_count,
        )

    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    finally:
        # --------------------------------------------------------
        # Remove temporary upload.
        #
        # The permanent artifact was already saved by
        # DocumentService.ingest_document().
        # --------------------------------------------------------

        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except Exception:
                logger.warning(
                    "Failed to remove temporary upload: %s",
                    temporary_path,
                )

        try:
            await file.close()
        except Exception:
            logger.warning(
                "Failed to close uploaded file: %s",
                original_filename,
            )


# ============================================================
# LIST WORKSPACE DOCUMENTS
# ============================================================

@router.get(
    "/",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
)
def get_workspace_documents(
    workspace_id: UUID = Query(
        ...,
        description="Workspace whose documents should be listed",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of documents per page",
    ),
    db: Session = Depends(get_db),
):
    """
    List documents belonging to a workspace.
    """

    service = DocumentService(db)

    try:
        documents, total = (
            service.get_workspace_documents(
                workspace_id=workspace_id,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            (total + page_size - 1)
            // page_size
            if total > 0
            else 0
        )

        return DocumentListResponse(
            documents=[
                _document_response(
                    document
                )
                for document in documents
            ],
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# GET DOCUMENT
# ============================================================

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a single document by ID.
    """

    service = DocumentService(db)

    try:
        document = service.get_document(
            document_id
        )

        return _document_response(
            document
        )

    except DocumentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ============================================================
# RENAME DOCUMENT
# ============================================================

@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def rename_document(
    document_id: UUID,
    request: RenameDocumentRequest,
    db: Session = Depends(get_db),
):
    """
    Rename the user-facing display name of a document.

    This must not:
    - reindex the document
    - change the original filename
    - change the checksum
    - change the storage key
    """

    service = DocumentService(db)

    try:
        document = service.rename_document(
            document_id=document_id,
            display_name=request.display_name,
        )

        return _document_response(
            document
        )

    except DocumentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# DELETE DOCUMENT
# ============================================================

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete one document and all associated resources.
    """

    service = DocumentService(db)

    try:
        service.delete_document(
            document_id
        )

    except DocumentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return None


# ============================================================
# RESPONSE HELPER
# ============================================================

def _document_response(
    document: Document,
) -> DocumentResponse:
    """
    Convert a Document ORM object into the public API schema.

    Internal storage paths, secrets, and internal tracebacks
    are deliberately not exposed.
    """

    return DocumentResponse(
        id=document.id,
        workspace_id=document.workspace_id,
        filename=document.filename,
        original_filename=document.original_filename,
        display_name=document.display_name,
        file_type=document.file_type,
        mime_type=document.mime_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        status=document.status,
        failure_reason=document.failure_reason,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )