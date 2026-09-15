"""SQLAlchemy engine, session factory, and FastAPI session dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.settings import Settings, get_settings


settings: Settings = get_settings()
our_database_engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)
engine: Engine = our_database_engine
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=our_database_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_our_database_session() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session and close it afterward.

    FastAPI-compatible: `Depends(get_our_database_session)`.

    Yields:
        An open `Session` bound to `SessionLocal`.
    """

    our_database_session: Session = SessionLocal()

    try:
        yield our_database_session
    finally:
        our_database_session.close()


__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_our_database_session",
    "our_database_engine",
]
