"""Content carousels: one kind of carousel, bound to a required skeleton.

A slide keeps its id, has a name, and holds at most one image. Its text
is one value per text element on that skeleton. Generated text stays a
draft until a person accepts it. ``slide_exclusions`` stores the other
slide ids it cannot be shown with. The carousel stores inspiration and
rules for that draft. Skeletons still store a concrete image path. They
do not reference these rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    SLIDE_IMAGE_INTAKE_ENUM,
    SLIDE_IMAGE_LICENSE_ENUM,
    SLIDE_IMAGE_MEDIA_TYPE_ENUM,
    SLIDE_TEXT_STATUS_ENUM,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)


CAROUSEL_NAME_CHECK_SQL: str = (
    "btrim(name) <> '' AND btrim(slug) <> ''"
)
SLIDE_POSITION_CHECK_SQL: str = "position >= 0"
SLIDE_NAME_CHECK_SQL: str = "btrim(name) <> ''"
SLIDE_FIELD_TEXT_CHECK_SQL: str = "btrim(label) <> '' AND btrim(value) <> ''"
SLIDE_IMAGE_SOURCE_CHECK_SQL: str = "btrim(source) <> ''"
SLIDE_IMAGE_BYTE_SIZE_CHECK_SQL: str = "byte_size > 0"
SLIDE_IMAGE_LICENSE_NOTE_CHECK_SQL: str = (
    "("
    "license <> 'licensed'::slide_image_license"
    " AND license_note = ''"
    ") OR ("
    "license = 'licensed'::slide_image_license"
    " AND btrim(license_note) <> ''"
    ")"
)
SLIDE_IMAGE_DIMENSIONS_CHECK_SQL: str = (
    "("
    "media_type = 'svg'::slide_image_media_type"
    " AND width IS NULL"
    " AND height IS NULL"
    " AND thumbnail_path IS NULL"
    ") OR ("
    "media_type <> 'svg'::slide_image_media_type"
    " AND width > 0"
    " AND height > 0"
    ")"
)
RESOURCE_FILE_MAX_BYTES: int = 2 * 1024 * 1024
SLIDE_IMAGE_PATH_CHECK_SQL: str = (
    "btrim(relative_path) = relative_path"
    " AND relative_path <> ''"
    " AND strpos(relative_path, '..') = 0"
    " AND strpos(relative_path, ':') = 0"
    " AND strpos(relative_path, chr(92)) = 0"
    " AND left(relative_path, 1) <> '/'"
    " AND ("
    "lower(right(relative_path, 4)) IN ('.svg', '.png', '.jpg')"
    " OR lower(right(relative_path, 5)) = '.jpeg'"
    ")"
)


class Carousel(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``carousels``. Every carousel requires one skeleton."""

    __tablename__ = "carousels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_carousels_slug"),
        CheckConstraint(CAROUSEL_NAME_CHECK_SQL, name="name"),
    )

    skeleton_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeletons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    inspiration: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    rules: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    slides: Mapped[list["Slide"]] = relationship(
        "Slide",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="Slide.position",
    )


class Slide(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One piece of content inside a carousel. The id stays; the name is set."""

    __tablename__ = "slides"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_slides_carousel_id_position",
        ),
        CheckConstraint(SLIDE_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(SLIDE_NAME_CHECK_SQL, name="name"),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    text_status: Mapped[SlideTextStatus] = mapped_column(
        SLIDE_TEXT_STATUS_ENUM,
        nullable=False,
        default=SlideTextStatus.LIVE,
        server_default="live",
    )

    carousel: Mapped[Carousel] = relationship("Carousel", back_populates="slides")
    element_texts: Mapped[list["SlideElementText"]] = relationship(
        "SlideElementText",
        back_populates="slide",
        cascade="all, delete-orphan",
    )
    images: Mapped[list["SlideImage"]] = relationship(
        "SlideImage",
        back_populates="slide",
        cascade="all, delete-orphan",
        order_by="SlideImage.position",
    )
    exclusions: Mapped[list["SlideExclusion"]] = relationship(
        "SlideExclusion",
        foreign_keys="SlideExclusion.slide_id",
        back_populates="slide",
        cascade="all, delete-orphan",
    )


class SlideExclusion(Base, UuidPrimaryKeyMixin):
    """One other slide this slide cannot be shown with.

    The pair is stored in both directions. Deleting either slide removes
    both rows because each foreign key cascades.
    """

    __tablename__ = "slide_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "slide_id",
            "excluded_slide_id",
            name="uq_slide_exclusions_slide_id_excluded_slide_id",
        ),
        CheckConstraint(
            "slide_id <> excluded_slide_id",
            name="not_self",
        ),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    excluded_slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    slide: Mapped[Slide] = relationship(
        "Slide",
        foreign_keys=[slide_id],
        back_populates="exclusions",
    )
    excluded_slide: Mapped[Slide] = relationship(
        "Slide",
        foreign_keys=[excluded_slide_id],
    )


class SlideElementText(Base, UuidPrimaryKeyMixin):
    """The text a slide stores for one skeleton text element."""

    __tablename__ = "slide_element_texts"
    __table_args__ = (
        UniqueConstraint(
            "slide_id",
            "skeleton_element_id",
            name="uq_slide_element_texts_slide_id_skeleton_element_id",
        ),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skeleton_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeleton_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    draft_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    slide: Mapped[Slide] = relationship("Slide", back_populates="element_texts")


class SlideImage(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One image file that belongs to a slide, with license and source."""

    __tablename__ = "slide_images"
    __table_args__ = (
        UniqueConstraint("relative_path", name="uq_slide_images_relative_path"),
        UniqueConstraint("slide_id", name="uq_slide_images_slide_id"),
        UniqueConstraint(
            "slide_id",
            "position",
            name="uq_slide_images_slide_id_position",
        ),
        CheckConstraint(SLIDE_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(SLIDE_IMAGE_SOURCE_CHECK_SQL, name="source"),
        CheckConstraint(SLIDE_IMAGE_BYTE_SIZE_CHECK_SQL, name="byte_size"),
        CheckConstraint(
            SLIDE_IMAGE_LICENSE_NOTE_CHECK_SQL,
            name="license_note",
        ),
        CheckConstraint(
            SLIDE_IMAGE_DIMENSIONS_CHECK_SQL,
            name="dimensions",
        ),
        CheckConstraint(SLIDE_IMAGE_PATH_CHECK_SQL, name="relative_path"),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[SlideImageMediaType] = mapped_column(
        SLIDE_IMAGE_MEDIA_TYPE_ENUM,
        nullable=False,
    )
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[SlideImageLicense] = mapped_column(
        SLIDE_IMAGE_LICENSE_ENUM,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    license_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    intake: Mapped[SlideImageIntake] = mapped_column(
        SLIDE_IMAGE_INTAKE_ENUM,
        nullable=False,
    )
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    slide: Mapped[Slide] = relationship("Slide", back_populates="images")
