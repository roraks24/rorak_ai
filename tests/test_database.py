from sqlalchemy import text
from backend.core.database import engine, SessionLocal, get_db, Base


def test_database_connection():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_lifecycle():
    gen = get_db()
    session = next(gen)
    try:
        assert session.is_active
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_base_metadata():
    assert Base.metadata is not None
