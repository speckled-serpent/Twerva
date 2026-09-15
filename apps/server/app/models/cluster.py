"""Cluster / lane — topical account group (steer grain and purity)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Index, Table, Text, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.artifact import Artifact
    from app.models.brand import Brand
    from app.models.source_item import SourceItem
    from app.models.steer_action import SteerAction


cluster_source_items: Table = Table(
    "cluster_source_items",
    Base.metadata,
    Column(
        "cluster_id",
        UUID(as_uuid=True),
        ForeignKey("clusters.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "source_item_id",
        UUID(as_uuid=True),
        ForeignKey("source_items.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Index("ix_cluster_source_items_cluster_id", "cluster_id"),
    Index("ix_cluster_source_items_source_item_id", "source_item_id"),
)


class Cluster(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `clusters`.

    `slug` is unique per brand via unique index `ix_clusters_brand_id_slug`.
    Manual interest→lane assignment uses the `cluster_source_items` join.
    The composite primary key (`cluster_id`, `source_item_id`) is the
    unique pair (1.2e-ii).
    """

    __tablename__ = "clusters"
    __table_args__ = (
        Index("ix_clusters_brand_id", "brand_id"),
        Index("ix_clusters_brand_id_slug", "brand_id", "slug", unique=True),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
    )

    brand: Mapped["Brand"] = relationship(
        "Brand",
        back_populates="clusters",
    )
    source_items: Mapped[list["SourceItem"]] = relationship(
        "SourceItem",
        secondary=cluster_source_items,
        back_populates="clusters",
    )
    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="cluster",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="cluster",
    )
    steer_actions: Mapped[list["SteerAction"]] = relationship(
        "SteerAction",
        back_populates="cluster",
    )
