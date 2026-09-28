import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.models.db.conversation import Conversation
from backend.models.db.message import Message
from backend.models.schemas import MessageRole
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.services.exceptions import (
    ConversationNotFound,
    ValidationError,
)
from backend.services.generator import chat_func


logger = logging.getLogger(__name__)

VALID_ROLES = {role.value for role in MessageRole}


class ConversationService:
    """
    Coordinates conversation lifecycle, message history, validation,
    and RAG generation integration.
    """

    def __init__(
        self,
        db: Session,
        repository: ConversationRepository | None = None,
        message_repository: MessageRepository | None = None,
    ):
        self.db = db
        self.repository = repository or ConversationRepository(db)
        self.message_repository = message_repository or MessageRepository(db)

    def get_conversation(self, conversation_id: UUID) -> Conversation:
        """Retrieve conversation by ID or raise ConversationNotFound."""
        conv = self.repository.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFound(f"Conversation with ID {conversation_id} was not found.")
        return conv

    def list_workspace_conversations(
        self,
        workspace_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        """List conversations in a workspace with pagination."""
        if page < 1:
            raise ValidationError("Page number must be >= 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        skip = (page - 1) * page_size
        convs = self.repository.get_by_workspace_paginated(
            workspace_id=workspace_id,
            skip=skip,
            limit=page_size,
        )
        total = self.repository.count_by_workspace(workspace_id)
        return convs, total

    def list_user_conversations(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        """List conversations for a user with pagination."""
        if page < 1:
            raise ValidationError("Page number must be >= 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        skip = (page - 1) * page_size
        convs = self.repository.get_by_user_paginated(
            user_id=user_id,
            skip=skip,
            limit=page_size,
        )
        total = self.repository.count_by_user(user_id)
        return convs, total

    def create_conversation(
        self,
        workspace_id: UUID,
        user_id: UUID,
        title: str,
    ) -> Conversation:
        """Create a new conversation record."""
        clean_title = title.strip() if title else ""
        if not clean_title:
            raise ValidationError("Conversation title cannot be empty.")
        if len(clean_title) > 255:
            raise ValidationError("Conversation title exceeds maximum length of 255 characters.")

        conv = Conversation(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            title=clean_title,
        )
        self.repository.create(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def delete_conversation(self, conversation_id: UUID) -> None:
        """Delete a conversation and its messages."""
        conv = self.get_conversation(conversation_id)
        messages = self.message_repository.get_by_conversation(conversation_id)
        for msg in messages:
            self.message_repository.delete(msg)
        self.repository.delete(conv)
        self.db.commit()

    def get_messages(
        self,
        conversation_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Message], int]:
        """Retrieve paginated messages for a conversation."""
        # Ensure conversation exists
        self.get_conversation(conversation_id)

        if page < 1:
            raise ValidationError("Page number must be >= 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        skip = (page - 1) * page_size
        messages = self.message_repository.get_by_conversation_paginated(
            conversation_id=conversation_id,
            skip=skip,
            limit=page_size,
        )
        total = self.message_repository.count_by_conversation(conversation_id)
        return messages, total

    def create_message(
        self,
        conversation_id: UUID,
        role: str | MessageRole,
        content: str,
    ) -> Message:
        """Validate and create a message in a conversation."""
        # Ensure conversation exists
        self.get_conversation(conversation_id)

        role_str = role.value if isinstance(role, MessageRole) else str(role).lower().strip()
        if role_str not in VALID_ROLES:
            raise ValidationError(
                f"Invalid message role '{role}'. Allowed roles: {sorted(list(VALID_ROLES))}."
            )

        clean_content = content.strip() if content else ""
        if not clean_content:
            raise ValidationError("Message content cannot be empty.")
        if len(clean_content) > 10000:
            raise ValidationError("Message content cannot exceed 10000 characters.")

        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role_str,
            content=clean_content,
        )
        self.message_repository.create(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def send_user_message_and_reply(
        self,
        conversation_id: UUID,
        user_content: str,
    ) -> tuple[Message, Message]:
        """
        Create user message, run RAG generation via chat_func(),
        and persist assistant response.
        """
        user_msg = self.create_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_content,
        )

        # Call existing RAG generator
        answer = chat_func(user_msg.content)

        assistant_msg = self.create_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer,
        )

        return user_msg, assistant_msg