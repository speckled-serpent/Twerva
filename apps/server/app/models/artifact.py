"""Artifact — draft or approved post asset (metadata + slide plan, no bytes)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import ARTIFACT_STATUS_ENUM, ArtifactStatus


if TYPE_CHECKING:
    from app.models.brand import Brand
    from app.models.cluster import Cluster
    from app.models.post_job import PostJob
    from app.models.source_item import SourceItem


class ArtifactSlide(TypedDict):
    """One ordered slide in `artifacts.slides`.

    `asset_ref` is a path relative to local `ARTIFACT_STORAGE_DIR`.
    """

    role: str
    text: str
    asset_ref: NotRequired[str]


class Artifact(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `artifacts`.

    Status is stored only; 1.5 approval routes enforce
    `ARTIFACT_STATUS_TRANSITIONS` (see `docs/planning/domain_statuses.md`).
    Media bytes stay out of Postgres — `slides` holds the structured plan.
    """

    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_brand_id", "brand_id"),
        Index("ix_artifacts_source_item_id", "source_item_id"),
        Index("ix_artifacts_cluster_id", "cluster_id"),
        Index("ix_artifacts_status", "status"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id"),
        nullable=False,
    )
    source_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_items.id"),
        nullable=True,
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id"),
        nullable=True,
    )
    status: Mapped[ArtifactStatus] = mapped_column(
        ARTIFACT_STATUS_ENUM,
        nullable=False,
    )
    format: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'carousel'"),
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    slides: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    brand: Mapped["Brand"] = relationship(
        "Brand",
        back_populates="artifacts",
    )
    source_item: Mapped["SourceItem | None"] = relationship(
        "SourceItem",
        back_populates="artifacts",
    )
    cluster: Mapped["Cluster | None"] = relationship(
        "Cluster",
        back_populates="artifacts",
    )
    post_jobs: Mapped[list["PostJob"]] = relationship(
        "PostJob",
        back_populates="artifact",
    )
