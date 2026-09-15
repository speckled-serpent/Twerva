"""Post job — scheduled or published instance of an artifact on an account."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import POST_JOB_STATUS_ENUM, PostJobStatus


if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.artifact import Artifact
    from app.models.metric_snapshot import MetricSnapshot


class PostJob(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `post_jobs`.

    Status transitions are documented in `docs/planning/domain_statuses.md`
    and `POST_JOB_STATUS_TRANSITIONS`. The scheduler reads
    `ix_post_jobs_status_scheduled_for`.
    """

    __tablename__ = "post_jobs"
    __table_args__ = (
        Index("ix_post_jobs_artifact_id", "artifact_id"),
        Index("ix_post_jobs_account_id", "account_id"),
        Index("ix_post_jobs_status_scheduled_for", "status", "scheduled_for"),
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )
    status: Mapped[PostJobStatus] = mapped_column(
        POST_JOB_STATUS_ENUM,
        nullable=False,
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    platform_post_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    artifact: Mapped["Artifact"] = relationship(
        "Artifact",
        back_populates="post_jobs",
    )
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="post_jobs",
    )
    metric_snapshots: Mapped[list["MetricSnapshot"]] = relationship(
        "MetricSnapshot",
        back_populates="post_job",
    )
