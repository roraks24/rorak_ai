import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.core.database import Base, get_db
from backend.models.db import (
    User,
    Document,
    DocumentChunk,
    Conversation,
    Message,
    Memory,
    IngestionJob,
)


def test_models_inherit_from_base():
    """Verify all 7 core entities inherit from declarative Base."""
    for model_cls in [
        User,
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
        db.query(User).filter(User.email == unique_email).delete()
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
        db.commit()

        # Create document
        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="test.pdf",
            display_name="test.pdf",
            original_filename="test.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=1024,
            page_count=1,
            chunk_count=0,
            storage_key="documents/test.pdf",
            checksum_sha256=None,
            status="INDEXED",
            failure_reason=None,
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
            content="User prefers brief summaries",
            memory_type="user_preference",
        )
        db.add(mem)
        db.commit()

        # Verify all can be queried
        assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 1
        assert db.query(Message).filter(Message.conversation_id == conv.id).count() == 1
        assert db.query(IngestionJob).filter(IngestionJob.document_id == doc.id).count() == 1
        assert db.query(Memory).filter(Memory.user_id == user.id).count() == 1

        # Clean up child entities first with flush
        db.delete(mem)
        db.delete(msg)
        db.delete(chunk)
        db.delete(job)
        db.flush()

        db.delete(conv)
        db.delete(doc)
        db.flush()

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
    """Verify Document cannot reference nonexistent user_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = Document(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="orphan.pdf",
            display_name="orphan.pdf",
            original_filename="orphan.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=100,
            page_count=1,
            chunk_count=0,
            storage_key="documents/orphan.pdf",
            checksum_sha256="fake_sha256",
            status="UPLOADED",
            failure_reason=None,
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
    """Verify Conversation cannot reference nonexistent user_id."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphan = Conversation(
            id=uuid.uuid4(),
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


def test_document_model_fields():
    """Verify all required document columns exist on the Document model."""
    expected_columns = {
        "id",
        "user_id",
        "conversation_id",
        "filename",
        "display_name",
        "original_filename",
        "file_type",
        "mime_type",
        "file_size",
        "page_count",
        "chunk_count",
        "storage_key",
        "checksum_sha256",
        "status",
        "failure_reason",
        "created_at",
        "updated_at",
    }
    actual_columns = set(Document.__table__.columns.keys())
    assert expected_columns.issubset(actual_columns), f"Missing columns: {expected_columns - actual_columns}"


def test_document_model_crud_and_status():
    """Verify Document model persists fields and handles status transitions."""
    db_gen = get_db()
    db = next(db_gen)
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(id=uuid.uuid4(), email=f"doc_test_{unique_suffix}@example.com")
    db.add(user)
    db.commit()

    doc_id = uuid.uuid4()
    try:
        # 1. Create document with UPLOADED status
        doc = Document(
            id=doc_id,
            user_id=user.id,
            filename=f"doc_{unique_suffix}.pdf",
            display_name="Initial Display Name",
            original_filename="Original_Document.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=2048,
            page_count=3,
            chunk_count=0,
            storage_key=f"documents/{doc_id}/original/Original_Document.pdf",
            checksum_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            status="UPLOADED",
            failure_reason=None,
        )
        db.add(doc)
        db.commit()

        # Query and verify
        fetched = db.query(Document).filter(Document.id == doc_id).first()
        assert fetched is not None
        assert fetched.display_name == "Initial Display Name"
        assert fetched.original_filename == "Original_Document.pdf"
        assert fetched.mime_type == "application/pdf"
        assert fetched.chunk_count == 0
        assert fetched.status == "UPLOADED"
        assert fetched.failure_reason is None

        # 2. Transition status: PROCESSING -> INDEXED
        fetched.status = "PROCESSING"
        db.commit()
        assert db.query(Document).filter(Document.id == doc_id).first().status == "PROCESSING"

        fetched.status = "INDEXED"
        fetched.chunk_count = 6
        db.commit()
        indexed_doc = db.query(Document).filter(Document.id == doc_id).first()
        assert indexed_doc.status == "INDEXED"
        assert indexed_doc.chunk_count == 6

        # 3. Rename display_name
        indexed_doc.display_name = "My Research Notes"
        db.commit()
        renamed_doc = db.query(Document).filter(Document.id == doc_id).first()
        assert renamed_doc.display_name == "My Research Notes"

        # 4. Transition to FAILED with failure_reason
        renamed_doc.status = "FAILED"
        renamed_doc.failure_reason = "Corrupted PDF stream encountered"
        db.commit()
        failed_doc = db.query(Document).filter(Document.id == doc_id).first()
        assert failed_doc.status == "FAILED"
        assert failed_doc.failure_reason == "Corrupted PDF stream encountered"

        # 5. Delete document
        db.delete(failed_doc)
        db.commit()
        assert db.query(Document).filter(Document.id == doc_id).first() is None

    finally:
        db.rollback()
        # Clean up any leftover document and user
        leftover = db.query(Document).filter(Document.id == doc_id).first()
        if leftover:
            db.delete(leftover)
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        try:
            next(db_gen)
        except StopIteration:
            pass
