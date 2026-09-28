import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.schemas import (
    AddMemberRequest,
    APIErrorResponse,
    CreateWorkspaceRequest,
    Pagination,
    WorkspaceListResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from backend.services.exceptions import (
    Conflict,
    ValidationError,
    WorkspaceAlreadyExists,
    WorkspaceNotFound,
)
from backend.services.workspace_service import WorkspaceService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        409: {"model": APIErrorResponse, "description": "Workspace Already Exists"},
    },
)
def create_workspace(
    payload: CreateWorkspaceRequest,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        workspace = service.create_workspace(
            name=payload.name,
            owner_id=payload.owner_id,
        )
        return workspace
    except WorkspaceAlreadyExists as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    responses={
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        return service.get_workspace(workspace_id)
    except WorkspaceNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/",
    response_model=WorkspaceListResponse,
)
def list_workspaces(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        workspaces, total = service.list_workspaces(page=page, page_size=page_size)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return WorkspaceListResponse(
            workspaces=workspaces,
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
    "/{workspace_id}",
    responses={
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def delete_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        service.delete_workspace(workspace_id)
        return {"status": "deleted", "message": f"Workspace {workspace_id} deleted."}
    except WorkspaceNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
        409: {"model": APIErrorResponse, "description": "Member Already Exists"},
    },
)
def add_workspace_member(
    workspace_id: UUID,
    payload: AddMemberRequest,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        member = service.add_member(
            workspace_id=workspace_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        return member
    except WorkspaceNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except Conflict as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    responses={
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def get_workspace_members(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        return service.get_members(workspace_id)
    except WorkspaceNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        service.remove_member(workspace_id=workspace_id, user_id=user_id)
        return {"status": "removed", "message": f"User {user_id} removed from workspace."}
    except WorkspaceNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
