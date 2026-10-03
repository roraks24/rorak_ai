import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_db
from backend.models.db import (
    User,
    Document,
    DocumentChunk,
    Conversation,
    Message,
    IngestionJob,
    Memory,
)
from backend.repositories import (
    UserRepository,
    DocumentRepository,
    DocumentChunkRepository,
    ConversationRepository,
    MessageRepository,
    IngestionJobRepository,
    MemoryRepository,
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


def test_user_repository(db_session):
    repo = UserRepository(db_session)
    email = f"repo_user_{uuid.uuid4()}@example.com"
    user = User(id=uuid.uuid4(), email=email)
    created = repo.create(user)
    db_session.commit()

    assert created.id == user.id
    found = repo.get_by_id(user.id)
    assert found is not None
    assert found.email == email

    by_email = repo.get_by_email(email)
    assert by_email is not None
    assert by_email.id == user.id

    repo.delete(user)
    db_session.commit()
    assert repo.get_by_id(user.id) is None


def test_document_and_chunk_repositories(db_session):
    u_repo = UserRepository(db_session)
    d_repo = DocumentRepository(db_session)
    c_repo = DocumentChunkRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"doc_user_{uuid.uuid4().hex[:8]}@example.com"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        filename="report.pdf",
        display_name="report.pdf",
        original_filename="report.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=5000,
        page_count=2,
        chunk_count=0,
        storage_key=f"documents/{doc_id}/original/report.pdf",
        checksum_sha256="fake_sha256",
        status="UPLOADED",
        failure_reason=None,
    )
    d_repo.create(doc)
    db_session.commit()

    found_doc = d_repo.get_by_id(doc.id)
    assert found_doc is not None

    d_repo.update_status(doc.id, "INDEXED")
    db_session.commit()
    assert d_repo.get_by_id(doc.id).status == "INDEXED"

    # Paginated documents
    docs_page = d_repo.get_by_user_paginated(user.id, skip=0, limit=10)
    assert len(docs_page) == 1
    assert d_repo.count_by_user(user.id) == 1

    # Chunks
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Chunk 1",
        page_number=1,
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=1,
        content="Chunk 2",
        page_number=2,
    )
    c_repo.bulk_create([chunk1, chunk2])
    db_session.commit()

    chunks = c_repo.get_by_document(doc.id)
    assert len(chunks) == 2
    assert c_repo.count_by_document(doc.id) == 2

    # Cleanup
    for c in chunks:
        c_repo.delete(c)
    d_repo.delete(doc)
    u_repo.delete(user)
    db_session.commit()


def test_conversation_and_message_repositories(db_session):
    u_repo = UserRepository(db_session)
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"chat_{uuid.uuid4()}@example.com"))
    db_session.commit()

    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Repo Chat",
    )
    conv_repo.create(conv)
    db_session.commit()

    assert conv_repo.get_by_id(conv.id) is not None

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role="user",
        content="Testing repo message",
    )
    msg_repo.create(msg)
    db_session.commit()

    msgs = msg_repo.get_by_conversation(conv.id)
    assert len(msgs) == 1
    assert msgs[0].content == "Testing repo message"

    # Cleanup
    msg_repo.delete(msg)
    conv_repo.delete(conv)
    u_repo.delete(user)
    db_session.commit()


def test_ingestion_job_repository(db_session):
    u_repo = UserRepository(db_session)
    d_repo = DocumentRepository(db_session)
    j_repo = IngestionJobRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"job_{uuid.uuid4()}@example.com"))
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        filename="job_doc.pdf",
        display_name="job_doc.pdf",
        original_filename="job_doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        page_count=1,
        chunk_count=0,
        storage_key=f"documents/{doc_id}/original/job_doc.pdf",
        checksum_sha256="fake_sha",
        status="UPLOADED",
        failure_reason=None,
    )
    d_repo.create(doc)
    db_session.commit()

    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=doc.id,
        status="PENDING",
    )
    j_repo.create(job)
    db_session.commit()

    assert j_repo.get_by_id(job.id) is not None
    assert j_repo.get_by_document(doc.id) is not None

    j_repo.update_status(job.id, "PROCESSING")
    db_session.commit()
    assert j_repo.get_by_id(job.id).status == "PROCESSING"

    j_repo.delete(job)
    d_repo.delete(doc)
    u_repo.delete(user)
    db_session.commit()


def test_user_isolation_documents(db_session):
    """Verify documents for user A cannot be retrieved by user B."""
    u_repo = UserRepository(db_session)
    d_repo = DocumentRepository(db_session)

    u1 = u_repo.create(User(id=uuid.uuid4(), email=f"u1_{uuid.uuid4().hex[:6]}@example.com"))
    u2 = u_repo.create(User(id=uuid.uuid4(), email=f"u2_{uuid.uuid4().hex[:6]}@example.com"))
    db_session.commit()

    d1 = d_repo.create(Document(
        id=uuid.uuid4(),
        user_id=u1.id,
        filename="doc_u1.pdf",
        display_name="doc_u1.pdf",
        original_filename="doc_u1.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        page_count=1,
        chunk_count=0,
        storage_key="test",
        checksum_sha256="sha",
        status="INDEXED",
        failure_reason=None,
    ))
    db_session.commit()

    docs_u1 = d_repo.get_by_user_paginated(u1.id)
    assert len(docs_u1) == 1
    assert docs_u1[0].id == d1.id

    docs_u2 = d_repo.get_by_user_paginated(u2.id)
    assert len(docs_u2) == 0

    d_repo.delete(d1)
    u_repo.delete(u1)
    u_repo.delete(u2)
    db_session.commit()


def test_user_isolation_conversations(db_session):
    """Verify conversations for user A cannot be retrieved by user B."""
    u_repo = UserRepository(db_session)
    c_repo = ConversationRepository(db_session)

    u1 = u_repo.create(User(id=uuid.uuid4(), email=f"u1_{uuid.uuid4().hex[:6]}@example.com"))
    u2 = u_repo.create(User(id=uuid.uuid4(), email=f"u2_{uuid.uuid4().hex[:6]}@example.com"))
    db_session.commit()

    conv1 = c_repo.create(Conversation(
        id=uuid.uuid4(),
        user_id=u1.id,
        title="U1 Thread",
    ))
    db_session.commit()

    convs_u1 = c_repo.get_by_user_paginated(u1.id)
    assert len(convs_u1) == 1

    convs_u2 = c_repo.get_by_user_paginated(u2.id)
    assert len(convs_u2) == 0

    c_repo.delete(conv1)
    u_repo.delete(u1)
    u_repo.delete(u2)
    db_session.commit()


def test_repositories_nonexistent_lookups(db_session):
    """Verify querying non-existent entities returns None."""
    random_id = uuid.uuid4()
    assert UserRepository(db_session).get_by_id(random_id) is None
    assert DocumentRepository(db_session).get_by_id(random_id) is None
    assert ConversationRepository(db_session).get_by_id(random_id) is None
    assert MessageRepository(db_session).get_by_id(random_id) is None
    assert IngestionJobRepository(db_session).get_by_id(random_id) is None
    assert MemoryRepository(db_session).get_by_id(random_id) is None


def test_memory_repository(db_session):
    """Verify MemoryRepository CRUD and scoped operations."""
    u_repo = UserRepository(db_session)
    mem_repo = MemoryRepository(db_session)

    user1 = u_repo.create(User(id=uuid.uuid4(), email=f"mem_u1_{uuid.uuid4().hex[:6]}@example.com"))
    user2 = u_repo.create(User(id=uuid.uuid4(), email=f"mem_u2_{uuid.uuid4().hex[:6]}@example.com"))
    db_session.commit()

    try:
        mem1 = mem_repo.create(Memory(
            id=uuid.uuid4(),
            user_id=user1.id,
            content="User prefers Python over JavaScript",
            memory_type="preference",
        ))
        mem2 = mem_repo.create(Memory(
            id=uuid.uuid4(),
            user_id=user1.id,
            content="User is a senior ML engineer",
            memory_type="profile",
        ))
        mem3 = mem_repo.create(Memory(
            id=uuid.uuid4(),
            user_id=user2.id,
            content="User 2 prefers Rust",
            memory_type="preference",
        ))
        db_session.commit()

        # Get by id
        found = mem_repo.get_by_id(mem1.id)
        assert found is not None
        assert found.content == "User prefers Python over JavaScript"

        # Get by user
        user1_mems = mem_repo.get_by_user(user1.id)
        assert len(user1_mems) == 2

        # Scoped memories: isolation check
        scoped_u1 = mem_repo.get_scoped_memories(user_id=user1.id)
        assert len(scoped_u1) == 2
        scoped_ids = [m.id for m in scoped_u1]
        assert mem3.id not in scoped_ids  # Never retrieve another user's memory

        # Counts
        assert mem_repo.count_by_user(user1.id) == 2
        assert mem_repo.count_by_user(user2.id) == 1

        # Update
        updated = mem_repo.update(mem1, content="Updated: User prefers Python 3.12", memory_type="tech_preference")
        assert updated.content == "Updated: User prefers Python 3.12"
        assert updated.memory_type == "tech_preference"
        db_session.commit()

        # Delete
        mem_repo.delete(mem1)
        mem_repo.delete(mem2)
        mem_repo.delete(mem3)
        db_session.commit()

        assert mem_repo.get_by_id(mem1.id) is None

    finally:
        u_repo.delete(user1)
        u_repo.delete(user2)
        db_session.commit()
