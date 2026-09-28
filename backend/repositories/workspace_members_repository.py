from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.db.workspace_members import WorkspaceMember


class WorkspaceMemberRepository:

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )

        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_workspace(
        self,
        workspace_id: UUID,
    ) -> list[WorkspaceMember]:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_by_user(
        self,
        user_id: UUID,
    ) -> list[WorkspaceMember]:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id
        )

        return list(self.db.execute(stmt).scalars().all())

    def create(self, membership: WorkspaceMember) -> WorkspaceMember:
        self.db.add(membership)
        self.db.flush()
        return membership

    def delete(self, membership: WorkspaceMember) -> None:
        self.db.delete(membership)
        self.db.flush()