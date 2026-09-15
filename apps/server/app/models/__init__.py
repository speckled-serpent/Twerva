"""ORM models package.

Domain tables land in task 1.2b+. This package only exports the declarative
base so Alembic and `app.db` share the same metadata.
"""

from app.models.base import Base

__all__ = ["Base"]
