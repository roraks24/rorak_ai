import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from langchain_core.documents import Document as LCDocument

from backend.core.database import get_db
from backend.models.db import User, Workspace
from backend.models.schemas import DocumentStatus, IngestionStatus, MessageRole
from backend.services.document_service import DocumentService
from backend.services.conversation_service import ConversationService
from backend.services.workspace_service import WorkspaceService
from backend.services.exceptions import (
    DocumentNotFound,
    ConversationNotFound,
    WorkspaceNotFound,
    WorkspaceAlreadyExists,
    ValidationError,
    Conflict,
    IngestionError,
)


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
def sample_workspace_and_user(db_session):
    user = User(id=uuid.uuid4(), email=f"svc_user_{uuid.uuid4()}@example.com")
    ws = Workspace(id=uuid.uuid4(), name=f"Svc_WS_{uuid.uuid4().hex[:8]}")
    db_session.add(user)
    db_session.add(ws)
    db_session.commit()
    yield ws, user

    # Cleanup
    db_session.query(Workspace).filter(Workspace.id == ws.id).delete()
    db_session.query(User).filter(User.id == user.id).delete()
    db_session.commit()


# ============================================================
# WORKSPACE SERVICE TESTS
# ============================================================

def test_workspace_service_lifecycle(db_session):
    service = WorkspaceService(db_session)
    name = f"Service_WS_{uuid.uuid4().hex[:8]}"

    # Create
    ws = service.create_workspace(name=name)
    assert ws.name == name

    # Duplicate name raises WorkspaceAlreadyExists
    with pytest.raises(WorkspaceAlreadyExists):
        service.create_workspace(name=name)

    # Empty name raises ValidationError
    with pytest.raises(ValidationError):
        service.create_workspace(name="   ")

    # Name too long raises ValidationError
    with pytest.raises(ValidationError):
        service.create_workspace(name="A" * 51)

    # Get by ID
    found = service.get_workspace(ws.id)
    assert found.id == ws.id

    # Nonexistent ID raises WorkspaceNotFound
    with pytest.raises(WorkspaceNotFound):
        service.get_workspace(uuid.uuid4())

    # Get by name
    found_by_name = service.get_workspace_by_name(name)
    assert found_by_name.id == ws.id

    # List
    items, total = service.list_workspaces(page=1, page_size=10)
    assert total >= 1

    # Delete
    service.delete_workspace(ws.id)
    with pytest.raises(WorkspaceNotFound):
        service.get_workspace(ws.id)


def test_workspace_service_members(db_session, sample_workspace_and_user):
    ws, user = sample_workspace_and_user
    service = WorkspaceService(db_session)

    # Add member
    member = service.add_member(workspace_id=ws.id, user_id=user.id, role="admin")
    assert member.role == "admin"

    # Duplicate member raises Conflict
    with pytest.raises(Conflict):
        service.add_member(workspace_id=ws.id, user_id=user.id, role="member")

    # Invalid role raises ValidationError
    other_user = User(id=uuid.uuid4(), email=f"other_{uuid.uuid4()}@example.com")
    db_session.add(other_user)
    db_session.commit()

    with pytest.raises(ValidationError):
        service.add_member(workspace_id=ws.id, user_id=other_user.id, role="superhero")

    # List members
    members = service.get_members(ws.id)
    assert len(members) == 1

    # Remove member
    service.remove_member(ws.id, user.id)
    assert len(service.get_members(ws.id)) == 0

    # Removing non-member raises ValidationError
    with pytest.raises(ValidationError):
        service.remove_member(ws.id, user.id)

    db_session.delete(other_user)
    db_session.commit()


# ============================================================
# CONVERSATION SERVICE TESTS
# ============================================================

def test_conversation_service_lifecycle(db_session, sample_workspace_and_user):
    ws, user = sample_workspace_and_user
    service = ConversationService(db_session)

    # Empty title raises ValidationError
    with pytest.raises(ValidationError):
        service.create_conversation(ws.id, user.id, "")

    # Create
    conv = service.create_conversation(ws.id, user.id, "Test Thread")
    assert conv.title == "Test Thread"

    # Get
    found = service.get_conversation(conv.id)
    assert found.id == conv.id

    # Nonexistent raises ConversationNotFound
    with pytest.raises(ConversationNotFound):
        service.get_conversation(uuid.uuid4())

    # List by workspace
    convs, total = service.list_workspace_conversations(ws.id)
    assert total >= 1

    # Messages
    # Invalid role raises ValidationError
    with pytest.raises(ValidationError):
        service.create_message(conv.id, "robot", "Hello")

    # Empty content raises ValidationError
    with pytest.raises(ValidationError):
        service.create_message(conv.id, MessageRole.USER, "")

    # Valid message
    msg = service.create_message(conv.id, MessageRole.USER, "What is Rorak?")
    assert msg.role == "user"
    assert msg.content == "What is Rorak?"

    msgs, count = service.get_messages(conv.id)
    assert count == 1
    assert msgs[0].id == msg.id

    # Delete conversation
    service.delete_conversation(conv.id)
    with pytest.raises(ConversationNotFound):
        service.get_conversation(conv.id)


@patch("backend.services.conversation_service.chat_func")
def test_conversation_service_send_and_reply(mock_chat, db_session, sample_workspace_and_user):
    ws, user = sample_workspace_and_user
    service = ConversationService(db_session)
    mock_chat.return_value = "Rorak AI is a document-grounded assistant."

    conv = service.create_conversation(ws.id, user.id, "RAG Chat")
    user_msg, assistant_msg = service.send_user_message_and_reply(conv.id, "Describe Rorak")

    assert user_msg.role == "user"
    assert assistant_msg.role == "assistant"
    assert assistant_msg.content == "Rorak AI is a document-grounded assistant."

    service.delete_conversation(conv.id)


# ============================================================
# DOCUMENT SERVICE TESTS
# ============================================================

def test_document_service_crud(db_session, sample_workspace_and_user):
    ws, _ = sample_workspace_and_user
    service = DocumentService(db_session)

    # Create
    doc = service.create_document(
        workspace_id=ws.id,
        filename="manual.pdf",
        original_filename="user_manual.pdf",
        file_size=1024,
        page_count=5,
    )
    assert doc.filename == "manual.pdf"
    assert doc.status == "UPLOADED"

    # Get
    found = service.get_document(doc.id)
    assert found.id == doc.id

    # Nonexistent raises DocumentNotFound
    with pytest.raises(DocumentNotFound):
        service.get_document(uuid.uuid4())

    # List
    docs, total = service.get_workspace_documents(ws.id)
    assert total >= 1

    # Delete
    service.delete_document(doc.id)
    with pytest.raises(DocumentNotFound):
        service.get_document(doc.id)


@patch("backend.services.document_service.ingest_func")
@patch("backend.services.document_service.add_documents")
def test_document_service_ingest_workflow_success(mock_add_docs, mock_ingest, db_session, sample_workspace_and_user, tmp_path):
    ws, _ = sample_workspace_and_user
    service = DocumentService(db_session)

    # Setup mock ingest
    mock_ingest.return_value = [
        LCDocument(page_content="First page chunk", metadata={"page": 1}),
        LCDocument(page_content="Second page chunk", metadata={"page": 2}),
    ]

    dummy_file = tmp_path / "sample.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 mock")

    doc, job, chunk_count = service.ingest_document(
        workspace_id=ws.id,
        file_path=dummy_file,
        original_filename="sample.pdf",
        file_size=100,
    )

    assert doc.status == DocumentStatus.INDEXED.value
    assert job.status == IngestionStatus.SUCCEEDED.value
    assert chunk_count == 2
    mock_add_docs.assert_called_once()

    # Clean up
    service.delete_document(doc.id)


@patch("backend.services.document_service.ingest_func", return_value=[])
def test_document_service_ingest_workflow_failure_on_empty(mock_ingest, db_session, sample_workspace_and_user, tmp_path):
    ws, _ = sample_workspace_and_user
    service = DocumentService(db_session)

    dummy_file = tmp_path / "empty.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 empty")

    with pytest.raises(IngestionError):
        service.ingest_document(
            workspace_id=ws.id,
            file_path=dummy_file,
            original_filename="empty.pdf",
            file_size=50,
        )

    # Verify document in failed status
    docs, _ = service.get_workspace_documents(ws.id)
    assert len(docs) == 1
    assert docs[0].status == DocumentStatus.FAILED.value

    # Clean up
    service.delete_document(docs[0].id)


def test_service_pagination_bounds(db_session, sample_workspace_and_user):
    """Verify all service list methods validate pagination bounds."""
    ws, user = sample_workspace_and_user
    ws_svc = WorkspaceService(db_session)
    doc_svc = DocumentService(db_session)
    conv_svc = ConversationService(db_session)

    conv = conv_svc.create_conversation(ws.id, user.id, "Test Pagination")

    try:
        # WorkspaceService pagination bounds
        with pytest.raises(ValidationError):
            ws_svc.list_workspaces(page=0)
        with pytest.raises(ValidationError):
            ws_svc.list_workspaces(page_size=0)
        with pytest.raises(ValidationError):
            ws_svc.list_workspaces(page_size=101)

        # DocumentService pagination bounds
        with pytest.raises(ValidationError):
            doc_svc.get_workspace_documents(ws.id, page=0)
        with pytest.raises(ValidationError):
            doc_svc.get_workspace_documents(ws.id, page_size=0)
        with pytest.raises(ValidationError):
            doc_svc.get_workspace_documents(ws.id, page_size=101)

        # ConversationService list_workspace_conversations bounds
        with pytest.raises(ValidationError):
            conv_svc.list_workspace_conversations(ws.id, page=0)
        with pytest.raises(ValidationError):
            conv_svc.list_workspace_conversations(ws.id, page_size=0)
        with pytest.raises(ValidationError):
            conv_svc.list_workspace_conversations(ws.id, page_size=101)

        # ConversationService get_messages bounds
        with pytest.raises(ValidationError):
            conv_svc.get_messages(conv.id, page=0)
        with pytest.raises(ValidationError):
            conv_svc.get_messages(conv.id, page_size=0)
        with pytest.raises(ValidationError):
            conv_svc.get_messages(conv.id, page_size=101)
    finally:
        conv_svc.delete_conversation(conv.id)


def test_service_not_found_validations(db_session):
    """Verify services reject nonexistent parent IDs with appropriate domain exceptions."""
    ws_svc = WorkspaceService(db_session)
    doc_svc = DocumentService(db_session)
    conv_svc = ConversationService(db_session)
    fake_id = uuid.uuid4()

    # Nonexistent workspace operations
    with pytest.raises(WorkspaceNotFound):
        ws_svc.get_workspace(fake_id)

    with pytest.raises(WorkspaceNotFound):
        ws_svc.delete_workspace(fake_id)

    with pytest.raises(WorkspaceNotFound):
        ws_svc.get_members(workspace_id=fake_id)

    with pytest.raises(WorkspaceNotFound):
        ws_svc.add_member(workspace_id=fake_id, user_id=fake_id, role="admin")

    with pytest.raises(WorkspaceNotFound):
        ws_svc.remove_member(workspace_id=fake_id, user_id=fake_id)

    # Nonexistent document operations
    with pytest.raises(DocumentNotFound):
        doc_svc.get_document(fake_id)

    with pytest.raises(DocumentNotFound):
        doc_svc.delete_document(fake_id)

    # Nonexistent conversation operations
    with pytest.raises(ConversationNotFound):
        conv_svc.get_conversation(fake_id)

    with pytest.raises(ConversationNotFound):
        conv_svc.delete_conversation(fake_id)

    with pytest.raises(ConversationNotFound):
        conv_svc.create_message(conversation_id=fake_id, role=MessageRole.USER, content="hi")

    with pytest.raises(ConversationNotFound):
        conv_svc.get_messages(conversation_id=fake_id)

    with pytest.raises(ConversationNotFound):
        conv_svc.send_user_message_and_reply(fake_id, "hi")



