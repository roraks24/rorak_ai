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
    db_session.query(Workspace).filter(Workspace.id == ws.id).delete()
    db_session.query(User).filter(User.id == user.id).delete()
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

    # DB connectivity test endpoint
    resp_db = client.get("/documents/db-test")
    assert resp_db.status_code == 200
    assert resp_db.json()["database"] == "connected"


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

