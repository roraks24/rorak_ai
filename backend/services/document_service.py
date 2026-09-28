import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.models.db.document import Document
from backend.models.db.document_chunk import DocumentChunk
from backend.models.db.ingestion_job import IngestionJob
from backend.models.schemas import DocumentStatus, IngestionStatus
from backend.rag.vector_store import add_documents
from backend.repositories.document_chunk_repository import DocumentChunkRepository
from backend.repositories.document_repository import DocumentRepository
from backend.repositories.ingestion_job_repository import IngestionJobRepository
from backend.services.exceptions import (
    DocumentNotFound,
    IngestionError,
    ValidationError,
)
from backend.services.ingestion import ingest_func


logger = logging.getLogger(__name__)


class DocumentService:
    """
    Coordinates document persistence, retrieval, workspace isolation,
    and ingestion into the vector store.
    """

    def __init__(
        self,
        db: Session,
        repository: DocumentRepository | None = None,
        chunk_repository: DocumentChunkRepository | None = None,
        job_repository: IngestionJobRepository | None = None,
    ):
        self.db = db
        self.repository = repository or DocumentRepository(db)
        self.chunk_repository = chunk_repository or DocumentChunkRepository(db)
        self.job_repository = job_repository or IngestionJobRepository(db)

    def get_document(self, document_id: UUID) -> Document:
        """Retrieve a document by ID or raise DocumentNotFound."""
        doc = self.repository.get_by_id(document_id)
        if not doc:
            raise DocumentNotFound(f"Document with ID {document_id} was not found.")
        return doc

    def get_workspace_documents(
        self,
        workspace_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        """List documents in a workspace with pagination."""
        if page < 1:
            raise ValidationError("Page number must be >= 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        skip = (page - 1) * page_size
        docs = self.repository.get_by_workspace_paginated(
            workspace_id=workspace_id,
            skip=skip,
            limit=page_size,
        )
        total = self.repository.count_by_workspace(workspace_id)
        return docs, total

    def create_document(
        self,
        workspace_id: UUID,
        filename: str,
        original_filename: str,
        file_type: str = "pdf",
        file_size: int = 0,
        page_count: int = 0,
        status: DocumentStatus = DocumentStatus.UPLOADED,
    ) -> Document:
        """Create a new document record."""
        if not filename or not filename.strip():
            raise ValidationError("Filename cannot be empty.")

        document = Document(
            id=uuid4(),
            workspace_id=workspace_id,
            filename=filename.strip(),
            original_filename=original_filename.strip(),
            file_type=file_type,
            file_size=file_size,
            page_count=page_count,
            status=status.value if isinstance(status, DocumentStatus) else status,
        )
        self.repository.create(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_document(self, document_id: UUID) -> None:
        """Delete a document and its associated records."""
        doc = self.get_document(document_id)
        # Delete related chunks
        chunks = self.chunk_repository.get_by_document(document_id)
        for chunk in chunks:
            self.chunk_repository.delete(chunk)

        # Delete related ingestion jobs
        jobs = self.job_repository.get_by_document(document_id)
        for job in jobs:
            self.job_repository.delete(job)

        self.repository.delete(doc)
        self.db.commit()

    def ingest_document(
        self,
        workspace_id: UUID,
        file_path: Path | str,
        original_filename: str,
        file_size: int = 0,
    ) -> tuple[Document, IngestionJob, int]:
        """
        Full V2 document ingestion workflow:
        1. Create IngestionJob (QUEUED/RUNNING).
        2. Create and mark Document PROCESSING.
        3. Call ingest_func(file_path).
        4. Validate extracted chunks.
        5. Call add_documents(chunks) to index into FAISS.
        6. Persist chunks in document_chunks table.
        7. Mark Document INDEXED.
        8. Mark IngestionJob SUCCEEDED.
        On failure:
        - Mark Document FAILED.
        - Mark IngestionJob FAILED with error message.
        - Raise IngestionError.
        """
        path = Path(file_path)
        safe_name = path.name

        # 1. Create Document with PROCESSING status
        document = Document(
            id=uuid4(),
            workspace_id=workspace_id,
            filename=safe_name,
            original_filename=original_filename,
            file_type=path.suffix.lstrip(".").lower() or "pdf",
            file_size=file_size,
            page_count=0,
            status=DocumentStatus.PROCESSING.value,
        )
        self.repository.create(document)

        # 2. Create IngestionJob with RUNNING status
        job = IngestionJob(
            id=uuid4(),
            document_id=document.id,
            status=IngestionStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc),
        )
        self.job_repository.create(job)
        self.db.commit()
        self.db.refresh(document)
        self.db.refresh(job)

        try:
            # 3. Call existing ingestion function
            chunks = ingest_func(path)

            # 4. Validate extracted chunks
            if not chunks:
                raise IngestionError(
                    "No readable text content could be extracted from this document."
                )

            # 5. Add chunks to FAISS vector store
            add_documents(chunks)

            # 6. Persist chunks to database
            db_chunks = []
            max_page = 0
            for i, chunk in enumerate(chunks):
                page_num = chunk.metadata.get("page", 1) if chunk.metadata else 1
                if isinstance(page_num, int) and page_num > max_page:
                    max_page = page_num
                db_chunks.append(
                    DocumentChunk(
                        id=uuid4(),
                        document_id=document.id,
                        chunk_index=i,
                        content=chunk.page_content,
                        page_number=page_num if isinstance(page_num, int) else 1,
                    )
                )
            self.chunk_repository.bulk_create(db_chunks)

            # 7. Update document status to INDEXED
            document.status = DocumentStatus.INDEXED.value
            document.page_count = max(max_page, 1)

            # 8. Mark ingestion job SUCCEEDED
            job.status = IngestionStatus.SUCCEEDED.value
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(document)
            self.db.refresh(job)

            logger.info(
                "Document %s (%s) ingested successfully: %d chunks created.",
                document.id, original_filename, len(chunks)
            )
            return document, job, len(chunks)

        except Exception as e:
            self.db.rollback()
            error_message = str(e)
            logger.exception("Ingestion failed for document %s: %s", document.id, error_message)

            try:
                self.job_repository.update_status(
                    job.id,
                    status=IngestionStatus.FAILED.value,
                    error_message=error_message,
                    completed=True,
                )
                self.repository.update_status(
                    document.id,
                    status=DocumentStatus.FAILED.value,
                )
                self.db.commit()
            except Exception:
                self.db.rollback()

            raise IngestionError(f"Document ingestion failed: {error_message}") from e