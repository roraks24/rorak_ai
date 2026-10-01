"""
Security Test Suite for Rorak AI V2.6: Authentication & Multi-User Isolation.

Covers:
- User registration (POST /auth/register), password hashing, email validation, duplicate user (409)
- Login (POST /auth/login), password verification, JWT issuance
- Authentication dependency: Bearer token extraction, signature validation, expiration, resolution
- Authorization & Isolation:
  - User A cannot access User B's conversation (403)
  - User A cannot modify/delete User B's memory (403)
  - User A cannot access User B's documents (403)
  - User A cannot access User B's workspace (403)
  - Wrong workspace -> denied (403)
  - Missing JWT -> 401
  - Invalid JWT -> 401
  - Expired JWT -> 401
  - Valid JWT + unauthorized resource -> denied (403)
- Removal of client-controlled identity:
  - Client-supplied user_id is ignored/overridden by current_user.id
"""
from datetime import timedelta
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.db import (
    User,
    Workspace,
    WorkspaceMember,
    Conversation,
    Message,
    Memory,
    Document,
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


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, email: str, password: str = "SecurePass123!") -> tuple[dict, str]:
    # Register
    reg_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert reg_resp.status_code == 201, reg_resp.text
    user_data = reg_resp.json()

    # Login
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return user_data, token


# ============================================================
# 1. REGISTRATION TESTS
# ============================================================

def test_register_success(db_session):
    email = f"reg_success_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPassword99!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert "id" in data

    # Verify password hash exists and is not plaintext
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != "StrongPassword99!"
    assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")


def test_register_duplicate_email():
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    resp1 = client.post(
        "/auth/register",
        json={"email": email, "password": "Password1234!"},
    )
    assert resp1.status_code == 201

    # Second registration with same email fails with 409
    resp2 = client.post(
        "/auth/register",
        json={"email": email, "password": "AnotherPassword567!"},
    )
    assert resp2.status_code == 409
    err = resp2.json()["detail"]["error"]
    assert err["code"] == "DUPLICATE_EMAIL"


def test_register_validation_failures():
    # Invalid email format (missing @)
    resp_no_at = client.post(
        "/auth/register",
        json={"email": "notanemail", "password": "Password1234!"},
    )
    assert resp_no_at.status_code == 400
    assert resp_no_at.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    # Password too short (< 8 chars)
    resp_short = client.post(
        "/auth/register",
        json={"email": f"short_{uuid.uuid4().hex[:8]}@example.com", "password": "short"},
    )
    assert resp_short.status_code == 400
    assert resp_short.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 2. LOGIN TESTS
# ============================================================

def test_login_success():
    email = f"login_ok_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "ValidPassword123!"
    client.post("/auth/register", json={"email": email, "password": pwd})

    resp = client.post("/auth/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"].lower() == "bearer"
    assert data["expires_in"] > 0


def test_login_wrong_password():
    email = f"wrong_pwd_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "RightPassword123!"})

    resp = client.post("/auth/login", json={"email": email, "password": "IncorrectPassword!"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"
    assert "WWW-Authenticate" in resp.headers


def test_login_nonexistent_user():
    resp = client.post(
        "/auth/login",
        json={"email": "nonexistent_ghost_user@example.com", "password": "AnyPassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


# ============================================================
# 3. AUTHENTICATION DEPENDENCY TESTS (401 CODES)
# ============================================================

def test_auth_missing_jwt():
    # Calling protected endpoint without token returns 401
    resp = client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "UNAUTHORIZED"
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_auth_invalid_jwt():
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"


def test_auth_expired_jwt():
    user_id = uuid.uuid4()
    # Issue a token that expired 1 hour ago
    expired_token = create_access_token(
        subject=str(user_id),
        expires_delta=timedelta(hours=-1),
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "TOKEN_EXPIRED"


def test_auth_valid_jwt():
    email = f"me_test_{uuid.uuid4().hex[:8]}@example.com"
    user_data, token = register_and_login(client, email)

    resp = client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == user_data["id"]
    assert resp.json()["email"] == email


# ============================================================
# 4. WORKSPACE ISOLATION & AUTHORIZATION TESTS
# ============================================================

def test_workspace_isolation():
    # Setup User A and User B
    user_a, token_a = register_and_login(client, f"usera_ws_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_ws_{uuid.uuid4().hex[:8]}@example.com")

    # User A creates Workspace A
    resp_ws_a = client.post(
        "/workspaces/",
        json={"name": f"WS_A_{uuid.uuid4().hex[:8]}"},
        headers=auth_header(token_a),
    )
    assert resp_ws_a.status_code == 201
    ws_a_id = resp_ws_a.json()["id"]

    # User B creates Workspace B
    resp_ws_b = client.post(
        "/workspaces/",
        json={"name": f"WS_B_{uuid.uuid4().hex[:8]}"},
        headers=auth_header(token_b),
    )
    assert resp_ws_b.status_code == 201
    ws_b_id = resp_ws_b.json()["id"]

    # User A CANNOT access User B's Workspace B -> 403 Forbidden
    resp_a_on_b = client.get(
        f"/workspaces/{ws_b_id}",
        headers=auth_header(token_a),
    )
    assert resp_a_on_b.status_code == 403
    assert resp_a_on_b.json()["detail"]["error"]["code"] == "FORBIDDEN"

    # User A CANNOT add members to Workspace B -> 403 Forbidden
    resp_add_member = client.post(
        f"/workspaces/{ws_b_id}/members",
        json={"user_id": user_a["id"], "role": "member"},
        headers=auth_header(token_a),
    )
    assert resp_add_member.status_code == 403

    # User A CANNOT delete Workspace B -> 403 Forbidden
    resp_del_b = client.delete(
        f"/workspaces/{ws_b_id}",
        headers=auth_header(token_a),
    )
    assert resp_del_b.status_code == 403

    # Nonexistent workspace returns 404 (not 403)
    random_ws = str(uuid.uuid4())
    resp_nonexistent = client.get(
        f"/workspaces/{random_ws}",
        headers=auth_header(token_a),
    )
    assert resp_nonexistent.status_code == 404


# ============================================================
# 5. CONVERSATION & MESSAGE ISOLATION TESTS
# ============================================================

def test_conversation_and_message_isolation():
    user_a, token_a = register_and_login(client, f"usera_conv_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_conv_{uuid.uuid4().hex[:8]}@example.com")

    # Workspaces
    ws_a = client.post("/workspaces/", json={"name": f"WS_A_{uuid.uuid4().hex[:8]}"}, headers=auth_header(token_a)).json()
    ws_b = client.post("/workspaces/", json={"name": f"WS_B_{uuid.uuid4().hex[:8]}"}, headers=auth_header(token_b)).json()

    # User B creates conversation in Workspace B
    conv_b = client.post(
        "/conversations/",
        json={"workspace_id": ws_b["id"], "title": "User B Secret Thread"},
        headers=auth_header(token_b),
    ).json()
    conv_b_id = conv_b["id"]

    # User B posts a message in Conversation B
    msg_b = client.post(
        f"/conversations/{conv_b_id}/messages",
        json={"role": "user", "content": "Confidential data for User B"},
        headers=auth_header(token_b),
    ).json()

    # SECURITY CHECK 1: User A cannot access User B's conversation (403)
    resp_get = client.get(f"/conversations/{conv_b_id}", headers=auth_header(token_a))
    assert resp_get.status_code == 403
    assert resp_get.json()["detail"]["error"]["code"] == "FORBIDDEN"

    # SECURITY CHECK 2: User A cannot read User B's conversation messages (403)
    resp_msgs = client.get(f"/conversations/{conv_b_id}/messages", headers=auth_header(token_a))
    assert resp_msgs.status_code == 403

    # SECURITY CHECK 3: User A cannot post messages to User B's conversation (403)
    resp_post_msg = client.post(
        f"/conversations/{conv_b_id}/messages",
        json={"role": "user", "content": "Injected by User A"},
        headers=auth_header(token_a),
    )
    assert resp_post_msg.status_code == 403

    # SECURITY CHECK 4: User A cannot rename User B's conversation (403)
    resp_rename = client.patch(
        f"/conversations/{conv_b_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(token_a),
    )
    assert resp_rename.status_code == 403

    # SECURITY CHECK 5: User A cannot delete User B's conversation (403)
    resp_del = client.delete(f"/conversations/{conv_b_id}", headers=auth_header(token_a))
    assert resp_del.status_code == 403

    # SECURITY CHECK 6: User A cannot list User B's conversations (403)
    resp_list_spoof = client.get(
        f"/conversations/?user_id={user_b['id']}",
        headers=auth_header(token_a),
    )
    assert resp_list_spoof.status_code == 403

    # SECURITY CHECK 7: User A cannot create conversation in User B's workspace (403)
    resp_create_wrong_ws = client.post(
        "/conversations/",
        json={"workspace_id": ws_b["id"], "title": "Thread in unauthorized WS"},
        headers=auth_header(token_a),
    )
    assert resp_create_wrong_ws.status_code == 403


# ============================================================
# 6. MEMORY ISOLATION TESTS
# ============================================================

def test_memory_isolation():
    user_a, token_a = register_and_login(client, f"usera_mem_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_mem_{uuid.uuid4().hex[:8]}@example.com")

    # User B creates a private memory
    mem_b = client.post(
        "/memories/",
        json={
            "content": "User B prefers Python 3.14 async syntax",
            "memory_type": "user_preference",
        },
        headers=auth_header(token_b),
    ).json()
    mem_b_id = mem_b["id"]

    # SECURITY CHECK 1: User A cannot access User B's memory (403)
    resp_get = client.get(f"/memories/{mem_b_id}", headers=auth_header(token_a))
    assert resp_get.status_code == 403
    assert resp_get.json()["detail"]["error"]["code"] == "FORBIDDEN"

    # SECURITY CHECK 2: User A cannot modify User B's memory (403)
    resp_patch = client.patch(
        f"/memories/{mem_b_id}",
        json={"content": "Overwritten by User A"},
        headers=auth_header(token_a),
    )
    assert resp_patch.status_code == 403

    # SECURITY CHECK 3: User A cannot delete User B's memory (403)
    resp_del = client.delete(f"/memories/{mem_b_id}", headers=auth_header(token_a))
    assert resp_del.status_code == 403

    # SECURITY CHECK 4: User A cannot list User B's memories (403)
    resp_list_spoof = client.get(
        f"/memories/?user_id={user_b['id']}",
        headers=auth_header(token_a),
    )
    assert resp_list_spoof.status_code == 403


# ============================================================
# 7. DOCUMENT ISOLATION TESTS
# ============================================================

def test_document_isolation():
    user_a, token_a = register_and_login(client, f"usera_doc_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_doc_{uuid.uuid4().hex[:8]}@example.com")

    ws_b = client.post("/workspaces/", json={"name": f"WS_B_{uuid.uuid4().hex[:8]}"}, headers=auth_header(token_b)).json()

    # User A cannot list documents of Workspace B (403)
    resp_docs = client.get(f"/documents/?workspace_id={ws_b['id']}", headers=auth_header(token_a))
    assert resp_docs.status_code == 403

    # User A cannot upload documents to Workspace B (403)
    resp_upload = client.post(
        f"/documents/upload?workspace_id={ws_b['id']}",
        files={"file": ("test.pdf", b"%PDF-1.4 mock content", "application/pdf")},
        headers=auth_header(token_a),
    )
    assert resp_upload.status_code == 403


# ============================================================
# 8. CHAT ENDPOINT PROTECTION
# ============================================================

def test_chat_isolation_and_ownership():
    user_a, token_a = register_and_login(client, f"usera_chat_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_chat_{uuid.uuid4().hex[:8]}@example.com")

    ws_b = client.post("/workspaces/", json={"name": f"WS_B_{uuid.uuid4().hex[:8]}"}, headers=auth_header(token_b)).json()

    conv_b = client.post(
        "/conversations/",
        json={"workspace_id": ws_b["id"], "title": "User B Thread"},
        headers=auth_header(token_b),
    ).json()

    # User A cannot chat in Workspace B (403)
    resp_chat_ws = client.post(
        "/chat/",
        json={"question": "What is in Workspace B?", "workspace_id": ws_b["id"]},
        headers=auth_header(token_a),
    )
    assert resp_chat_ws.status_code == 403

    # User A cannot continue User B's conversation (403)
    resp_chat_conv = client.post(
        "/chat/",
        json={"question": "Hijacking User B thread", "conversation_id": conv_b["id"]},
        headers=auth_header(token_a),
    )
    assert resp_chat_conv.status_code == 403


# ============================================================
# 9. REMOVAL OF CLIENT-CONTROLLED IDENTITY
# ============================================================

def test_remove_client_controlled_identity():
    user_a, token_a = register_and_login(client, f"usera_spoof_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_spoof_{uuid.uuid4().hex[:8]}@example.com")

    ws_a = client.post("/workspaces/", json={"name": f"WS_A_{uuid.uuid4().hex[:8]}"}, headers=auth_header(token_a)).json()

    # User A attempts to create a conversation with client-controlled user_id = user_b.id
    resp_conv = client.post(
        "/conversations/",
        json={
            "workspace_id": ws_a["id"],
            "user_id": user_b["id"],  # Attempted spoof
            "title": "Anti-Spoofing Test Thread",
        },
        headers=auth_header(token_a),
    )
    assert resp_conv.status_code == 201
    # Server derived identity from JWT (current_user.id), ignoring payload.user_id
    assert resp_conv.json()["user_id"] == user_a["id"]
    assert resp_conv.json()["user_id"] != user_b["id"]

    # User A attempts to create a memory with user_id = user_b.id
    resp_mem = client.post(
        "/memories/",
        json={
            "content": "Anti-spoofing memory",
            "memory_type": "note",
            "user_id": user_b["id"],  # Attempted spoof
        },
        headers=auth_header(token_a),
    )
    assert resp_mem.status_code == 201
    assert resp_mem.json()["user_id"] == user_a["id"]
    assert resp_mem.json()["user_id"] != user_b["id"]
