import logging
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.db.users import User
from backend.models.schemas import APIErrorResponse
from backend.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
    updated_at: datetime


class CreateUserRequest(BaseModel):
    email: str


@router.get(
    "/default",
    response_model=UserResponse,
    responses={
        500: {"model": APIErrorResponse, "description": "Internal Server Error"},
    },
)
def get_or_create_default_user(db: Session = Depends(get_db)):
    """Retrieve or automatically provision the default application user."""
    repo = UserRepository(db)
    default_email = "default@rorak.tech"
    user = repo.get_by_email(default_email)
    if user is None:
        user = User(
            id=uuid4(),
            email=default_email,
        )
        repo.create(user)
        db.commit()
        db.refresh(user)
        logger.info("Created default application user with ID: %s", user.id)
    return user


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
    },
)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)):
    """Create a new user or return existing by email."""
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Valid email is required."}},
        )
    repo = UserRepository(db)
    user = repo.get_by_email(clean_email)
    if user is not None:
        return user
    user = User(
        id=uuid4(),
        email=clean_email,
    )
    repo.create(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        404: {"model": APIErrorResponse, "description": "User Not Found"},
    },
)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a user by ID."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"User with ID {user_id} was not found."}},
        )
    return user
