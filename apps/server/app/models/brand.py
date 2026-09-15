"""Brand — first-class content world. Phase 1–2 seed brand is Spotmu."""

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.cluster import Cluster
    from app.models.source_item import SourceItem


class Brand(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `brands`.

    `slug` is globally unique (indexed by the unique constraint).
    `notes` and `voice_notes` are optional Phase 1 stubs — not a Phase 3
    brand-editorial engine.
    """

    __tablename__ = "brands"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_items: Mapped[list["SourceItem"]] = relationship(
        "SourceItem",
        back_populates="brand",
    )
    clusters: Mapped[list["Cluster"]] = relationship(
        "Cluster",
        back_populates="brand",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="brand",
    )
