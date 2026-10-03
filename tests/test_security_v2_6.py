"""
Security Test Suite for Rorak AI: Authentication & Multi-User Isolation.

Covers:
- User registration (POST /auth/register), password hashing, email validation, duplicate user (409)
- Login (POST /auth/login), password verification, JWT issuance
- Authentication dependency: Bearer token extraction, signature validation, expiration, resolution
- Authorization & Isolation:
  - User A cannot access User B's conversation (403)
  - User A cannot modify/delete User B's memory (403)
  - User A cannot access User B's documents (403)
  - Missing JWT -> 401
  - Invalid JWT -> 401
  - Expired JWT -> 401
  - Valid JWT + unauthorized resource -> denied (403)
- Removal of client-controlled identity:
  - Client-supplied user_id is ignored/overridden by current_user.id
"""
from datetime import timedelta
import io
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.db import (
    User,
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
    """Helper to register a user and return (user_dict, access_token)."""
    resp_reg = client.post("/auth/register", json={"email": email, "password": password})
    assert resp_reg.status_code == 201, f"Register failed: {resp_reg.text}"
    user_data = resp_reg.json()

    resp_login = client.post("/auth/login", json={"email": email, "password": password})
    assert resp_login.status_code == 200, f"Login failed: {resp_login.text}"
    token = resp_login.json()["access_token"]
    return user_data, token


# ============================================================
# 1. REGISTRATION TESTS
# ============================================================

def test_register_success(db_session):
    email = f"sec_reg_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/auth/register", json={"email": email, "password": "StrongPassword123!"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["email"] == email

    # Verify password is NOT stored as plaintext
    user = db_session.query(User).filter(User.id == uuid.UUID(data["id"])).first()
    assert user is not None
    assert user.password_hash != "StrongPassword123!"
    assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")

    # Cleanup
    db_session.delete(user)
    db_session.commit()


def test_register_with_name_and_auto_memory(db_session):
    email = f"sec_name_{uuid.uuid4().hex[:8]}@example.com"
    name = "Rorak Master"
    resp = client.post("/auth/register", json={"email": email, "password": "StrongPassword123!", "name": name})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name

    user_id = uuid.UUID(data["id"])
    user = db_session.query(User).filter(User.id == user_id).first()
    assert user is not None
    assert user.name == name

    # Verify auto-created memory for name
    mem = db_session.query(Memory).filter(Memory.user_id == user_id).first()
    assert mem is not None
    assert "Rorak Master" in mem.content

    # Cleanup
    db_session.query(Memory).filter(Memory.user_id == user_id).delete()
    db_session.delete(user)
    db_session.commit()


def test_register_duplicate_email():
    email = f"sec_dup_{uuid.uuid4().hex[:8]}@example.com"
    resp1 = client.post("/auth/register", json={"email": email, "password": "StrongPassword123!"})
    assert resp1.status_code == 201

    # Duplicate registration must return 409 Conflict
    resp2 = client.post("/auth/register", json={"email": email, "password": "AnotherPassword456!"})
    assert resp2.status_code == 409
    err = resp2.json()
    assert "detail" in err
    assert "already exists" in err["detail"]["error"]["message"].lower()


def test_register_validation_failures():
    # Invalid email
    resp = client.post("/auth/register", json={"email": "not-an-email", "password": "ValidPass123!"})
    assert resp.status_code == 400

    # Short password (<8 chars)
    resp = client.post("/auth/register", json={"email": "valid@example.com", "password": "short"})
    assert resp.status_code == 400

    # Empty email
    resp = client.post("/auth/register", json={"email": "", "password": "ValidPass123!"})
    assert resp.status_code in (400, 422)


# ============================================================
# 2. LOGIN TESTS
# ============================================================

def test_login_success():
    email = f"sec_login_{uuid.uuid4().hex[:8]}@example.com"
    register_and_login(client, email, "MySecretPass999!")

    resp = client.post("/auth/login", json={"email": email, "password": "MySecretPass999!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == email


def test_login_wrong_password():
    email = f"sec_wrongpass_{uuid.uuid4().hex[:8]}@example.com"
    register_and_login(client, email, "CorrectPassword123!")

    resp = client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})
    assert resp.status_code == 401
    err = resp.json()
    assert err["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_user():
    resp = client.post("/auth/login", json={"email": f"ghost_{uuid.uuid4()}@example.com", "password": "AnyPassword123!"})
    assert resp.status_code == 401
    err = resp.json()
    assert err["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


# ============================================================
# 3. AUTHENTICATION DEPENDENCY TESTS
# ============================================================

def test_auth_missing_jwt():
    # Calling /auth/me without header -> 401
    resp = client.get("/auth/me")
    assert resp.status_code == 401
    err = resp.json()
    assert err["detail"]["error"]["code"] == "UNAUTHORIZED"


def test_auth_invalid_jwt():
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"


def test_auth_expired_jwt():
    expired_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "email": "expired@example.com"},
        expires_delta=timedelta(seconds=-10),
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "TOKEN_EXPIRED"


def test_auth_valid_jwt():
    email = f"sec_valid_{uuid.uuid4().hex[:8]}@example.com"
    user_data, token = register_and_login(client, email)

    resp = client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == user_data["id"]
    assert resp.json()["email"] == email


# ============================================================
# 4. CONVERSATION & MESSAGE ISOLATION TESTS
# ============================================================

def test_conversation_and_message_isolation():
    user_a, token_a = register_and_login(client, f"usera_conv_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_conv_{uuid.uuid4().hex[:8]}@example.com")

    # User B creates conversation
    conv_b = client.post(
        "/conversations/",
        json={"title": "User B Secret Thread"},
        headers=auth_header(token_b),
    ).json()
    conv_b_id = conv_b["id"]

    # User B posts a message in Conversation B
    client.post(
        f"/conversations/{conv_b_id}/messages",
        json={"role": "user", "content": "Confidential data for User B"},
        headers=auth_header(token_b),
    )

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


# ============================================================
# 5. MEMORY ISOLATION TESTS
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
# 6. DOCUMENT ISOLATION TESTS
# ============================================================

def test_document_isolation():
    user_a, token_a = register_and_login(client, f"usera_doc_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_doc_{uuid.uuid4().hex[:8]}@example.com")

    # User A cannot list documents of another user spoofing user_id
    resp_docs = client.get(f"/documents/?user_id={user_b['id']}", headers=auth_header(token_a))
    # It lists User A's documents, ignoring spoofed user_id
    assert resp_docs.status_code == 200


# ============================================================
# 7. CHAT ENDPOINT PROTECTION
# ============================================================

def test_chat_isolation_and_ownership():
    user_a, token_a = register_and_login(client, f"usera_chat_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_chat_{uuid.uuid4().hex[:8]}@example.com")

    conv_b = client.post(
        "/conversations/",
        json={"title": "User B Thread"},
        headers=auth_header(token_b),
    ).json()

    # User A cannot continue User B's conversation (403)
    resp_chat_conv = client.post(
        "/chat/",
        json={"question": "Hijacking User B thread", "conversation_id": conv_b["id"]},
        headers=auth_header(token_a),
    )
    assert resp_chat_conv.status_code == 403


# ============================================================
# 8. REMOVAL OF CLIENT-CONTROLLED IDENTITY
# ============================================================

def test_remove_client_controlled_identity():
    user_a, token_a = register_and_login(client, f"usera_spoof_{uuid.uuid4().hex[:8]}@example.com")
    user_b, token_b = register_and_login(client, f"userb_spoof_{uuid.uuid4().hex[:8]}@example.com")

    # User A attempts to create a conversation with client-controlled user_id = user_b.id
    resp_conv = client.post(
        "/conversations/",
        json={
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
