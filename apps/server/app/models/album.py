"""Reusable albums: a named set of images, shared across carousels later.

An album image keeps the license, source, alt, and path that used to live
on a slide. The bytes stay where they already are. A slide points at one
album image. A carousel may point at the album those images came from.
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
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
)


ALBUM_NAME_CHECK_SQL: str = "btrim(name) <> '' AND btrim(slug) <> ''"
ALBUM_IMAGE_POSITION_CHECK_SQL: str = "position >= 0"
ALBUM_IMAGE_SOURCE_CHECK_SQL: str = "btrim(source) <> ''"
ALBUM_IMAGE_BYTE_SIZE_CHECK_SQL: str = "byte_size > 0"
ALBUM_IMAGE_LICENSE_NOTE_CHECK_SQL: str = (
    "("
    "license <> 'licensed'::slide_image_license"
    " AND license_note = ''"
    ") OR ("
    "license = 'licensed'::slide_image_license"
    " AND btrim(license_note) <> ''"
    ")"
)
ALBUM_IMAGE_DIMENSIONS_CHECK_SQL: str = (
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
ALBUM_IMAGE_PATH_CHECK_SQL: str = (
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


class Album(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``albums``. A name, a slug, and ordered images."""

    __tablename__ = "albums"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_albums_slug"),
        CheckConstraint(ALBUM_NAME_CHECK_SQL, name="name"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)

    images: Mapped[list["AlbumImage"]] = relationship(
        "AlbumImage",
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="AlbumImage.position",
    )


class AlbumImage(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One image file in an album, with license and source."""

    __tablename__ = "album_images"
    __table_args__ = (
        UniqueConstraint("relative_path", name="uq_album_images_relative_path"),
        UniqueConstraint(
            "album_id",
            "position",
            name="uq_album_images_album_id_position",
        ),
        CheckConstraint(ALBUM_IMAGE_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(ALBUM_IMAGE_SOURCE_CHECK_SQL, name="source"),
        CheckConstraint(ALBUM_IMAGE_BYTE_SIZE_CHECK_SQL, name="byte_size"),
        CheckConstraint(ALBUM_IMAGE_LICENSE_NOTE_CHECK_SQL, name="license_note"),
        CheckConstraint(ALBUM_IMAGE_DIMENSIONS_CHECK_SQL, name="dimensions"),
        CheckConstraint(ALBUM_IMAGE_PATH_CHECK_SQL, name="relative_path"),
    )

    album_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("albums.id", ondelete="CASCADE"),
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

    album: Mapped[Album] = relationship("Album", back_populates="images")
