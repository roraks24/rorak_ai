from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError as PydanticValidationError

from backend.models.schemas import (
    DocumentStatus,
    IngestionStatus,
    MessageRole,
    Pagination,
    PaginationParams,
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse,
    HealthResponse,
    ReadyResponse,
    WorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceMemberResponse,
    DocumentResponse,
    DocumentListResponse,
    ConversationResponse,
    ConversationListResponse,
    MessageResponse,
    MessageListResponse,
    IngestionJobResponse,
    CreateWorkspaceRequest,
    CreateConversationRequest,
    CreateMessageRequest,
    AddMemberRequest,
    RenameDocumentRequest,
)


def test_enum_values():
    """Verify all enum values match specification."""
    assert DocumentStatus.UPLOADED.value == "UPLOADED"
    assert DocumentStatus.PROCESSING.value == "PROCESSING"
    assert DocumentStatus.INDEXED.value == "INDEXED"
    assert DocumentStatus.FAILED.value == "FAILED"

    assert IngestionStatus.QUEUED.value == "QUEUED"
    assert IngestionStatus.RUNNING.value == "RUNNING"
    assert IngestionStatus.SUCCEEDED.value == "SUCCEEDED"
    assert IngestionStatus.FAILED.value == "FAILED"

    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.SYSTEM.value == "system"


def test_pagination_bounds():
    """Verify pagination validation bounds."""
    # Valid
    p = Pagination(page=1, page_size=20, total=100, total_pages=5)
    assert p.page == 1
    assert p.page_size == 20

    # Invalid page < 1
    with pytest.raises(PydanticValidationError):
        Pagination(page=0, page_size=20)

    # Invalid page_size < 1
    with pytest.raises(PydanticValidationError):
        Pagination(page=1, page_size=0)

    # Invalid page_size > 100
    with pytest.raises(PydanticValidationError):
        Pagination(page=1, page_size=101)

    # Invalid total < 0
    with pytest.raises(PydanticValidationError):
        Pagination(page=1, page_size=20, total=-1)


def test_pagination_params():
    """Verify pagination query params schema."""
    params = PaginationParams()
    assert params.page == 1
    assert params.page_size == 20


def test_ready_response_distinguishes_documents_and_chunks():
    """Verify ReadyResponse contract separates documents_indexed from chunks_indexed and includes database_connected."""
    ready = ReadyResponse(
        status="ready",
        models_loaded=True,
        vector_store_initialized=True,
        database_connected=True,
        documents_indexed=5,
        chunks_indexed=42,
    )
    assert ready.documents_indexed == 5
    assert ready.chunks_indexed == 42
    assert ready.database_connected is True


def test_health_response_defaults():
    """Verify HealthResponse has status and version."""
    health = HealthResponse(status="healthy")
    assert health.status == "healthy"
    assert health.version == "2.1.0"


def test_workspace_schemas():
    """Verify workspace request and response contracts."""
    req = CreateWorkspaceRequest(name="Alpha Workspace")
    assert req.name == "Alpha Workspace"

    now = datetime.now(timezone.utc)
    ws_id = uuid.uuid4()
    resp = WorkspaceResponse(
        id=ws_id,
        name="Alpha Workspace",
        created_at=now,
        updated_at=now,
    )
    assert resp.id == ws_id
    assert resp.name == "Alpha Workspace"

    list_resp = WorkspaceListResponse(
        workspaces=[resp],
        pagination=Pagination(page=1, page_size=20, total=1, total_pages=1),
    )
    assert len(list_resp.workspaces) == 1


def test_document_schemas():
    """Verify document response and list contracts."""
    now = datetime.now(timezone.utc)
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    doc = DocumentResponse(
        id=doc_id,
        workspace_id=ws_id,
        filename="report.pdf",
        original_filename="Q3_Report.pdf",
        display_name="Q3 Report",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        page_count=3,
        chunk_count=5,
        status=DocumentStatus.INDEXED,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    assert doc.status == DocumentStatus.INDEXED
    assert doc.display_name == "Q3 Report"
    assert doc.original_filename == "Q3_Report.pdf"
    assert doc.mime_type == "application/pdf"
    assert doc.chunk_count == 5
    assert doc.failure_reason is None

    doc_list = DocumentListResponse(
        documents=[doc],
        pagination=Pagination(page=1, page_size=20, total=1, total_pages=1),
    )
    assert len(doc_list.documents) == 1


def test_conversation_and_message_schemas():
    """Verify conversation and message schemas."""
    now = datetime.now(timezone.utc)
    conv_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    conv = ConversationResponse(
        id=conv_id,
        workspace_id=ws_id,
        user_id=user_id,
        title="Project Discussion",
        created_at=now,
        updated_at=now,
    )
    assert conv.title == "Project Discussion"

    msg_id = uuid.uuid4()
    msg = MessageResponse(
        id=msg_id,
        conversation_id=conv_id,
        role=MessageRole.USER,
        content="What is the progress?",
        created_at=now,
    )
    assert msg.role == MessageRole.USER
    assert msg.content == "What is the progress?"


def test_ingestion_job_schema():
    """Verify IngestionJobResponse fields and status enum."""
    now = datetime.now(timezone.utc)
    job = IngestionJobResponse(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status=IngestionStatus.SUCCEEDED,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    assert job.status == IngestionStatus.SUCCEEDED
    assert job.error_message is None


def test_chat_request_and_response_validation():
    """Verify ChatRequest validation rules and ChatResponse model."""
    # Valid
    req = ChatRequest(question="What is Rorak?")
    assert req.question == "What is Rorak?"

    # Empty question rejected
    with pytest.raises(PydanticValidationError):
        ChatRequest(question="")

    # Oversized question (> 10000 chars) rejected
    with pytest.raises(PydanticValidationError):
        ChatRequest(question="a" * 10001)

    # ChatResponse
    resp = ChatResponse(answer="Rorak is an AI assistant.")
    assert resp.answer == "Rorak is an AI assistant."


def test_document_upload_response_schema():
    """Verify DocumentUploadResponse structure."""
    resp = DocumentUploadResponse(
        message="Upload succeeded",
        filename="test.pdf",
        chunks_created=5,
    )
    assert resp.filename == "test.pdf"
    assert resp.chunks_created == 5
    assert resp.message == "Upload succeeded"


def test_request_validation_models():
    """Verify validation constraints on CreateWorkspace, CreateConversation, CreateMessage, and AddMember."""
    # CreateWorkspaceRequest: empty or > 50 chars rejected
    with pytest.raises(PydanticValidationError):
        CreateWorkspaceRequest(name="")
    with pytest.raises(PydanticValidationError):
        CreateWorkspaceRequest(name="a" * 51)
    valid_ws = CreateWorkspaceRequest(name="Engineering")
    assert valid_ws.name == "Engineering"

    # CreateConversationRequest: empty title rejected, missing user_id rejected
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()
    with pytest.raises(PydanticValidationError):
        CreateConversationRequest(workspace_id=ws_id, user_id=u_id, title="")
    valid_conv = CreateConversationRequest(workspace_id=ws_id, user_id=u_id, title="Sprint Plan")
    assert valid_conv.title == "Sprint Plan"

    # CreateMessageRequest: empty content or invalid role rejected
    with pytest.raises(PydanticValidationError):
        CreateMessageRequest(role="user", content="")
    with pytest.raises(PydanticValidationError):
        CreateMessageRequest(role="invalid_role", content="Hello")
    valid_msg = CreateMessageRequest(role="user", content="Hello world")
    assert valid_msg.role == MessageRole.USER

    # AddMemberRequest: missing or invalid user_id rejected
    with pytest.raises(PydanticValidationError):
        AddMemberRequest(user_id="not-a-uuid", role="admin")
    valid_member = AddMemberRequest(user_id=u_id, role="admin")
    assert valid_member.role == "admin"
    assert valid_member.user_id == u_id


def test_api_error_response_schema():
    """Verify APIErrorResponse contract envelope."""
    from backend.models.schemas import APIErrorResponse, ErrorDetail

    err = APIErrorResponse(
        error=ErrorDetail(code="NOT_FOUND", message="Resource was not found.")
    )
    assert err.error.code == "NOT_FOUND"
    assert err.error.message == "Resource was not found."
    assert err.error.request_id is None
    assert err.error.field is None


def test_rename_document_request_validation():
    """Verify RenameDocumentRequest validation rules."""
    # Valid name
    req = RenameDocumentRequest(display_name="My Research Notes")
    assert req.display_name == "My Research Notes"

    # Single character valid
    req_short = RenameDocumentRequest(display_name="A")
    assert req_short.display_name == "A"

    # Exactly 255 characters valid
    req_max = RenameDocumentRequest(display_name="x" * 255)
    assert len(req_max.display_name) == 255

    # Empty string rejected
    with pytest.raises(PydanticValidationError):
        RenameDocumentRequest(display_name="")

    # Too long (> 255 characters) rejected
    with pytest.raises(PydanticValidationError):
        RenameDocumentRequest(display_name="x" * 256)


def test_document_upload_response_schema():
    """Verify DocumentUploadResponse structure with document, ingestion_job, and chunk_count."""
    now = datetime.now(timezone.utc)
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    job_id = uuid.uuid4()

    doc_resp = DocumentResponse(
        id=doc_id,
        workspace_id=ws_id,
        filename="notes.pdf",
        original_filename="My_Notes.pdf",
        display_name="My Notes",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        page_count=2,
        chunk_count=4,
        status=DocumentStatus.INDEXED,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )

    job_resp = IngestionJobResponse(
        id=job_id,
        document_id=doc_id,
        status=IngestionStatus.SUCCEEDED,
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
    )

    upload_resp = DocumentUploadResponse(
        document=doc_resp,
        ingestion_job=job_resp,
        chunk_count=4,
    )

    assert upload_resp.document.id == doc_id
    assert upload_resp.ingestion_job.id == job_id
    assert upload_resp.chunk_count == 4


def test_document_response_orm_serialization():
    """Verify DocumentResponse serializes correctly from an ORM-like object."""
    from unittest.mock import Mock

    now = datetime.now(timezone.utc)
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    orm_doc = Mock()
    orm_doc.id = doc_id
    orm_doc.workspace_id = ws_id
    orm_doc.filename = "report.pdf"
    orm_doc.original_filename = "Quarterly_Report.pdf"
    orm_doc.display_name = "Quarterly Report"
    orm_doc.file_type = "pdf"
    orm_doc.mime_type = "application/pdf"
    orm_doc.file_size = 4096
    orm_doc.page_count = 10
    orm_doc.chunk_count = 25
    orm_doc.status = DocumentStatus.INDEXED
    orm_doc.failure_reason = None
    orm_doc.created_at = now
    orm_doc.updated_at = now

    resp = DocumentResponse.model_validate(orm_doc)
    assert resp.id == doc_id
    assert resp.workspace_id == ws_id
    assert resp.display_name == "Quarterly Report"
    assert resp.original_filename == "Quarterly_Report.pdf"
    assert resp.mime_type == "application/pdf"
    assert resp.chunk_count == 25
    assert resp.status == DocumentStatus.INDEXED
    assert resp.failure_reason is None
