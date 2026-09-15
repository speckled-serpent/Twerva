"""SQLAlchemy declarative base for Twerva tables (1.2b+)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata root. No domain models in 1.2a."""
