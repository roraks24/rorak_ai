"""
Authentication and Authorization dependencies for FastAPI.

Rorak AI V2.6: Authentication & Multi-User Isolation.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.models.db import User, Workspace, WorkspaceMember


logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate request via JWT Bearer token and resolve active User.
    Raises 401 Unauthorized if token is missing, expired, or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing authentication credentials."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Token payload missing subject identifier."}},
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = UUID(str(user_id_str))
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Access token has expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.PyJWTError, ValueError) as e:
        logger.debug("JWT decode failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or malformed authentication token."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "User associated with token not found."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Authenticate request if Bearer token is provided.
    Returns None if no credentials are provided.
    Raises 401 if invalid or expired token is provided.
    """
    if not credentials or not credentials.credentials:
        return None
    return get_current_user(credentials=credentials, db=db)


def verify_workspace_access(
    workspace_id: UUID,
    user_id: UUID,
    db: Session,
    required_roles: Optional[List[str]] = None,
) -> WorkspaceMember:
    """
    Validate that the user is an authorized member of the specified workspace.
    Raises 404 if workspace does not exist.
    Raises 403 if user is not a member or lacks required roles.
    """
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "WORKSPACE_NOT_FOUND", "message": f"Workspace {workspace_id} not found."}},
        )

    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "You do not have access to this workspace."}},
        )

    if required_roles and member.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient permissions for this operation."}},
        )

    return member
