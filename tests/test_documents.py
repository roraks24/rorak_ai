"""
Unit tests for document upload validation and error contracts.
"""
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from backend.main import app


client = TestClient(app)


def test_upload_non_pdf_file_rejected():
    """Verify non-PDF file upload returns 400 Bad Request with structured error."""
    file_bytes = io.BytesIO(b"Plain text content")
    response = client.post(
        "/documents/upload",
        files={"file": ("test.txt", file_bytes, "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_empty_pdf_rejected():
    """Verify empty 0-byte PDF upload returns 400 Bad Request."""
    empty_bytes = io.BytesIO(b"")
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.pdf", empty_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "EMPTY_FILE"


def test_upload_oversized_pdf_rejected():
    """Verify oversized file upload (> 10 MB) returns 413 Payload Too Large."""
    # 11 MB payload
    large_bytes = io.BytesIO(b"0" * (11 * 1024 * 1024))
    response = client.post(
        "/documents/upload",
        files={"file": ("huge.pdf", large_bytes, "application/pdf")}
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "FILE_TOO_LARGE"


@patch("backend.routes.documents.ingest_func")
@patch("backend.routes.documents.add_documents")
def test_upload_valid_pdf_success(mock_add_docs, mock_ingest):
    """Verify valid PDF upload succeeds and returns 200 with chunk metadata."""
    mock_ingest.return_value = [
        Document(page_content="Valid chunk content 1", metadata={"source": "valid.pdf", "page": 1}),
        Document(page_content="Valid chunk content 2", metadata={"source": "valid.pdf", "page": 2}),
    ]

    valid_pdf_bytes = io.BytesIO(b"%PDF-1.4 header dummy content")
    response = client.post(
        "/documents/upload",
        files={"file": ("valid.pdf", valid_pdf_bytes, "application/pdf")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "valid.pdf"
    assert data["chunks_created"] == 2
    mock_add_docs.assert_called_once()


def test_clear_documents_endpoint():
    """Verify DELETE /documents/clear resets the vector store and returns 200."""
    response = client.delete("/documents/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
