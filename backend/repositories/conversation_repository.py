from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.db.conversation import Conversation


class ConversationRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_workspace(
        self,
        workspace_id: UUID,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_workspace_paginated(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_workspace(self, workspace_id: UUID) -> int:
        stmt = select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace_id
        )
        return self.db.execute(stmt).scalar() or 0

    def get_by_user(
        self,
        user_id: UUID,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_user_paginated(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_user(self, user_id: UUID) -> int:
        stmt = select(func.count(Conversation.id)).where(
            Conversation.user_id == user_id
        )
        return self.db.execute(stmt).scalar() or 0

    def create(
        self,
        conversation: Conversation,
    ) -> Conversation:
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def delete(
        self,
        conversation: Conversation,
    ) -> None:
        self.db.delete(conversation)
        self.db.flush()