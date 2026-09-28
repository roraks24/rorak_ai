import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.models.db.workspace import Workspace
from backend.models.db.workspace_members import WorkspaceMember
from backend.repositories.workspace_members_repository import WorkspaceMemberRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.services.exceptions import (
    Conflict,
    ValidationError,
    WorkspaceAlreadyExists,
    WorkspaceNotFound,
)


logger = logging.getLogger(__name__)

SUPPORTED_ROLES = {"owner", "admin", "member", "viewer"}


class WorkspaceService:
    """
    Coordinates workspace lifecycle, naming validation,
    and membership management with role isolation.
    """

    def __init__(
        self,
        db: Session,
        repository: WorkspaceRepository | None = None,
        member_repository: WorkspaceMemberRepository | None = None,
    ):
        self.db = db
        self.repository = repository or WorkspaceRepository(db)
        self.member_repository = member_repository or WorkspaceMemberRepository(db)

    def get_workspace(self, workspace_id: UUID) -> Workspace:
        """Retrieve workspace by ID or raise WorkspaceNotFound."""
        workspace = self.repository.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFound(f"Workspace with ID {workspace_id} was not found.")
        return workspace

    def get_workspace_by_name(self, name: str) -> Workspace:
        """Retrieve workspace by name or raise WorkspaceNotFound."""
        workspace = self.repository.get_by_name(name.strip())
        if not workspace:
            raise WorkspaceNotFound(f"Workspace with name '{name}' was not found.")
        return workspace

    def list_workspaces(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Workspace], int]:
        """List workspaces with pagination."""
        if page < 1:
            raise ValidationError("Page number must be >= 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        skip = (page - 1) * page_size
        workspaces = self.repository.list_all(skip=skip, limit=page_size)
        total = self.repository.count()
        return workspaces, total

    def create_workspace(
        self,
        name: str,
        owner_id: UUID | None = None,
    ) -> Workspace:
        """
        Validate name, ensure uniqueness, create workspace,
        and optionally assign initial owner membership.
        """
        clean_name = name.strip() if name else ""
        if not clean_name:
            raise ValidationError("Workspace name cannot be empty.")
        if len(clean_name) > 50:
            raise ValidationError("Workspace name cannot exceed 50 characters.")

        existing = self.repository.get_by_name(clean_name)
        if existing:
            raise WorkspaceAlreadyExists(
                f"A workspace with the name '{clean_name}' already exists."
            )

        workspace = Workspace(
            id=uuid4(),
            name=clean_name,
        )
        self.repository.create(workspace)

        if owner_id:
            membership = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=owner_id,
                role="owner",
            )
            self.member_repository.create(membership)

        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def delete_workspace(self, workspace_id: UUID) -> None:
        """Delete workspace and all associated member links."""
        workspace = self.get_workspace(workspace_id)
        members = self.member_repository.get_by_workspace(workspace_id)
        for member in members:
            self.member_repository.delete(member)

        self.repository.delete(workspace)
        self.db.commit()

    def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "member",
    ) -> WorkspaceMember:
        """Add or update member in a workspace."""
        self.get_workspace(workspace_id)

        clean_role = role.strip().lower() if role else ""
        if clean_role not in SUPPORTED_ROLES:
            raise ValidationError(
                f"Invalid role '{role}'. Supported roles: {sorted(list(SUPPORTED_ROLES))}."
            )

        existing = self.member_repository.get(workspace_id=workspace_id, user_id=user_id)
        if existing:
            raise Conflict("User is already a member of this workspace.")

        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=clean_role,
        )
        self.member_repository.create(membership)
        self.db.commit()
        return membership

    def get_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        """List all members of a workspace."""
        self.get_workspace(workspace_id)
        return self.member_repository.get_by_workspace(workspace_id)

    def remove_member(self, workspace_id: UUID, user_id: UUID) -> None:
        """Remove a member from a workspace."""
        self.get_workspace(workspace_id)
        membership = self.member_repository.get(workspace_id=workspace_id, user_id=user_id)
        if not membership:
            raise ValidationError("User is not a member of this workspace.")

        self.member_repository.delete(membership)
        self.db.commit()