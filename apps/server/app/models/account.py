"""Account — platform identity assigned to a cluster. No OAuth tokens."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import ACCOUNT_STATUS_ENUM, PLATFORM_ENUM, AccountStatus, Platform


if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.post_job import PostJob


class Account(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `accounts`.

    Uniqueness lock (1.2f-ii): (`platform`, `handle`) is unique. The same
    handle may exist on another platform. `external_account_id` is a
    nullable vendor/platform id and is not part of the unique key.

    OAuth / refresh tokens are out of scope for 1.2 — do not add token
    columns here.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "handle",
            name="uq_accounts_platform_handle",
        ),
        Index("ix_accounts_cluster_id", "cluster_id"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id"),
        nullable=False,
    )
    platform: Mapped[Platform] = mapped_column(PLATFORM_ENUM, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        ACCOUNT_STATUS_ENUM,
        nullable=False,
    )
    cadence_cap_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cluster: Mapped["Cluster"] = relationship(
        "Cluster",
        back_populates="accounts",
    )
    post_jobs: Mapped[list["PostJob"]] = relationship(
        "PostJob",
        back_populates="account",
    )
