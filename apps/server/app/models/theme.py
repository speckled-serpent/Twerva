"""Theme — visual styling for carousel advertisements (short video later)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    ADVERTISEMENT_TYPE_ENUM,
    THEME_STATUS_ENUM,
    AdvertisementType,
    ThemeStatus,
)


if TYPE_CHECKING:
    from app.models.ops_user import OpsUser


class Theme(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `themes`.

    Create stores a name, a unique slug derived from that name,
    ``advertisement_type`` (carousel only), and ``status`` ``draft``.
    Optional ``template_key`` points at a restricted carousel generator
    such as ``spotmu_paper_v1``. Creating a theme does not render
    artifacts or bind a campaign. ``live`` is stored only by a later
    partial patch.
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_users.id"),
        nullable=True,
    )

    created_by_user: Mapped["OpsUser | None"] = relationship("OpsUser")
