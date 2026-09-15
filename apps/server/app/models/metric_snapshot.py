"""Metric snapshot — performance readback grain (per post job)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UuidPrimaryKeyMixin


if TYPE_CHECKING:
    from app.models.post_job import PostJob


class MetricSnapshot(Base, UuidPrimaryKeyMixin):
    """Row in `metric_snapshots`.

    Multiple snapshots per post job are allowed. There is **no** unique
    constraint on `post_job_id` (that would collapse history). Queries
    take the latest row by `captured_at` (latest-wins). Use
    `ix_metric_snapshots_post_job_id` plus `ORDER BY captured_at DESC`
    `LIMIT 1`.
    """

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("ix_metric_snapshots_post_job_id", "post_job_id"),
    )

    post_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("post_jobs.id"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    views: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    likes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comments: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    post_job: Mapped["PostJob"] = relationship(
        "PostJob",
        back_populates="metric_snapshots",
    )
