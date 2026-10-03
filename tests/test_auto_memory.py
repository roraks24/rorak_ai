"""
Tests for Automated Long-Term Memory Extraction and Storage (Rorak AI V2).
"""
import uuid
import pytest
from unittest.mock import patch

from backend.core.database import get_db
from backend.models.db import User, Memory
from backend.services.conversation_service import ConversationService
from backend.services.memory_extractor import (
    extract_durable_memories,
    has_memory_indicators,
    auto_extract_and_save_memories,
)


@pytest.fixture
def db_session():
    gen = get_db()
    session = next(gen)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_user(db_session):
    user = User(id=uuid.uuid4(), email=f"mem_auto_{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(user)
    db_session.commit()
    yield user

    # Cleanup in proper dependency order
    from backend.models.db import Conversation, Message
    conv_ids = [c.id for c in db_session.query(Conversation).filter(Conversation.user_id == user.id).all()]
    if conv_ids:
        db_session.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db_session.query(Conversation).filter(Conversation.id.in_(conv_ids)).delete(synchronize_session=False)
    db_session.query(Memory).filter(Memory.user_id == user.id).delete(synchronize_session=False)
    db_session.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db_session.commit()


def test_has_memory_indicators():
    assert has_memory_indicators("My name is John") is True
    assert has_memory_indicators("Call me Alex") is True
    assert has_memory_indicators("I work as a developer") is True
    assert has_memory_indicators("I prefer Python") is True
    assert has_memory_indicators("Remember that I am vegan") is True
    assert has_memory_indicators("What is photosynthesis?") is False
    assert has_memory_indicators("Hello!") is False
    assert has_memory_indicators("Summarize this document for me") is False


def test_extract_durable_memories_name():
    res1 = extract_durable_memories("My name is Alice.")
    assert len(res1) == 1
    assert res1[0]["content"] == "User's name is Alice"
    assert res1[0]["memory_type"] == "fact"

    res2 = extract_durable_memories("Please call me Bob.")
    assert len(res2) == 1
    assert res2[0]["content"] == "User's name is Bob"

    res3 = extract_durable_memories("I'm Charlie")
    assert len(res3) == 1
    assert res3[0]["content"] == "User's name is Charlie"


def test_extract_durable_memories_role_and_location():
    res_role = extract_durable_memories("I work as a senior backend engineer")
    assert len(res_role) == 1
    assert "senior backend engineer" in res_role[0]["content"]

    res_loc = extract_durable_memories("I live in San Francisco")
    assert len(res_loc) == 1
    assert "San Francisco" in res_loc[0]["content"]


def test_extract_durable_memories_preferences():
    res = extract_durable_memories("I prefer PostgreSQL over MySQL")
    assert len(res) == 1
    assert res[0]["content"] == "User prefers PostgreSQL over MySQL"
    assert res[0]["memory_type"] == "preference"

    res_fav = extract_durable_memories("My favorite framework is FastAPI")
    assert len(res_fav) == 1
    assert "FastAPI" in res_fav[0]["content"]


def test_extract_durable_memories_directives():
    res = extract_durable_memories("Remember that I have a gluten allergy")
    assert len(res) == 1
    assert "gluten allergy" in res[0]["content"].lower()
    assert res[0]["memory_type"] == "directive"


def test_auto_save_memories_in_db_and_deduplication(db_session, sample_user):
    user = sample_user

    # First call extracts and saves
    saved_first = auto_extract_and_save_memories(
        db=db_session,
        user_content="My name is David. I prefer Python.",
        user_id=user.id,
    )
    assert len(saved_first) >= 1
    names = [m.content for m in saved_first]
    assert "User's name is David" in names

    # Verify saved in database
    db_mems = db_session.query(Memory).filter(Memory.user_id == user.id).all()
    assert len(db_mems) == len(saved_first)

    # Second call with the same content skips duplicates
    saved_second = auto_extract_and_save_memories(
        db=db_session,
        user_content="My name is David",
        user_id=user.id,
    )
    assert len(saved_second) == 0

    # Total in DB remains unchanged
    total_mems = db_session.query(Memory).filter(Memory.user_id == user.id).count()
    assert total_mems == len(saved_first)


def test_auto_save_memories_rejects_sensitive_info(db_session, sample_user):
    user = sample_user

    saved = auto_extract_and_save_memories(
        db=db_session,
        user_content="Remember that my password is supersecretpassword123!",
        user_id=user.id,
    )
    assert len(saved) == 0

    saved_token = auto_extract_and_save_memories(
        db=db_session,
        user_content="Remember that my api_key = sk-12345678901234567890123456",
        user_id=user.id,
    )
    assert len(saved_token) == 0


def test_conversation_service_auto_saves_memory_end_to_end(db_session, sample_user):
    user = sample_user
    service = ConversationService(db_session)

    conv = service.create_conversation(
        user_id=user.id,
        title="Auto Memory Test",
    )

    with patch("backend.services.conversation_service.chat_func") as mock_chat:
        mock_chat.return_value = "Hello Michael! Great to meet you."

        user_msg, asst_msg = service.send_user_message_and_reply(
            conversation_id=conv.id,
            user_content="Hi Rorak, my name is Michael and I live in Chicago",
            user_id=user.id,
        )

        assert user_msg.content == "Hi Rorak, my name is Michael and I live in Chicago"
        assert asst_msg.content == "Hello Michael! Great to meet you."

    # Check memories saved for user
    mems = service.memory_repository.get_scoped_memories(user_id=user.id)
    contents = [m.content for m in mems]
    assert any("Michael" in c for c in contents)
