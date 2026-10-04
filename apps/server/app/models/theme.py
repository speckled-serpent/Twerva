"""Theme — visual styling for carousel advertisements (short video later)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    ADVERTISEMENT_TYPE_ENUM,
    BACKGROUND_KIND_ENUM,
    THEME_STATUS_ENUM,
    AdvertisementType,
    BackgroundKind,
    ThemeStatus,
)


if TYPE_CHECKING:
    from app.models.ops_user import OpsUser
    from app.models.theme_element import ThemeElement


DEFAULT_PAGE_MARGIN: int = 96
DEFAULT_ELEMENT_GAP: int = 0
DEFAULT_ELEMENT_MARGIN: int = 0
DEFAULT_BACKGROUND_COLOR: str = "#F6F1E8"


class Theme(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `themes`.

    Create stores a name, a unique slug derived from that name,
    ``advertisement_type`` (carousel only), ``status`` ``draft``, and
    the three spacing integers, and one background. Each spacing column
    is one value applied on every edge. The background is a kind plus
    optional color, gradient, and asset ref on this row. Create stores
    kind ``color`` and paper ``#F6F1E8``. Optional ``template_key``
    points at a restricted carousel generator such as
    ``spotmu_paper_v1``. Creating a theme does not render artifacts or
    bind a campaign. ``live``, non-default spacing, and other background
    kinds are stored only by a later partial patch. Elements, when any,
    live on ``theme_elements``. Creating a theme does not insert elements.
    """

    __tablename__ = "themes"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_themes_slug"),
        UniqueConstraint("template_key", name="uq_themes_template_key"),
        Index("ix_themes_created_by", "created_by"),
        Index("ix_themes_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    advertisement_type: Mapped[AdvertisementType] = mapped_column(
        ADVERTISEMENT_TYPE_ENUM,
        nullable=False,
    )
    template_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ThemeStatus] = mapped_column(
        THEME_STATUS_ENUM,
        nullable=False,
        default=ThemeStatus.DRAFT,
        server_default=ThemeStatus.DRAFT.value,
    )
    page_margin: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_PAGE_MARGIN,
        server_default=str(DEFAULT_PAGE_MARGIN),
    )
    element_gap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_ELEMENT_GAP,
        server_default=str(DEFAULT_ELEMENT_GAP),
    )
    element_margin: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_ELEMENT_MARGIN,
        server_default=str(DEFAULT_ELEMENT_MARGIN),
    )
    background_kind: Mapped[BackgroundKind] = mapped_column(
        BACKGROUND_KIND_ENUM,
        nullable=False,
        default=BackgroundKind.COLOR,
        server_default=BackgroundKind.COLOR.value,
    )
    background_color: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=DEFAULT_BACKGROUND_COLOR,
        server_default=DEFAULT_BACKGROUND_COLOR,
    )
    background_gradient: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    background_asset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_users.id"),
        nullable=True,
    )

    created_by_user: Mapped["OpsUser | None"] = relationship("OpsUser")
    elements: Mapped[list["ThemeElement"]] = relationship(
        "ThemeElement",
        back_populates="theme",
        cascade="all, delete-orphan",
    )
