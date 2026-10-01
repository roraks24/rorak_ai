import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.db import (
    Conversation,
    Document,
    DocumentChunk,
    IngestionJob,
    Memory,
    Message,
    User,
    Workspace,
    WorkspaceMember,
)


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
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
    db_session.add(user)
    db_session.add(ws)
    db_session.add(member)
    db_session.commit()

    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    old_auth = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {token}"

    try:
        yield ws, user
    finally:
        if old_auth:
            client.headers["Authorization"] = old_auth
        else:
            client.headers.pop("Authorization", None)

        # Cleanup
        db_session.query(Memory).filter((Memory.workspace_id == ws.id) | (Memory.user_id == user.id)).delete(synchronize_session=False)
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

def test_workspace_api_crud(db_session):
    user = User(id=uuid.uuid4(), email=f"ws_crud_{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    headers = {"Authorization": f"Bearer {token}"}
    ws_name = f"API_Test_WS_{uuid.uuid4().hex[:8]}"

    # Create workspace
    resp = client.post("/workspaces/", json={"name": ws_name}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == ws_name
    ws_id = data["id"]

    # Duplicate name fails with 409
    resp_dup = client.post("/workspaces/", json={"name": ws_name}, headers=headers)
    assert resp_dup.status_code == 409

    # Validation failure: empty name
    resp_empty = client.post("/workspaces/", json={"name": ""}, headers=headers)
    assert resp_empty.status_code == 422

    # Get workspace by ID
    resp_get = client.get(f"/workspaces/{ws_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == ws_id

    # List workspaces
    resp_list = client.get("/workspaces/", headers=headers)
    assert resp_list.status_code == 200
    assert resp_list.json()["pagination"]["total"] >= 1

    # Delete workspace
    resp_del = client.delete(f"/workspaces/{ws_id}", headers=headers)
    assert resp_del.status_code == 200

    # 404 after deletion
    resp_gone = client.get(f"/workspaces/{ws_id}", headers=headers)
    assert resp_gone.status_code == 404


def test_workspace_members_api(setup_user_and_workspace, db_session):
    ws, owner = setup_user_and_workspace
    new_user = User(id=uuid.uuid4(), email=f"member_user_{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(new_user)
    db_session.commit()

    # Add member
    resp = client.post(
        f"/workspaces/{ws.id}/members",
        json={"user_id": str(new_user.id), "role": "admin"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"

    # Duplicate member fails with 409
    resp_dup = client.post(
        f"/workspaces/{ws.id}/members",
        json={"user_id": str(new_user.id), "role": "member"},
    )
    assert resp_dup.status_code == 409

    # List members
    resp_list = client.get(f"/workspaces/{ws.id}/members")
    assert resp_list.status_code == 200
    assert any(m["user_id"] == str(new_user.id) for m in resp_list.json())

    # Remove member
    resp_rm = client.delete(f"/workspaces/{ws.id}/members/{new_user.id}")
    assert resp_rm.status_code == 200

    # Removing again fails with 400
    resp_rm_again = client.delete(f"/workspaces/{ws.id}/members/{new_user.id}")
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


def test_memory_api_crud(setup_user_and_workspace):
    """Verify Memory REST API lifecycle: create, list, get, patch, delete."""
    ws, user = setup_user_and_workspace

    # 1. Create memory
    resp = client.post(
        "/memories/",
        json={
            "user_id": str(user.id),
            "workspace_id": str(ws.id),
            "content": "API preference: User prefers JSON responses",
            "memory_type": "preference",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "API preference: User prefers JSON responses"
    assert data["memory_type"] == "preference"
    mem_id = data["id"]

    # 2. Sensitive content rejected with 400
    resp_sens = client.post(
        "/memories/",
        json={
            "user_id": str(user.id),
            "content": "Secret key is sk-123456789012345678901234",
            "memory_type": "secret",
        },
    )
    assert resp_sens.status_code == 400

    # 3. Get memory by ID
    resp_get = client.get(f"/memories/{mem_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == mem_id

    # 4. List memories
    resp_list = client.get(f"/memories/?user_id={user.id}&workspace_id={ws.id}")
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["pagination"]["total"] >= 1
    assert any(m["id"] == mem_id for m in list_data["memories"])

    # 5. Update memory
    resp_patch = client.patch(
        f"/memories/{mem_id}",
        json={
            "content": "Updated API preference: User prefers YAML responses",
            "memory_type": "format_preference",
        },
    )
    assert resp_patch.status_code == 200
    patch_data = resp_patch.json()
    assert patch_data["content"] == "Updated API preference: User prefers YAML responses"
    assert patch_data["memory_type"] == "format_preference"

    # 6. Delete memory
    resp_del = client.delete(f"/memories/{mem_id}")
    assert resp_del.status_code == 200

    # 7. 404 after deletion
    resp_gone = client.get(f"/memories/{mem_id}")
    assert resp_gone.status_code == 404


def test_step_9_conversation_api_contract(setup_user_and_workspace):
    """
    Step 9 — API Contracts:
    - Create: POST /conversations (Bind to correct user/workspace)
    - List: GET /conversations (Scoped + paginated)
    - Get: GET /conversations/{id} (Reopen, scoped lookup)
    - Rename: PATCH /conversations/{id} (Change title, no message mutation)
    - Messages: GET /conversations/{id}/messages (Load history in deterministic order)
    - Chat continuity: carry conversation_id when continuing an existing thread, avoid creating a new conversation for every message
    - Delete: DELETE /conversations/{id} (Remove thread, safe message cleanup)
    """
    from unittest.mock import patch

    ws, user = setup_user_and_workspace

    # 1. Create thread (POST /conversations)
    resp_create = client.post(
        "/conversations/",
        json={
            "workspace_id": str(ws.id),
            "user_id": str(user.id),
            "title": "Initial Step 9 Thread",
        },
    )
    assert resp_create.status_code == 201
    conv_data = resp_create.json()
    assert conv_data["title"] == "Initial Step 9 Thread"
    assert conv_data["workspace_id"] == str(ws.id)
    assert conv_data["user_id"] == str(user.id)
    conv_id = conv_data["id"]

    # 2. List threads (GET /conversations) - scoped and paginated
    resp_list_ws = client.get(f"/conversations/?workspace_id={ws.id}&page=1&page_size=10")
    assert resp_list_ws.status_code == 200
    assert resp_list_ws.json()["pagination"]["total"] == 1

    resp_list_user = client.get(f"/conversations/?user_id={user.id}&page=1&page_size=10")
    assert resp_list_user.status_code == 200
    assert resp_list_user.json()["pagination"]["total"] == 1

    # Calling without any scope returns 422
    resp_no_scope = client.get("/conversations/")
    assert resp_no_scope.status_code == 422

    # 3. Get thread (reopen with scoped lookup) (GET /conversations/{id})
    resp_get = client.get(f"/conversations/{conv_id}?workspace_id={ws.id}&user_id={user.id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == conv_id

    # Cross-workspace scoped lookup returns 404
    fake_ws_id = uuid.uuid4()
    resp_cross_ws = client.get(f"/conversations/{conv_id}?workspace_id={fake_ws_id}")
    assert resp_cross_ws.status_code == 404

    # 4. Add historical message before rename
    resp_msg1 = client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Message 1 before rename"},
    )
    assert resp_msg1.status_code == 201

    # 5. Rename thread (PATCH /conversations/{id}) - no message mutation
    resp_rename = client.patch(
        f"/conversations/{conv_id}",
        json={"title": "Updated Thread Title"},
        params={"workspace_id": str(ws.id), "user_id": str(user.id)},
    )
    assert resp_rename.status_code == 200
    assert resp_rename.json()["title"] == "Updated Thread Title"

    # Verify message was not mutated
    resp_msgs_check = client.get(f"/conversations/{conv_id}/messages")
    assert resp_msgs_check.status_code == 200
    assert len(resp_msgs_check.json()["messages"]) == 1
    assert resp_msgs_check.json()["messages"][0]["content"] == "Message 1 before rename"

    # 6. Messages endpoint (GET /conversations/{id}/messages) - deterministic order
    resp_msg2 = client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "Message 2 assistant reply"},
    )
    assert resp_msg2.status_code == 201

    resp_msgs = client.get(f"/conversations/{conv_id}/messages?page=1&page_size=10")
    assert resp_msgs.status_code == 200
    msgs_data = resp_msgs.json()["messages"]
    assert len(msgs_data) == 2
    # Deterministic chronological order
    assert msgs_data[0]["content"] == "Message 1 before rename"
    assert msgs_data[1]["content"] == "Message 2 assistant reply"

    # 7. Chat continuity: carry conversation_id when continuing an existing thread
    with patch("backend.services.conversation_service.chat_func") as mock_chat:
        mock_chat.return_value = "Turn 1 answer from Rorak"

        # Turn 1 continuing existing thread
        resp_turn1 = client.post(
            "/chat/",
            json={
                "question": "Chat Turn 1 question",
                "conversation_id": conv_id,
                "workspace_id": str(ws.id),
                "user_id": str(user.id),
            },
        )
        assert resp_turn1.status_code == 200
        assert resp_turn1.json()["conversation_id"] == conv_id
        assert resp_turn1.json()["answer"] == "Turn 1 answer from Rorak"

        # Turn 2 continuing existing thread
        mock_chat.return_value = "Turn 2 answer from Rorak"
        resp_turn2 = client.post(
            "/chat/",
            json={
                "question": "Chat Turn 2 question",
                "conversation_id": conv_id,
                "workspace_id": str(ws.id),
                "user_id": str(user.id),
            },
        )
        assert resp_turn2.status_code == 200
        assert resp_turn2.json()["conversation_id"] == conv_id
        assert resp_turn2.json()["answer"] == "Turn 2 answer from Rorak"

    # Verify no new duplicate conversations were created for every message
    resp_list_threads = client.get(f"/conversations/?workspace_id={ws.id}")
    assert resp_list_threads.status_code == 200
    assert resp_list_threads.json()["pagination"]["total"] == 1

    # 8. Delete thread (DELETE /conversations/{id}) - safe message cleanup
    resp_del = client.delete(f"/conversations/{conv_id}")
    assert resp_del.status_code == 200

    # 404 after deletion
    resp_reopen_deleted = client.get(f"/conversations/{conv_id}")
    assert resp_reopen_deleted.status_code == 404


def test_step_10_and_11_frontend_contracts(setup_user_and_workspace):
    """
    Step 10 & 11 — End-to-end backend contract support for frontend experience:
    - Default user provisioning
    - Conversation lifecycle with message history deterministic restore
    - Memory list with scope isolation and individual deletion
    """
    ws, user = setup_user_and_workspace

    # 1. Default user endpoint works
    resp_user = client.get("/users/default")
    assert resp_user.status_code == 200
    default_user_data = resp_user.json()
    assert "id" in default_user_data
    assert default_user_data["email"] == "default@rorak.tech"

    # 2. Step 10: Create conversation thread
    resp_conv = client.post(
        "/conversations/",
        json={
            "workspace_id": str(ws.id),
            "user_id": str(user.id),
            "title": "Initial Frontend Thread",
        },
    )
    assert resp_conv.status_code == 201
    conv_id = resp_conv.json()["id"]

    # 3. Add message to thread
    resp_msg = client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Hello Rorak!"},
    )
    assert resp_msg.status_code == 201

    # 4. Fetch messages deterministic history
    resp_messages = client.get(f"/conversations/{conv_id}/messages?workspace_id={ws.id}")
    assert resp_messages.status_code == 200
    msg_data = resp_messages.json()
    assert msg_data["pagination"]["total"] >= 1
    assert msg_data["messages"][0]["content"] == "Hello Rorak!"

    # 5. Rename conversation
    resp_rename = client.patch(
        f"/conversations/{conv_id}?workspace_id={ws.id}",
        json={"title": "Renamed Frontend Thread"},
    )
    assert resp_rename.status_code == 200
    assert resp_rename.json()["title"] == "Renamed Frontend Thread"

    # 6. Step 11: Create memory and verify scope
    resp_mem = client.post(
        "/memories/",
        json={
            "user_id": str(user.id),
            "workspace_id": str(ws.id),
            "content": "User prefers concise answers",
            "memory_type": "user_preference",
        },
    )
    assert resp_mem.status_code == 201
    mem_id = resp_mem.json()["id"]
    assert resp_mem.json()["workspace_id"] == str(ws.id)

    # 7. List memories with scope
    resp_mem_list = client.get(f"/memories/?user_id={user.id}&workspace_id={ws.id}&include_global=true")
    assert resp_mem_list.status_code == 200
    assert resp_mem_list.json()["pagination"]["total"] >= 1

    # 8. Delete individual memory
    resp_del_mem = client.delete(f"/memories/{mem_id}?user_id={user.id}&workspace_id={ws.id}")
    assert resp_del_mem.status_code == 200

    # 9. Clean up conversation
    client.delete(f"/conversations/{conv_id}?workspace_id={ws.id}")
