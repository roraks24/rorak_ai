from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.models.db.memory import Memory


class MemoryRepository:
    """Repository handling CRUD operations and scoped queries for durable memory."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, memory_id: UUID) -> Memory | None:
        """Get memory by ID."""
        stmt = select(Memory).where(Memory.id == memory_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user(self, user_id: UUID, limit: int = 10) -> list[Memory]:
        """Get recent memories for a user."""
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_workspace(self, workspace_id: UUID, limit: int = 10) -> list[Memory]:
        """Get recent memories for a workspace."""
        stmt = (
            select(Memory)
            .where(Memory.workspace_id == workspace_id)
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_scoped_memories(
        self,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Retrieve relevant durable memories for the specified scope
        (user and/or workspace), newest first.
        """
        stmt = select(Memory)
        conditions = []
        if user_id is not None:
            conditions.append(Memory.user_id == user_id)
        if workspace_id is not None:
            conditions.append(Memory.workspace_id == workspace_id)

        if conditions:
            stmt = stmt.where(or_(*conditions))

        stmt = stmt.order_by(Memory.created_at.desc(), Memory.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_by_user(self, user_id: UUID) -> int:
        """Count memories for a user."""
        stmt = select(func.count(Memory.id)).where(Memory.user_id == user_id)
        return self.db.execute(stmt).scalar_one()

    def count_by_workspace(self, workspace_id: UUID) -> int:
        """Count memories for a workspace."""
        stmt = select(func.count(Memory.id)).where(Memory.workspace_id == workspace_id)
        return self.db.execute(stmt).scalar_one()

    def create(self, memory: Memory) -> Memory:
        """Create and flush a new memory record."""
        self.db.add(memory)
        self.db.flush()
        return memory

    def delete(self, memory: Memory) -> None:
        """Delete a memory record."""
        self.db.delete(memory)
        self.db.flush()
