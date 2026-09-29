import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import get_db
from backend.models.db import User, Workspace


client = TestClient(app)


@pytest.fixture
def db_session():
    gen = get_db()
    session = next(gen)
    try:
        yield session
    finally:
        session.rollback()
        try:
            next(gen)
        except StopIteration:
            pass


@pytest.fixture
def setup_user_and_workspace(db_session):
    user = User(id=uuid.uuid4(), email=f"api_test_{uuid.uuid4()}@example.com")
    ws = Workspace(id=uuid.uuid4(), name=f"API_WS_{uuid.uuid4().hex[:8]}")
    db_session.add(user)
    db_session.add(ws)
    db_session.commit()
    yield ws, user

    # Cleanup
    from backend.models.db import DocumentChunk, IngestionJob, Document, Message, Conversation, WorkspaceMember
    doc_ids = [d.id for d in db_session.query(Document).filter(Document.workspace_id == ws.id).all()]
    if doc_ids:
        db_session.query(DocumentChunk).filter(DocumentChunk.document_id.in_(doc_ids)).delete(synchronize_session=False)
        db_session.query(IngestionJob).filter(IngestionJob.document_id.in_(doc_ids)).delete(synchronize_session=False)
        db_session.query(Document).filter(Document.workspace_id == ws.id).delete(synchronize_session=False)
    conv_ids = [c.id for c in db_session.query(Conversation).filter(Conversation.workspace_id == ws.id).all()]
    if conv_ids:
        db_session.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db_session.query(Conversation).filter(Conversation.workspace_id == ws.id).delete(synchronize_session=False)
    db_session.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws.id).delete(synchronize_session=False)
    db_session.query(Workspace).filter(Workspace.id == ws.id).delete(synchronize_session=False)
    db_session.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db_session.commit()


# ============================================================
# WORKSPACE API TESTS
# ============================================================

def test_workspace_api_crud():
    ws_name = f"API_Test_WS_{uuid.uuid4().hex[:8]}"

    # Create workspace
    resp = client.post("/workspaces/", json={"name": ws_name})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == ws_name
    ws_id = data["id"]

    # Duplicate name fails with 409
    resp_dup = client.post("/workspaces/", json={"name": ws_name})
    assert resp_dup.status_code == 409

    # Validation failure: empty name
    resp_empty = client.post("/workspaces/", json={"name": ""})
    assert resp_empty.status_code == 422

    # Get workspace by ID
    resp_get = client.get(f"/workspaces/{ws_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == ws_id

    # List workspaces
    resp_list = client.get("/workspaces/")
    assert resp_list.status_code == 200
    assert resp_list.json()["pagination"]["total"] >= 1

    # Delete workspace
    resp_del = client.delete(f"/workspaces/{ws_id}")
    assert resp_del.status_code == 200

    # 404 after deletion
    resp_gone = client.get(f"/workspaces/{ws_id}")
    assert resp_gone.status_code == 404


def test_workspace_members_api(setup_user_and_workspace):
    ws, user = setup_user_and_workspace

    # Add member
    resp = client.post(
        f"/workspaces/{ws.id}/members",
        json={"user_id": str(user.id), "role": "admin"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"

    # Duplicate member fails with 409
    resp_dup = client.post(
        f"/workspaces/{ws.id}/members",
        json={"user_id": str(user.id), "role": "member"},
    )
    assert resp_dup.status_code == 409

    # List members
    resp_list = client.get(f"/workspaces/{ws.id}/members")
    assert resp_list.status_code == 200
    assert len(resp_list.json()) == 1

    # Remove member
    resp_rm = client.delete(f"/workspaces/{ws.id}/members/{user.id}")
    assert resp_rm.status_code == 200

    # Removing again fails with 400
    resp_rm_again = client.delete(f"/workspaces/{ws.id}/members/{user.id}")
    assert resp_rm_again.status_code == 400


# ============================================================
# CONVERSATION API TESTS
# ============================================================

def test_conversation_api_flow(setup_user_and_workspace):
    ws, user = setup_user_and_workspace

    # Create conversation
    resp = client.post(
        "/conversations/",
        json={
            "workspace_id": str(ws.id),
            "user_id": str(user.id),
            "title": "API Thread",
        },
    )
    assert resp.status_code == 201
    conv_id = resp.json()["id"]

    # Get conversation
    resp_get = client.get(f"/conversations/{conv_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["title"] == "API Thread"

    # List conversations for workspace
    resp_list = client.get(f"/conversations/?workspace_id={ws.id}")
    assert resp_list.status_code == 200
    assert resp_list.json()["pagination"]["total"] == 1

    # Create message
    resp_msg = client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "How do I use Rorak?"},
    )
    assert resp_msg.status_code == 201
    assert resp_msg.json()["content"] == "How do I use Rorak?"

    # List messages
    resp_msgs = client.get(f"/conversations/{conv_id}/messages")
    assert resp_msgs.status_code == 200
    assert len(resp_msgs.json()["messages"]) == 1

    # Delete conversation
    resp_del = client.delete(f"/conversations/{conv_id}")
    assert resp_del.status_code == 200

    # 404 after delete
    resp_gone = client.get(f"/conversations/{conv_id}")
    assert resp_gone.status_code == 404


# ============================================================
# DOCUMENT V2 API TESTS
# ============================================================

def test_document_v2_api(setup_user_and_workspace):
    ws, _ = setup_user_and_workspace

    # List documents for empty workspace
    resp_list = client.get(f"/documents/?workspace_id={ws.id}")
    assert resp_list.status_code == 200
    assert resp_list.json()["pagination"]["total"] == 0

    # Nonexistent document returns 404
    fake_id = uuid.uuid4()
    resp_get = client.get(f"/documents/{fake_id}")
    assert resp_get.status_code == 404

    # DB connectivity test via readiness probe
    resp_db = client.get("/ready/")
    assert resp_db.status_code == 200
    assert resp_db.json()["database_connected"] is True


def test_api_pagination_query_validation(setup_user_and_workspace):
    """Verify API endpoints reject out-of-bounds pagination query parameters with 422."""
    ws, _ = setup_user_and_workspace

    # Workspaces
    assert client.get("/workspaces/?page=0").status_code == 422
    assert client.get("/workspaces/?page_size=0").status_code == 422
    assert client.get("/workspaces/?page_size=101").status_code == 422

    # Conversations
    assert client.get(f"/conversations/?workspace_id={ws.id}&page=0").status_code == 422
    assert client.get(f"/conversations/?workspace_id={ws.id}&page_size=101").status_code == 422

    # Documents
    assert client.get(f"/documents/?workspace_id={ws.id}&page=0").status_code == 422
    assert client.get(f"/documents/?workspace_id={ws.id}&page_size=101").status_code == 422


def test_api_invalid_parameter_validation(setup_user_and_workspace):
    """Verify API endpoints reject malformed UUIDs and missing required parameters with 422."""
    ws, _ = setup_user_and_workspace

    # Missing required query param
    assert client.get("/conversations/").status_code == 422
    assert client.get("/documents/").status_code == 422

    # Malformed UUID paths
    assert client.get("/workspaces/not-a-uuid").status_code == 422
    assert client.get("/conversations/not-a-uuid").status_code == 422
    assert client.get("/documents/not-a-uuid").status_code == 422


# ============================================================
# V2.2 DOCUMENT API CONTRACT TESTS
# ============================================================

def test_document_v2_api_full_lifecycle(setup_user_and_workspace):
    """
    Test complete V2.2 document API lifecycle:
    - POST /documents/upload?workspace_id=...
    - GET /documents/{document_id}
    - GET /documents/?workspace_id=...&page=1&page_size=20
    - PATCH /documents/{document_id}
    - DELETE /documents/{document_id}
    """
    import io
    from unittest.mock import patch
    from langchain_core.documents import Document as LCDocument

    ws, _ = setup_user_and_workspace

    # 1. POST /documents/upload
    pdf_content = b"%PDF-1.4 test api upload document lifecycle content"
    files = {"file": ("research_paper.pdf", io.BytesIO(pdf_content), "application/pdf")}

    with patch("backend.services.document_service.ingest_func") as mock_ingest:
        mock_ingest.return_value = [
            LCDocument(page_content="Section 1: Introduction", metadata={"page": 1}),
            LCDocument(page_content="Section 2: Methodology", metadata={"page": 2}),
        ]
        resp_upload = client.post(
            f"/documents/upload?workspace_id={ws.id}",
            files=files,
        )

    assert resp_upload.status_code in (200, 201), f"Upload failed: {resp_upload.text}"
    upload_data = resp_upload.json()
    assert "document" in upload_data, "Response must include 'document'"
    doc_data = upload_data["document"]
    doc_id = doc_data["id"]
    try:
        assert doc_data["workspace_id"] == str(ws.id)
        assert doc_data["display_name"] == "research_paper.pdf"
        assert doc_data["mime_type"] == "application/pdf"
        assert "chunk_count" in doc_data
        assert "status" in doc_data

        # 2. GET /documents/{document_id}
        resp_get = client.get(f"/documents/{doc_id}")
        assert resp_get.status_code == 200
        fetched_data = resp_get.json()
        assert fetched_data["id"] == doc_id
        assert fetched_data["display_name"] == "research_paper.pdf"
        assert fetched_data["mime_type"] == "application/pdf"

        # 3. GET /documents/?workspace_id=<uuid>&page=1&page_size=20
        resp_list = client.get(f"/documents/?workspace_id={ws.id}&page=1&page_size=20")
        assert resp_list.status_code == 200
        list_data = resp_list.json()
        assert "documents" in list_data
        assert "pagination" in list_data
        assert list_data["pagination"]["page"] == 1
        assert list_data["pagination"]["page_size"] == 20
        assert list_data["pagination"]["total"] >= 1
        doc_ids_in_list = [d["id"] for d in list_data["documents"]]
        assert doc_id in doc_ids_in_list

        # 4. PATCH /documents/{document_id} (Rename)
        rename_payload = {
            "display_name": "My Research Notes"
        }
        resp_patch = client.patch(
            f"/documents/{doc_id}",
            json=rename_payload,
        )
        assert resp_patch.status_code == 200, f"Rename failed: {resp_patch.text}"
        renamed_data = resp_patch.json()
        assert renamed_data["display_name"] == "My Research Notes"

        # Verify GET reflects the renamed display_name
        resp_get_after = client.get(f"/documents/{doc_id}")
        assert resp_get_after.status_code == 200
        assert resp_get_after.json()["display_name"] == "My Research Notes"

        # 5. DELETE /documents/{document_id}
        resp_del = client.delete(f"/documents/{doc_id}")
        assert resp_del.status_code in (200, 204), f"Delete failed: {resp_del.text}"

        # Verify 404 after deletion
        resp_get_deleted = client.get(f"/documents/{doc_id}")
        assert resp_get_deleted.status_code == 404
    finally:
        # Cleanup document if still present
        client.delete(f"/documents/{doc_id}")


def test_document_v2_rename_validation_api(setup_user_and_workspace):
    """Verify PATCH /documents/{document_id} rejects invalid payloads."""
    ws, _ = setup_user_and_workspace
    fake_id = uuid.uuid4()

    # Reject nonexistent document with 404
    resp_404 = client.patch(
        f"/documents/{fake_id}",
        json={"display_name": "My Research Notes"},
    )
    assert resp_404.status_code == 404

    # Reject empty display_name
    resp_empty = client.patch(
        f"/documents/{fake_id}",
        json={"display_name": ""},
    )
    assert resp_empty.status_code in (400, 422)

    # Reject whitespace-only display_name
    resp_ws = client.patch(
        f"/documents/{fake_id}",
        json={"display_name": "   "},
    )
    assert resp_ws.status_code in (400, 422)

    # Reject display_name exceeding 255 chars
    resp_long = client.patch(
        f"/documents/{fake_id}",
        json={"display_name": "A" * 256},
    )
    assert resp_long.status_code in (400, 422)

