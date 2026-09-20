"""Ops operator account — not a social `accounts` row.

`ops_users` is the operator login table for the public ops console.
It is intentionally separate from platform `accounts` (Instagram / TikTok
identities assigned to a cluster).
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import OPS_USER_ROLE_ENUM, OpsUserRole


class OpsUser(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `ops_users`.

    `username` is globally unique. `password_hash` is a bcrypt hash; never
    store or return the plaintext password. `role` is `admin` (full) or
    `reader` (GET-only under `/api/v1`, plus self password change).
    """

    __tablename__ = "ops_users"

    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[OpsUserRole] = mapped_column(
        OPS_USER_ROLE_ENUM,
        nullable=False,
        default=OpsUserRole.READER,
        server_default=OpsUserRole.READER.value,
    )
