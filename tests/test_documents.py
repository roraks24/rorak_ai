"""
Unit tests for document upload validation and error contracts.
"""
import io
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.documents import Document as LCDocument

from backend.main import app
from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.db import User, Document, DocumentChunk, IngestionJob


client = TestClient(app)


@pytest.fixture(autouse=True)
def doc_test_auth():
    gen = get_db()
    session = next(gen)
    user = User(id=uuid.uuid4(), email=f"doc_auth_{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.commit()
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    client.headers["Authorization"] = f"Bearer {token}"
    try:
        yield user
    finally:
        client.headers.pop("Authorization", None)
        doc_ids = [d.id for d in session.query(Document).filter(Document.user_id == user.id).all()]
        if doc_ids:
            session.query(DocumentChunk).filter(DocumentChunk.document_id.in_(doc_ids)).delete(synchronize_session=False)
            session.query(IngestionJob).filter(IngestionJob.document_id.in_(doc_ids)).delete(synchronize_session=False)
            session.query(Document).filter(Document.user_id == user.id).delete(synchronize_session=False)
        session.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        session.commit()
        try:
            next(gen)
        except StopIteration:
            pass


def test_upload_unauthorized():
    """Verify upload without auth header returns 401."""
    client.headers.pop("Authorization", None)
    file_bytes = io.BytesIO(b"%PDF-1.4 header")
    response = client.post(
        "/documents/upload",
        files={"file": ("test.pdf", file_bytes, "application/pdf")},
    )
    assert response.status_code == 401


def test_upload_unsupported_format_rejected():
    """Verify that truly unsupported file types (e.g. .exe, .jpg) return 400 Bad Request."""
    file_bytes = io.BytesIO(b"MZ fake exe binary content")
    response = client.post(
        "/documents/upload",
        files={"file": ("malware.exe", file_bytes, "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Unsupported file type" in data["detail"]


def test_upload_jpg_rejected():
    """Verify that image files (.jpg) are also rejected with 400."""
    file_bytes = io.BytesIO(b"\xff\xd8\xff fake jpeg bytes")
    response = client.post(
        "/documents/upload",
        files={"file": ("photo.jpg", file_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Unsupported file type" in data["detail"]


def test_upload_empty_pdf_rejected():
    """Verify empty 0-byte PDF upload returns 422 Unprocessable Entity."""
    empty_bytes = io.BytesIO(b"")
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.pdf", empty_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "No readable text content could be extracted" in data["detail"]


def test_upload_valid_pdf_success():
    """Verify valid PDF upload succeeds and returns 201 Created with DocumentUploadResponse."""
    valid_pdf_bytes = io.BytesIO(b"%PDF-1.4 header dummy content for upload test")

    with patch("backend.services.document_service.ingest_func") as mock_ingest:
        mock_ingest.return_value = [
            LCDocument(page_content="Valid chunk content 1", metadata={"source": "valid.pdf", "page": 1}),
            LCDocument(page_content="Valid chunk content 2", metadata={"source": "valid.pdf", "page": 2}),
        ]
        response = client.post(
            "/documents/upload",
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
