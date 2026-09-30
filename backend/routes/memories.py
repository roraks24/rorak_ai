import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.schemas import (
    APIErrorResponse,
    CreateMemoryRequest,
    MemoryListResponse,
    MemoryResponse,
    Pagination,
    UpdateMemoryRequest,
)
from backend.services.exceptions import (
    MemoryNotFound,
    UserNotFound,
    ValidationError,
    WorkspaceNotFound,
)
from backend.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/memories",
    tags=["Memories"],
)


@router.post(
    "/",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "User or Workspace Not Found"},
    },
)
def create_memory(
    payload: CreateMemoryRequest,
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    try:
        memory = service.create_memory(
            user_id=payload.user_id,
            content=payload.content,
            memory_type=payload.memory_type,
            workspace_id=payload.workspace_id,
        )
        return memory
    except (UserNotFound, WorkspaceNotFound) as e:
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
    response_model=MemoryListResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "User or Workspace Not Found"},
    },
)
def list_memories(
    user_id: UUID = Query(..., description="Owner user ID"),
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID"),
    memory_type: str | None = Query(default=None, description="Optional memory type filter"),
    include_global: bool = Query(default=True, description="Whether to include global user memories"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    try:
        memories, total = service.list_memories(
            user_id=user_id,
            workspace_id=workspace_id,
            memory_type=memory_type,
            include_global=include_global,
            page=page,
            page_size=page_size,
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return MemoryListResponse(
            memories=memories,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )
    except (UserNotFound, WorkspaceNotFound) as e:
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
    "/{memory_id}",
    response_model=MemoryResponse,
    responses={
        404: {"model": APIErrorResponse, "description": "Memory Not Found"},
    },
)
def get_memory(
    memory_id: UUID,
    user_id: UUID | None = Query(default=None, description="Optional user ID for scoping"),
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID for scoping"),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    try:
        return service.get_memory(
            memory_id=memory_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    except MemoryNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Memory Not Found"},
    },
)
def update_memory(
    memory_id: UUID,
    payload: UpdateMemoryRequest,
    user_id: UUID | None = Query(default=None, description="Optional user ID for scoping"),
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID for scoping"),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    try:
        return service.update_memory(
            memory_id=memory_id,
            content=payload.content,
            memory_type=payload.memory_type,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    except MemoryNotFound as e:
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
    "/{memory_id}",
    responses={
        404: {"model": APIErrorResponse, "description": "Memory Not Found"},
    },
)
def delete_memory(
    memory_id: UUID,
    user_id: UUID | None = Query(default=None, description="Optional user ID for scoping"),
    workspace_id: UUID | None = Query(default=None, description="Optional workspace ID for scoping"),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    try:
        service.delete_memory(
            memory_id=memory_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return {"status": "deleted", "message": f"Memory {memory_id} deleted."}
    except MemoryNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
