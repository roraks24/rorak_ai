"""
Unit tests for document upload validation and error contracts in V2.2.
"""
import io
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.documents import Document as LCDocument

from backend.main import app
from backend.core.database import get_db
from backend.models.db import Workspace, Document, DocumentChunk, IngestionJob


client = TestClient(app)


@pytest.fixture
def test_workspace():
    gen = get_db()
    session = next(gen)
    ws = Workspace(id=uuid.uuid4(), name=f"DocUploadTest_WS_{uuid.uuid4().hex[:8]}")
    session.add(ws)
    session.commit()
    try:
        yield ws
    finally:
        # Clean any documents, chunks, jobs for this workspace in reverse FK order
        doc_ids = [d.id for d in session.query(Document).filter(Document.workspace_id == ws.id).all()]
        if doc_ids:
            session.query(DocumentChunk).filter(DocumentChunk.document_id.in_(doc_ids)).delete(synchronize_session=False)
            session.query(IngestionJob).filter(IngestionJob.document_id.in_(doc_ids)).delete(synchronize_session=False)
            session.query(Document).filter(Document.workspace_id == ws.id).delete(synchronize_session=False)
        session.query(Workspace).filter(Workspace.id == ws.id).delete(synchronize_session=False)
        session.commit()


def test_upload_missing_workspace_id_rejected():
    """Verify upload without required workspace_id query parameter returns 422."""
    file_bytes = io.BytesIO(b"%PDF-1.4 header")
    response = client.post(
        "/documents/upload",
        files={"file": ("test.pdf", file_bytes, "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_non_pdf_file_rejected(test_workspace):
    """Verify non-PDF file upload returns 400 Bad Request with descriptive message."""
    file_bytes = io.BytesIO(b"Plain text content")
    response = client.post(
        f"/documents/upload?workspace_id={test_workspace.id}",
        files={"file": ("test.txt", file_bytes, "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Only PDF files are supported" in data["detail"]


def test_upload_empty_pdf_rejected(test_workspace):
    """Verify empty 0-byte PDF upload returns 422 Unprocessable Entity."""
    empty_bytes = io.BytesIO(b"")
    response = client.post(
        f"/documents/upload?workspace_id={test_workspace.id}",
        files={"file": ("empty.pdf", empty_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "No readable text content could be extracted" in data["detail"]


def test_upload_valid_pdf_success(test_workspace):
    """Verify valid PDF upload succeeds and returns 201 Created with DocumentUploadResponse."""
    valid_pdf_bytes = io.BytesIO(b"%PDF-1.4 header dummy content for upload test")

    with patch("backend.services.document_service.ingest_func") as mock_ingest:
        mock_ingest.return_value = [
            LCDocument(page_content="Valid chunk content 1", metadata={"source": "valid.pdf", "page": 1}),
            LCDocument(page_content="Valid chunk content 2", metadata={"source": "valid.pdf", "page": 2}),
        ]
        response = client.post(
            f"/documents/upload?workspace_id={test_workspace.id}",
            files={"file": ("valid.pdf", valid_pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "document" in data
    assert data["document"]["original_filename"] == "valid.pdf"
    assert data["document"]["display_name"] == "valid.pdf"
    assert data["chunk_count"] == 2
    assert "ingestion_job" in data
    assert data["ingestion_job"]["status"] == "SUCCEEDED"

    # Cleanup the created document via DELETE endpoint
    doc_id = data["document"]["id"]
    del_resp = client.delete(f"/documents/{doc_id}")
    assert del_resp.status_code == 204
