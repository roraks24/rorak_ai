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
)
from backend.services.conversation_service import ConversationService
from backend.services.exceptions import (
    ConversationNotFound,
    ValidationError,
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
    },
)
def create_conversation(
    payload: CreateConversationRequest,
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        conv = service.create_conversation(
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            title=payload.title,
        )
        return conv
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
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        return service.get_conversation(conversation_id)
    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/",
    response_model=ConversationListResponse,
)
def list_conversations(
    workspace_id: UUID = Query(..., description="Filter conversations by workspace ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        convs, total = service.list_workspace_conversations(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
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
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        service.delete_conversation(conversation_id)
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
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        msg = service.create_message(
            conversation_id=conversation_id,
            role=payload.role,
            content=payload.content,
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    try:
        messages, total = service.get_messages(
            conversation_id=conversation_id,
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
