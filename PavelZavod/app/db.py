from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base

_settings = get_settings()
_engine = create_engine(_settings.database_url, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create database tables if they don't exist."""

    Base.metadata.create_all(bind=_engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_engine():
    return _engine
