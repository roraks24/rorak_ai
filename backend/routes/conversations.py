import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.schemas import (
    APIErrorResponse,
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    MessageListResponse,
    MessageResponse,
    Pagination,
    RenameConversationRequest,
)
from backend.services.conversation_service import ConversationService
from backend.services.exceptions import (
    ConversationNotFound,
    UserNotFound,
    ValidationError,
    WorkspaceNotFound,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Workspace or User Not Found"},
    },
)
def create_conversation(
    payload: CreateConversationRequest,
    db: Session = Depends(get_db),
):
    """Create a new conversation thread bound to a specific user and workspace."""
    service = ConversationService(db)
    try:
        conv = service.create_conversation(
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            title=payload.title,
        )
        return conv
    except (WorkspaceNotFound, UserNotFound) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    responses={
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
    },
)
def get_conversation(
    conversation_id: UUID,
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID scoping"),
    user_id: UUID | None = Query(default=None, description="Optional user ID scoping"),
    db: Session = Depends(get_db),
):
    """Retrieve / reopen a conversation thread with optional workspace/user scoping."""
    service = ConversationService(db)
    try:
        return service.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
    },
)
def rename_conversation(
    conversation_id: UUID,
    payload: RenameConversationRequest,
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID scoping"),
    user_id: UUID | None = Query(default=None, description="Optional user ID scoping"),
    db: Session = Depends(get_db),
):
    """Change conversation title without mutating historical messages."""
    service = ConversationService(db)
    try:
        return service.rename_conversation(
            conversation_id=conversation_id,
            title=payload.title,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/",
    response_model=ConversationListResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Workspace or User Not Found"},
    },
)
def list_conversations(
    workspace_id: UUID | None = Query(default=None, description="Filter conversations by workspace ID"),
    user_id: UUID | None = Query(default=None, description="Filter conversations by user ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List conversation threads scoped to workspace and/or user with pagination."""
    service = ConversationService(db)
    try:
        if workspace_id is not None:
            convs, total = service.list_workspace_conversations(
                workspace_id=workspace_id,
                user_id=user_id,
                page=page,
                page_size=page_size,
            )
        elif user_id is not None:
            convs, total = service.list_user_conversations(
                user_id=user_id,
                workspace_id=None,
                page=page,
                page_size=page_size,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "Either workspace_id or user_id must be provided to list conversations."}},
            )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return ConversationListResponse(
            conversations=convs,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )
    except (WorkspaceNotFound, UserNotFound) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.delete(
    "/{conversation_id}",
    responses={
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
    },
)
def delete_conversation(
    conversation_id: UUID,
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID scoping"),
    user_id: UUID | None = Query(default=None, description="Optional user ID scoping"),
    db: Session = Depends(get_db),
):
    """Remove a conversation thread and cleanly delete all associated messages."""
    service = ConversationService(db)
    try:
        service.delete_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return {"status": "deleted", "message": f"Conversation {conversation_id} deleted."}
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
    },
)
def create_message(
    conversation_id: UUID,
    payload: CreateMessageRequest,
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID scoping"),
    user_id: UUID | None = Query(default=None, description="Optional user ID scoping"),
    db: Session = Depends(get_db),
):
    """Add a message to a conversation thread."""
    service = ConversationService(db)
    try:
        msg = service.create_message(
            conversation_id=conversation_id,
            role=payload.role,
            content=payload.content,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return msg
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
    },
)
def get_messages(
    conversation_id: UUID,
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID scoping"),
    user_id: UUID | None = Query(default=None, description="Optional user ID scoping"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Load conversation history in deterministic order."""
    service = ConversationService(db)
    try:
        messages, total = service.get_messages(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return MessageListResponse(
            messages=messages,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
