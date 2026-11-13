"""Metric snapshot — performance readback grain (per post job or campaign post)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UuidPrimaryKeyMixin


if TYPE_CHECKING:
    from app.models.campaign import CampaignPost
    from app.models.post_job import PostJob


METRIC_SNAPSHOT_OWNER_CHECK_SQL: str = (
    "(post_job_id IS NOT NULL AND campaign_post_id IS NULL) "
    "OR (post_job_id IS NULL AND campaign_post_id IS NOT NULL)"
)


class MetricSnapshot(Base, UuidPrimaryKeyMixin):
    """Row in `metric_snapshots`.

    Multiple snapshots per post job or campaign post are allowed. There
    is **no** unique constraint on `post_job_id` (that would collapse
    history). Exactly one of `post_job_id` and `campaign_post_id` is set.
    Queries take the latest row by `captured_at` (latest-wins).
    """

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("ix_metric_snapshots_post_job_id", "post_job_id"),
        Index("ix_metric_snapshots_campaign_post_id", "campaign_post_id"),
        CheckConstraint(METRIC_SNAPSHOT_OWNER_CHECK_SQL, name="owner"),
    )

    post_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("post_jobs.id"),
        nullable=True,
    )
    campaign_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_posts.id", ondelete="CASCADE"),
        nullable=True,
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

    post_job: Mapped["PostJob | None"] = relationship(
        "PostJob",
        back_populates="metric_snapshots",
    )
    campaign_post: Mapped["CampaignPost | None"] = relationship(
        "CampaignPost",
        back_populates="metric_snapshots",
    )
