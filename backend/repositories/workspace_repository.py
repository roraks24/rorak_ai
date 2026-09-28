from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.db.workspace import Workspace


class WorkspaceRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, skip: int = 0, limit: int = 20) -> list[Workspace]:
        stmt = select(Workspace).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count(self) -> int:
        stmt = select(func.count(Workspace.id))
        return self.db.execute(stmt).scalar() or 0

    def create(self, workspace: Workspace) -> Workspace:
        self.db.add(workspace)
        self.db.flush()
        return workspace

    def delete(self, workspace: Workspace) -> None:
        self.db.delete(workspace)
        self.db.flush()