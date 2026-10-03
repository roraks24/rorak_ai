from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.models.db.conversation import Conversation
from backend.models.db.message import Message


class ConversationRepository:
    """Repository handling CRUD operations and queries for conversations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self,
        conversation_id: UUID,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> Conversation | None:
        """
        Get a conversation by ID, optionally scoped to a user.
        """
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)

        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user(
        self,
        user_id: UUID,
        workspace_id: UUID | None = None,
    ) -> list[Conversation]:
        """
        Return conversations for a user, newest first.
        """
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(
                Conversation.created_at.desc(),
                Conversation.id.desc(),
            )
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_by_user_paginated(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        workspace_id: UUID | None = None,
    ) -> list[Conversation]:
        """
        Return a paginated list of conversations for a user.
        """
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(
                Conversation.created_at.desc(),
                Conversation.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def count_by_user(
        self,
        user_id: UUID,
        workspace_id: UUID | None = None,
    ) -> int:
        """
        Count conversations for a user.
        """
        stmt = select(func.count(Conversation.id)).where(
            Conversation.user_id == user_id
        )

        return self.db.execute(stmt).scalar_one()

    def get_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
    ) -> list[Conversation]:
        """Backward-compatible fallback mapping to user conversations."""
        if user_id is not None:
            return self.get_by_user(user_id=user_id)
        stmt = select(Conversation).order_by(
            Conversation.created_at.desc(),
            Conversation.id.desc(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_workspace_paginated(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Conversation]:
        """Backward-compatible fallback mapping to user conversations."""
        if user_id is not None:
            return self.get_by_user_paginated(user_id=user_id, skip=skip, limit=limit)
        stmt = (
            select(Conversation)
            .order_by(
                Conversation.created_at.desc(),
                Conversation.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
    ) -> int:
        """Backward-compatible fallback counting user conversations."""
        if user_id is not None:
            return self.count_by_user(user_id=user_id)
        stmt = select(func.count(Conversation.id))
        return self.db.execute(stmt).scalar_one()

    def create(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """Create and flush a new conversation."""
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def update_title(
        self,
        conversation: Conversation,
        title: str,
    ) -> Conversation:
        """Update only the conversation title and flush."""
        conversation.title = title
        self.db.flush()
        return conversation

    def delete(
        self,
        conversation: Conversation | UUID,
        workspace_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> bool:
        """
        Delete a conversation. Accepts either a Conversation instance or conversation UUID.
        """
        if isinstance(conversation, UUID):
            conv = self.get_by_id(
                conversation_id=conversation,
                user_id=user_id,
            )
            if conv is None:
                return False
            target = conv
        else:
            target = conversation

        self.db.delete(target)
        self.db.flush()
        return True