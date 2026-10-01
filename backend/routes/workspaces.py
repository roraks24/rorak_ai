import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user, verify_workspace_access
from backend.core.database import get_db
from backend.models.db import User, Workspace, WorkspaceMember
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        409: {"model": APIErrorResponse, "description": "Workspace Already Exists"},
    },
)
def create_workspace(
    payload: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = WorkspaceService(db)
    owner_id = payload.owner_id or current_user.id
    try:
        workspace = service.create_workspace(
            name=payload.name,
            owner_id=owner_id,
        )
        # Ensure current user is explicitly recorded as member/owner if not the owner_id
        if current_user.id != owner_id:
            try:
                service.add_member(workspace_id=workspace.id, user_id=current_user.id, role="admin")
            except Exception:
                pass
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        403: {"model": APIErrorResponse, "description": "Forbidden"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify workspace membership
    verify_workspace_access(workspace_id=workspace_id, user_id=current_user.id, db=db)
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
    responses={
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
    },
)
def list_workspaces(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Scoped to workspaces the current user is a member of
        offset = (page - 1) * page_size
        query = (
            db.query(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .filter(WorkspaceMember.user_id == current_user.id)
            .order_by(Workspace.created_at.desc())
        )
        total = query.count()
        workspaces = query.offset(offset).limit(page_size).all()
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        403: {"model": APIErrorResponse, "description": "Forbidden"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify workspace membership and role (owner/admin)
    verify_workspace_access(
        workspace_id=workspace_id,
        user_id=current_user.id,
        db=db,
        required_roles=["owner", "admin"],
    )
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        403: {"model": APIErrorResponse, "description": "Forbidden"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
        409: {"model": APIErrorResponse, "description": "Member Already Exists"},
    },
)
def add_workspace_member(
    workspace_id: UUID,
    payload: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_workspace_access(
        workspace_id=workspace_id,
        user_id=current_user.id,
        db=db,
        required_roles=["owner", "admin"],
    )
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        403: {"model": APIErrorResponse, "description": "Forbidden"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def get_workspace_members(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_workspace_access(workspace_id=workspace_id, user_id=current_user.id, db=db)
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
        401: {"model": APIErrorResponse, "description": "Unauthorized"},
        403: {"model": APIErrorResponse, "description": "Forbidden"},
        404: {"model": APIErrorResponse, "description": "Workspace Not Found"},
    },
)
def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only self-removal or owner/admin can remove members
    if current_user.id != user_id:
        verify_workspace_access(
            workspace_id=workspace_id,
            user_id=current_user.id,
            db=db,
            required_roles=["owner", "admin"],
        )
    else:
        verify_workspace_access(
            workspace_id=workspace_id,
            user_id=current_user.id,
            db=db,
        )

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
