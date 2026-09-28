from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.db.message import Message


class MessageRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, message_id: UUID) -> Message | None:
        stmt = select(Message).where(Message.id == message_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_conversation(self, conversation_id: UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_conversation_paginated(
        self,
        conversation_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_conversation(self, conversation_id: UUID) -> int:
        stmt = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        return self.db.execute(stmt).scalar() or 0

    def create(self, message: Message) -> Message:
        self.db.add(message)
        self.db.flush()
        return message

    def delete(self, message: Message) -> None:
        self.db.delete(message)
        self.db.flush()
