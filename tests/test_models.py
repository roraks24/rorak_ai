import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.core.database import Base, get_db
from backend.models.db import (
    User,
    Workspace,
    WorkspaceMember,
    Document,
    DocumentChunk,
    Conversation,
    Message,
    Memory,
    IngestionJob,
)


def test_models_inherit_from_base():
    """Verify all 9 entities inherit from declarative Base."""
    for model_cls in [
        User,
        Workspace,
        WorkspaceMember,
        Document,
        DocumentChunk,
        Conversation,
        Message,
        Memory,
        IngestionJob,
    ]:
        assert issubclass(model_cls, Base)


def test_all_metadata_tables_present():
    """Verify all required tables exist in Base metadata."""
    expected_tables = {
        "users",
        "workspaces",
        "workspace_members",
        "documents",
        "document_chunks",
        "conversations",
        "messages",
        "memories",
        "ingestion_jobs",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables)


def test_user_uniqueness_constraint():
    """Verify duplicate user email violates unique constraint."""
    db_gen = get_db()
    db = next(db_gen)
    unique_email = f"test_{uuid.uuid4()}@example.com"
    try:
        user1 = User(id=uuid.uuid4(), email=unique_email)
        db.add(user1)
        db.commit()

        user2 = User(id=uuid.uuid4(), email=unique_email)
        db.add(user2)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        # Clean up user1
        existing = db.query(User).filter(User.email == unique_email).first()
        if existing:
            db.delete(existing)
            db.commit()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_full_model_relationships():
    """Verify foreign keys and persistence across core models."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        # Create user
        user = User(id=uuid.uuid4(), email=f"rel_{uuid.uuid4()}@example.com")
        db.add(user)

        # Create workspace
        ws = Workspace(id=uuid.uuid4(), name=f"WS_{uuid.uuid4().hex[:8]}")
        db.add(ws)
        db.commit()

        # Create workspace membership
        member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
        db.add(member)

        # Create document
        doc = Document(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            filename="test.pdf",
            original_filename="test.pdf",
            file_type="pdf",
            file_size=1024,
            page_count=1,
            status="INDEXED",
        )
        db.add(doc)
        db.commit()

        # Create chunk
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content="Test chunk content",
            page_number=1,
        )
        db.add(chunk)

        # Create ingestion job
        job = IngestionJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="SUCCEEDED",
        )
        db.add(job)

        # Create conversation
        conv = Conversation(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            user_id=user.id,
            title="Test Conversation",
        )
        db.add(conv)
        db.commit()

        # Create message
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content="Hello world",
        )
        db.add(msg)

        # Create memory
        mem = Memory(
            id=uuid.uuid4(),
            user_id=user.id,
            workspace_id=ws.id,
            content="User prefers brief summaries",
            memory_type="user_preference",
        )
        db.add(mem)
        db.commit()

        # Verify all can be queried
        assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 1
        assert db.query(Message).filter(Message.conversation_id == conv.id).count() == 1
        assert db.query(IngestionJob).filter(IngestionJob.document_id == doc.id).count() == 1
        assert db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws.id).count() == 1
        assert db.query(Memory).filter(Memory.user_id == user.id).count() == 1

        # Clean up child entities first with flush
        db.delete(mem)
        db.delete(msg)
        db.delete(chunk)
        db.delete(job)
        db.flush()

        db.delete(conv)
        db.delete(doc)
        db.delete(member)
        db.flush()

        db.delete(ws)
        db.delete(user)
        db.commit()

    finally:
        db.rollback()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_document_chunk_foreign_key_violation():
    """Verify DocumentChunk cannot reference nonexistent document_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="Orphan chunk",
            page_number=1,
        )
        db.add(orphan)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_document_foreign_key_violation():
    """Verify Document cannot reference nonexistent workspace_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = Document(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            filename="orphan.pdf",
            original_filename="orphan.pdf",
            file_type="pdf",
            file_size=100,
            page_count=1,
            status="UPLOADED",
        )
        db.add(orphan)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_conversation_foreign_key_violation():
    """Verify Conversation cannot reference nonexistent workspace_id or user_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = Conversation(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            title="Orphan Conversation",
        )
        db.add(orphan)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_message_foreign_key_violation():
    """Verify Message cannot reference nonexistent conversation_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            content="Orphan Message",
        )
        db.add(orphan)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_workspace_member_duplicate_pk_violation():
    """Verify duplicate (workspace_id, user_id) violates composite primary key."""
    db_gen = get_db()
    db = next(db_gen)
    user = User(id=uuid.uuid4(), email=f"dup_{uuid.uuid4()}@example.com")
    ws = Workspace(id=uuid.uuid4(), name=f"WS_{uuid.uuid4().hex[:8]}")
    db.add(user)
    db.add(ws)
    db.commit()

    try:
        m1 = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
        db.add(m1)
        db.commit()

        # Expunge m1 from identity map so the conflict is evaluated by the database
        db.expunge(m1)
        m2 = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="member")
        db.add(m2)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws.id).delete()
        db.query(Workspace).filter(Workspace.id == ws.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        try:
            next(db_gen)
        except StopIteration:
            pass

