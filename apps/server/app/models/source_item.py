"""Source item — raw material unit (Phase 1 shape = Spotmu interest)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import SOURCE_TYPE_ENUM, SourceType


if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.brand import Brand
    from app.models.cluster import Cluster


class SourceItem(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `source_items`.

    Uniqueness: partial unique index on (`brand_id`, `source_type`,
    `external_key`) where `external_key` is not null. Multiple rows may
    omit `external_key`. Queries that list a brand's hose also use
    `ix_source_items_brand_id_source_type`.
    """

    __tablename__ = "source_items"
    __table_args__ = (
        Index("ix_source_items_brand_id", "brand_id"),
        Index("ix_source_items_brand_id_source_type", "brand_id", "source_type"),
        Index(
            "uq_source_items_brand_type_external_key",
            "brand_id",
            "source_type",
            "external_key",
            unique=True,
            postgresql_where=text("external_key IS NOT NULL"),
        ),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id"),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SOURCE_TYPE_ENUM,
        nullable=False,
    )
    external_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    interest_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    overview_bullets: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_kit_refs: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    brand: Mapped["Brand"] = relationship(
        "Brand",
        back_populates="source_items",
    )
    clusters: Mapped[list["Cluster"]] = relationship(
        "Cluster",
        secondary="cluster_source_items",
        back_populates="source_items",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="source_item",
    )
