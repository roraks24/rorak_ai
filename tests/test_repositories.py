import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_db
from backend.models.db import (
    User,
    Workspace,
    WorkspaceMember,
    Document,
    DocumentChunk,
    Conversation,
    Message,
    IngestionJob,
)
from backend.repositories import (
    UserRepository,
    WorkspaceRepository,
    WorkspaceMemberRepository,
    DocumentRepository,
    DocumentChunkRepository,
    ConversationRepository,
    MessageRepository,
    IngestionJobRepository,
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


def test_workspace_repository(db_session):
    repo = WorkspaceRepository(db_session)
    name = f"Repo_WS_{uuid.uuid4().hex[:8]}"
    ws = Workspace(id=uuid.uuid4(), name=name)
    repo.create(ws)
    db_session.commit()

    found = repo.get_by_id(ws.id)
    assert found is not None
    assert found.name == name

    by_name = repo.get_by_name(name)
    assert by_name is not None
    assert by_name.id == ws.id

    all_ws = repo.list_all(skip=0, limit=10)
    assert len(all_ws) >= 1
    assert repo.count() >= 1

    repo.delete(ws)
    db_session.commit()
    assert repo.get_by_id(ws.id) is None


def test_workspace_member_repository(db_session):
    u_repo = UserRepository(db_session)
    w_repo = WorkspaceRepository(db_session)
    m_repo = WorkspaceMemberRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"m_{uuid.uuid4()}@example.com"))
    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"M_WS_{uuid.uuid4().hex[:8]}"))
    db_session.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="admin")
    m_repo.create(member)
    db_session.commit()

    found = m_repo.get(ws.id, user.id)
    assert found is not None
    assert found.role == "admin"

    by_ws = m_repo.get_by_workspace(ws.id)
    assert len(by_ws) == 1

    by_user = m_repo.get_by_user(user.id)
    assert len(by_user) >= 1

    m_repo.delete(member)
    w_repo.delete(ws)
    u_repo.delete(user)
    db_session.commit()


def test_document_and_chunk_repositories(db_session):
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)
    c_repo = DocumentChunkRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"Doc_WS_{uuid.uuid4().hex[:8]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        workspace_id=ws.id,
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
    docs_page = d_repo.get_by_workspace_paginated(ws.id, skip=0, limit=10)
    assert len(docs_page) == 1
    assert d_repo.count_by_workspace(ws.id) == 1

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
    w_repo.delete(ws)
    db_session.commit()


def test_conversation_and_message_repositories(db_session):
    u_repo = UserRepository(db_session)
    w_repo = WorkspaceRepository(db_session)
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"chat_{uuid.uuid4()}@example.com"))
    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"Chat_WS_{uuid.uuid4().hex[:8]}"))
    db_session.commit()

    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        user_id=user.id,
        title="Chat Thread",
    )
    conv_repo.create(conv)
    db_session.commit()

    assert conv_repo.get_by_id(conv.id) is not None
    assert conv_repo.count_by_workspace(ws.id) == 1
    assert conv_repo.count_by_user(user.id) == 1

    # Messages
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role="user",
        content="Hello repository test",
    )
    msg_repo.create(msg)
    db_session.commit()

    msgs = msg_repo.get_by_conversation(conv.id)
    assert len(msgs) == 1
    assert msgs[0].content == "Hello repository test"
    assert msg_repo.count_by_conversation(conv.id) == 1

    # Cleanup
    msg_repo.delete(msg)
    conv_repo.delete(conv)
    w_repo.delete(ws)
    u_repo.delete(user)
    db_session.commit()


def test_ingestion_job_repository(db_session):
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)
    job_repo = IngestionJobRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"Job_WS_{uuid.uuid4().hex[:8]}"))
    doc_id = uuid.uuid4()
    doc = d_repo.create(
        Document(
            id=doc_id,
            workspace_id=ws.id,
            filename="j.pdf",
            display_name="j.pdf",
            original_filename="j.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=10,
            page_count=1,
            chunk_count=0,
            storage_key=f"documents/{doc_id}/original/j.pdf",
            checksum_sha256="fake_sha256",
            status="PROCESSING",
            failure_reason=None,
        )
    )
    db_session.commit()

    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=doc.id,
        status="RUNNING",
    )
    job_repo.create(job)
    db_session.commit()

    assert job_repo.get_by_id(job.id) is not None
    latest = job_repo.get_latest_by_document(doc.id)
    assert latest is not None
    assert latest.id == job.id

    updated = job_repo.update_status(job.id, "SUCCEEDED", completed=True)
    db_session.commit()
    assert updated.status == "SUCCEEDED"
    assert updated.completed_at is not None

    job_repo.delete(job)
    d_repo.delete(doc)
    w_repo.delete(ws)
    db_session.commit()


def test_workspace_isolation_documents(db_session):
    """Verify querying documents in workspace A does not return documents from workspace B."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)

    ws_a = w_repo.create(Workspace(id=uuid.uuid4(), name=f"WS_A_{uuid.uuid4().hex[:6]}"))
    ws_b = w_repo.create(Workspace(id=uuid.uuid4(), name=f"WS_B_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    try:
        # Create 2 docs in WS_A, 1 in WS_B
        doc_a1_id = uuid.uuid4()
        doc_a2_id = uuid.uuid4()
        doc_b1_id = uuid.uuid4()
        doc_a1 = d_repo.create(Document(
            id=doc_a1_id, workspace_id=ws_a.id, filename="a1.pdf", original_filename="a1.pdf",
            display_name="a1.pdf", file_type="pdf", mime_type="application/pdf", file_size=100,
            page_count=1, chunk_count=1, storage_key=f"documents/{doc_a1_id}/original/a1.pdf",
            checksum_sha256="fake_sha_a1", status="INDEXED", failure_reason=None,
        ))
        doc_a2 = d_repo.create(Document(
            id=doc_a2_id, workspace_id=ws_a.id, filename="a2.pdf", original_filename="a2.pdf",
            display_name="a2.pdf", file_type="pdf", mime_type="application/pdf", file_size=200,
            page_count=2, chunk_count=2, storage_key=f"documents/{doc_a2_id}/original/a2.pdf",
            checksum_sha256="fake_sha_a2", status="INDEXED", failure_reason=None,
        ))
        doc_b1 = d_repo.create(Document(
            id=doc_b1_id, workspace_id=ws_b.id, filename="b1.pdf", original_filename="b1.pdf",
            display_name="b1.pdf", file_type="pdf", mime_type="application/pdf", file_size=300,
            page_count=3, chunk_count=3, storage_key=f"documents/{doc_b1_id}/original/b1.pdf",
            checksum_sha256="fake_sha_b1", status="INDEXED", failure_reason=None,
        ))
        db_session.commit()

        # Query A
        docs_a = d_repo.get_by_workspace_paginated(ws_a.id, skip=0, limit=10)
        docs_a_ids = {d.id for d in docs_a}
        assert len(docs_a) == 2
        assert doc_a1.id in docs_a_ids
        assert doc_a2.id in docs_a_ids
        assert doc_b1.id not in docs_a_ids
        assert d_repo.count_by_workspace(ws_a.id) == 2

        # Query B
        docs_b = d_repo.get_by_workspace_paginated(ws_b.id, skip=0, limit=10)
        docs_b_ids = {d.id for d in docs_b}
        assert len(docs_b) == 1
        assert doc_b1.id in docs_b_ids
        assert doc_a1.id not in docs_b_ids
        assert doc_a2.id not in docs_b_ids
        assert d_repo.count_by_workspace(ws_b.id) == 1

        # Clean up
        d_repo.delete(doc_a1)
        d_repo.delete(doc_a2)
        d_repo.delete(doc_b1)
        db_session.commit()
    finally:
        w_repo.delete(ws_a)
        w_repo.delete(ws_b)
        db_session.commit()


def test_workspace_isolation_conversations(db_session):
    """Verify querying conversations in workspace A does not return conversations from workspace B."""
    u_repo = UserRepository(db_session)
    w_repo = WorkspaceRepository(db_session)
    c_repo = ConversationRepository(db_session)

    user = u_repo.create(User(id=uuid.uuid4(), email=f"iso_user_{uuid.uuid4()}@example.com"))
    ws_a = w_repo.create(Workspace(id=uuid.uuid4(), name=f"WS_CA_{uuid.uuid4().hex[:6]}"))
    ws_b = w_repo.create(Workspace(id=uuid.uuid4(), name=f"WS_CB_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    try:
        conv_a = c_repo.create(Conversation(id=uuid.uuid4(), workspace_id=ws_a.id, user_id=user.id, title="Conv A"))
        conv_b = c_repo.create(Conversation(id=uuid.uuid4(), workspace_id=ws_b.id, user_id=user.id, title="Conv B"))
        db_session.commit()

        # Query A
        convs_a = c_repo.get_by_workspace_paginated(ws_a.id, skip=0, limit=10)
        assert len(convs_a) == 1
        assert convs_a[0].id == conv_a.id
        assert c_repo.count_by_workspace(ws_a.id) == 1

        # Query B
        convs_b = c_repo.get_by_workspace_paginated(ws_b.id, skip=0, limit=10)
        assert len(convs_b) == 1
        assert convs_b[0].id == conv_b.id
        assert c_repo.count_by_workspace(ws_b.id) == 1

        # Clean up
        c_repo.delete(conv_a)
        c_repo.delete(conv_b)
        db_session.commit()
    finally:
        w_repo.delete(ws_a)
        w_repo.delete(ws_b)
        u_repo.delete(user)
        db_session.commit()


def test_repositories_nonexistent_lookups(db_session):
    """Verify get_by_id returns None for all repositories when ID does not exist."""
    fake_id = uuid.uuid4()
    assert UserRepository(db_session).get_by_id(fake_id) is None
    assert WorkspaceRepository(db_session).get_by_id(fake_id) is None
    assert DocumentRepository(db_session).get_by_id(fake_id) is None
    assert DocumentChunkRepository(db_session).get_by_id(fake_id) is None
    assert ConversationRepository(db_session).get_by_id(fake_id) is None
    assert MessageRepository(db_session).get_by_id(fake_id) is None
    assert IngestionJobRepository(db_session).get_by_id(fake_id) is None


def test_foreign_key_delete_protection(db_session):
    """Verify deleting a workspace with dependent documents violates FK constraint unless children are removed."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"FK_Del_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = d_repo.create(Document(
        id=doc_id, workspace_id=ws.id, filename="fk.pdf", original_filename="fk.pdf",
        display_name="fk.pdf", file_type="pdf", mime_type="application/pdf", file_size=50,
        page_count=1, chunk_count=0, storage_key=f"documents/{doc_id}/original/fk.pdf",
        checksum_sha256="fake_sha_fk", status="INDEXED", failure_reason=None,
    ))
    db_session.commit()

    try:
        # Attempting to delete workspace while doc exists should fail on flush
        with pytest.raises(IntegrityError):
            w_repo.delete(ws)
        db_session.rollback()

        # Delete child doc first, then workspace succeeds
        d_repo.delete(doc)
        w_repo.delete(ws)
        db_session.commit()
        assert w_repo.get_by_id(ws.id) is None
    finally:
        db_session.rollback()


# ============================================================
# V2.2 DOCUMENT REPOSITORY TESTS
# ============================================================

def test_document_repository_v2_2_create(db_session):
    """Verify DocumentRepository creates and retrieves a document with all V2.2 fields."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"V22_Create_WS_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        workspace_id=ws.id,
        filename="research.pdf",
        display_name="Research Paper V1",
        original_filename="research_final.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=8192,
        page_count=5,
        chunk_count=12,
        storage_key=f"documents/{doc_id}/original/research_final.pdf",
        checksum_sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        status="INDEXED",
        failure_reason=None,
    )

    try:
        created = d_repo.create(doc)
        db_session.commit()

        assert created.id == doc_id
        found = d_repo.get_by_id(doc_id)
        assert found is not None
        assert found.display_name == "Research Paper V1"
        assert found.original_filename == "research_final.pdf"
        assert found.mime_type == "application/pdf"
        assert found.chunk_count == 12
        assert found.storage_key == f"documents/{doc_id}/original/research_final.pdf"
        assert found.status == "INDEXED"
    finally:
        d_repo.delete(doc)
        w_repo.delete(ws)
        db_session.commit()


def test_document_repository_v2_2_pagination_and_ordering(db_session):
    """Verify document pagination, total count, and newest-first ordering."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"V22_Page_WS_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    docs = []
    try:
        for i in range(5):
            d_id = uuid.uuid4()
            d = d_repo.create(Document(
                id=d_id,
                workspace_id=ws.id,
                filename=f"doc_{i}.pdf",
                display_name=f"Document {i}",
                original_filename=f"doc_{i}.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                file_size=1024 * (i + 1),
                page_count=i + 1,
                chunk_count=(i + 1) * 2,
                storage_key=f"documents/{d_id}/original/doc_{i}.pdf",
                checksum_sha256=f"{i:064x}",
                status="INDEXED",
                failure_reason=None,
            ))
            docs.append(d)
        db_session.commit()

        # Count
        assert d_repo.count_by_workspace(ws.id) == 5

        # Page 1 (size 2)
        page1 = d_repo.get_by_workspace_paginated(ws.id, skip=0, limit=2)
        assert len(page1) == 2

        # Page 2 (size 2)
        page2 = d_repo.get_by_workspace_paginated(ws.id, skip=2, limit=2)
        assert len(page2) == 2

        # Page 3 (size 2) -> remainder 1
        page3 = d_repo.get_by_workspace_paginated(ws.id, skip=4, limit=2)
        assert len(page3) == 1

        # Ordering: newest first (created_at desc)
        all_paginated = d_repo.get_by_workspace_paginated(ws.id, skip=0, limit=10)
        assert len(all_paginated) == 5
        for j in range(len(all_paginated) - 1):
            assert all_paginated[j].created_at >= all_paginated[j + 1].created_at

    finally:
        for d in docs:
            d_repo.delete(d)
        w_repo.delete(ws)
        db_session.commit()


def test_document_repository_v2_2_rename_and_update(db_session):
    """Verify document rename/update persistence."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"V22_Ren_WS_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = d_repo.create(Document(
        id=doc_id,
        workspace_id=ws.id,
        filename="old_name.pdf",
        display_name="Old Display Name",
        original_filename="old_name.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        page_count=2,
        chunk_count=4,
        storage_key=f"documents/{doc_id}/original/old_name.pdf",
        checksum_sha256="fake_sha_ren",
        status="INDEXED",
        failure_reason=None,
    ))
    db_session.commit()

    try:
        # Renaming updates display_name
        doc.display_name = "My Research Notes"
        if hasattr(d_repo, "update"):
            d_repo.update(doc)
        else:
            db_session.flush()
        db_session.commit()

        updated = d_repo.get_by_id(doc_id)
        assert updated.display_name == "My Research Notes"
    finally:
        d_repo.delete(doc)
        w_repo.delete(ws)
        db_session.commit()


def test_document_chunk_cleanup_v2_2(db_session):
    """Verify document chunk cleanup removes all chunks for a document."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)
    c_repo = DocumentChunkRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"V22_Chunk_WS_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = d_repo.create(Document(
        id=doc_id,
        workspace_id=ws.id,
        filename="chunked.pdf",
        display_name="Chunked Doc",
        original_filename="chunked.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=4096,
        page_count=2,
        chunk_count=3,
        storage_key=f"documents/{doc_id}/original/chunked.pdf",
        checksum_sha256="fake_sha_chunks",
        status="INDEXED",
        failure_reason=None,
    ))
    db_session.commit()

    try:
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                chunk_index=i,
                content=f"Content for chunk {i}",
                page_number=1,
            )
            for i in range(3)
        ]
        c_repo.bulk_create(chunks)
        db_session.commit()

        assert c_repo.count_by_document(doc_id) == 3

        # Cleanup chunks
        for chunk in c_repo.get_by_document(doc_id):
            c_repo.delete(chunk)
        db_session.commit()

        assert c_repo.count_by_document(doc_id) == 0
        assert len(c_repo.get_by_document(doc_id)) == 0

    finally:
        d_repo.delete(doc)
        w_repo.delete(ws)
        db_session.commit()


def test_ingestion_job_cleanup_v2_2(db_session):
    """Verify ingestion job cleanup removes all jobs for a document."""
    w_repo = WorkspaceRepository(db_session)
    d_repo = DocumentRepository(db_session)
    j_repo = IngestionJobRepository(db_session)

    ws = w_repo.create(Workspace(id=uuid.uuid4(), name=f"V22_Job_WS_{uuid.uuid4().hex[:6]}"))
    db_session.commit()

    doc_id = uuid.uuid4()
    doc = d_repo.create(Document(
        id=doc_id,
        workspace_id=ws.id,
        filename="jobbed.pdf",
        display_name="Jobbed Doc",
        original_filename="jobbed.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        page_count=1,
        chunk_count=0,
        storage_key=f"documents/{doc_id}/original/jobbed.pdf",
        checksum_sha256="fake_sha_jobs",
        status="PROCESSING",
        failure_reason=None,
    ))
    db_session.commit()

    try:
        job = IngestionJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            status="RUNNING",
        )
        j_repo.create(job)
        db_session.commit()

        assert j_repo.get_latest_by_document(doc_id) is not None

        # Cleanup job
        j_repo.delete(job)
        db_session.commit()

        assert j_repo.get_latest_by_document(doc_id) is None
    finally:
        d_repo.delete(doc)
        w_repo.delete(ws)
        db_session.commit()
