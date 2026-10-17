"""One full-width element stacked in a skeleton band. No coordinates."""

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
    SKELETON_ELEMENT_ALIGNMENT_ENUM,
    SKELETON_ELEMENT_BAND_ENUM,
    SKELETON_ELEMENT_CONTENT_KIND_ENUM,
    SKELETON_ELEMENT_TEXT_SOURCE_ENUM,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
)


if TYPE_CHECKING:
    from app.models.skeleton import Skeleton


SKELETON_ELEMENT_NAME_CHECK_SQL: str = "btrim(name) <> ''"

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

SKELETON_ELEMENT_CONTENT_CHECK_SQL: str = (
    "("
    "("
    "content_kind = 'text'::skeleton_element_content_kind"
    " AND font_family IS NOT NULL"
    " AND btrim(font_family) <> ''"
    " AND font_size > 0"
    " AND font_color IS NOT NULL"
    " AND btrim(font_color) <> ''"
    " AND alignment IS NOT NULL"
    ")"
    " OR "
    "("
    "content_kind = 'image'::skeleton_element_content_kind"
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


class SkeletonElement(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `skeleton_elements`.

    Every element is the full content width of its skeleton. There is no
    ``x``, ``y``, or ``width`` column. ``name`` is the operator's label
    for the element and cannot be blank. ``rectangle_color`` null means
    the rectangle is clear. ``text`` requires a non-blank family and
    color, a positive ``font_size``, and an ``alignment``. ``text_source``
    may be null: slide text is stored by element id and labeled by
    ``name``. Spotmu preview still reads ``text_source`` when it is set.
    ``image`` requires ``image_asset_ref`` (relative path, no ``..``, no
    scheme, suffix ``.svg`` / ``.png`` / ``.jpg`` / ``.jpeg``) and forbids
    ``text_source``. Style booleans default false.
    ``font_weight`` is optional, from 1 through 1000.
    ``rectangle_opacity`` is 0 through 100 and defaults to 100.
    ``rectangle_radius`` is pixels from 0 through 10000 and defaults to 0.
    A null ``rectangle_color`` is still clear. This table does not
    measure text or read image bytes.
    """

    __tablename__ = "skeleton_elements"
    __table_args__ = (
        UniqueConstraint(
            "skeleton_id",
            "band",
            "sort_order",
            name="uq_skeleton_elements_skeleton_id_band_sort_order",
        ),
        CheckConstraint(
            SKELETON_ELEMENT_CONTENT_CHECK_SQL,
            name="content",
        ),
        CheckConstraint(
            "rectangle_opacity >= 0 AND rectangle_opacity <= 100"
            " AND rectangle_radius >= 0 AND rectangle_radius <= 10000",
            name="rectangle_style",
        ),
        CheckConstraint(
            SKELETON_ELEMENT_NAME_CHECK_SQL,
            name="name",
        ),
    )

    skeleton_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeletons.id", ondelete="CASCADE"),
        nullable=False,
    )
    band: Mapped[SkeletonElementBand] = mapped_column(
        SKELETON_ELEMENT_BAND_ENUM,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_kind: Mapped[SkeletonElementContentKind] = mapped_column(
        SKELETON_ELEMENT_CONTENT_KIND_ENUM,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
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
    text_source: Mapped[SkeletonElementTextSource | None] = mapped_column(
        SKELETON_ELEMENT_TEXT_SOURCE_ENUM,
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
    alignment: Mapped[SkeletonElementAlignment | None] = mapped_column(
        SKELETON_ELEMENT_ALIGNMENT_ENUM,
        nullable=True,
    )
    image_asset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    skeleton: Mapped["Skeleton"] = relationship(
        "Skeleton",
        back_populates="elements",
    )
