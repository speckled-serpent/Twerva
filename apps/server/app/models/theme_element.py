"""One full-width element stacked in a theme band. No coordinates."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    THEME_ELEMENT_ALIGNMENT_ENUM,
    THEME_ELEMENT_BAND_ENUM,
    THEME_ELEMENT_CONTENT_KIND_ENUM,
    THEME_ELEMENT_TEXT_SOURCE_ENUM,
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
)


if TYPE_CHECKING:
    from app.models.theme import Theme


IMAGE_ASSET_REF_IS_RELATIVE_SQL: str = (
    "btrim(image_asset_ref) = image_asset_ref"
    " AND image_asset_ref <> ''"
    " AND strpos(image_asset_ref, '..') = 0"
    " AND strpos(image_asset_ref, ':') = 0"
    " AND strpos(image_asset_ref, chr(92)) = 0"
    " AND left(image_asset_ref, 1) <> '/'"
    " AND ("
    "lower(right(image_asset_ref, 4)) IN ('.svg', '.png', '.jpg')"
    " OR lower(right(image_asset_ref, 5)) = '.jpeg'"
    ")"
)

THEME_ELEMENT_CONTENT_CHECK_SQL: str = (
    "("
    "("
    "content_kind = 'text'::theme_element_content_kind"
    " AND text_source IS NOT NULL"
    " AND font_family IS NOT NULL"
    " AND btrim(font_family) <> ''"
    " AND font_size > 0"
    " AND font_color IS NOT NULL"
    " AND btrim(font_color) <> ''"
    " AND alignment IS NOT NULL"
    ")"
    " OR "
    "("
    "content_kind = 'image'::theme_element_content_kind"
    " AND text_source IS NULL"
    " AND image_asset_ref IS NOT NULL"
    ")"
    ")"
    " AND (font_weight IS NULL OR (font_weight >= 1 AND font_weight <= 1000))"
    " AND (font_size IS NULL OR font_size > 0)"
    " AND (image_asset_ref IS NULL OR ("
    f"{IMAGE_ASSET_REF_IS_RELATIVE_SQL}"
    "))"
)


class ThemeElement(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `theme_elements`.

    Every element is the full content width of its theme. There is no
    ``x``, ``y``, or ``width`` column. ``rectangle_color`` null means the
    rectangle is clear. ``text`` requires a Spotmu ``text_source``, a
    non-blank family and color, a positive ``font_size``, and an
    ``alignment``. ``image`` requires ``image_asset_ref`` (relative path,
    no ``..``, no scheme, suffix ``.svg`` / ``.png`` / ``.jpg`` /
    ``.jpeg``) and forbids ``text_source``. Style booleans default false.
    ``font_weight`` is optional, from 1 through 1000.
    ``rectangle_opacity`` is 0 through 100 and defaults to 100.
    ``rectangle_radius`` is pixels from 0 through 10000 and defaults to 0.
    A null ``rectangle_color`` is still clear. This table does not
    measure text or read image bytes.
    """

    __tablename__ = "theme_elements"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "band",
            "sort_order",
            name="uq_theme_elements_theme_id_band_sort_order",
        ),
        CheckConstraint(
            THEME_ELEMENT_CONTENT_CHECK_SQL,
            name="content",
        ),
        CheckConstraint(
            "rectangle_opacity >= 0 AND rectangle_opacity <= 100"
            " AND rectangle_radius >= 0 AND rectangle_radius <= 10000",
            name="rectangle_style",
        ),
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
    )
    band: Mapped[ThemeElementBand] = mapped_column(
        THEME_ELEMENT_BAND_ENUM,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_kind: Mapped[ThemeElementContentKind] = mapped_column(
        THEME_ELEMENT_CONTENT_KIND_ENUM,
        nullable=False,
    )
    rectangle_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    rectangle_opacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default=text("100"),
    )
    rectangle_radius: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    text_source: Mapped[ThemeElementTextSource | None] = mapped_column(
        THEME_ELEMENT_TEXT_SOURCE_ENUM,
        nullable=True,
    )
    font_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    font_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    bold: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    italic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    underline: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    strikethrough: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    font_weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alignment: Mapped[ThemeElementAlignment | None] = mapped_column(
        THEME_ELEMENT_ALIGNMENT_ENUM,
        nullable=True,
    )
    image_asset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    theme: Mapped["Theme"] = relationship(
        "Theme",
        back_populates="elements",
    )
