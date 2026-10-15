"""Content sources: one kind of source, bound to a required theme.

A unit keeps its id, has a name, and holds at most one image. Themes
still store a concrete image path. They do not reference these rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    UNIT_IMAGE_INTAKE_ENUM,
    UNIT_IMAGE_LICENSE_ENUM,
    UNIT_IMAGE_MEDIA_TYPE_ENUM,
    UnitImageIntake,
    UnitImageLicense,
    UnitImageMediaType,
)


CONTENT_SOURCE_NAME_CHECK_SQL: str = (
    "btrim(name) <> '' AND btrim(slug) <> ''"
)
UNIT_POSITION_CHECK_SQL: str = "position >= 0"
UNIT_NAME_CHECK_SQL: str = "btrim(name) <> ''"
UNIT_FIELD_TEXT_CHECK_SQL: str = "btrim(label) <> '' AND btrim(value) <> ''"
UNIT_IMAGE_SOURCE_CHECK_SQL: str = "btrim(source) <> ''"
UNIT_IMAGE_BYTE_SIZE_CHECK_SQL: str = "byte_size > 0"
UNIT_IMAGE_LICENSE_NOTE_CHECK_SQL: str = (
    "("
    "license <> 'licensed'::unit_image_license"
    " AND license_note = ''"
    ") OR ("
    "license = 'licensed'::unit_image_license"
    " AND btrim(license_note) <> ''"
    ")"
)
UNIT_IMAGE_DIMENSIONS_CHECK_SQL: str = (
    "("
    "media_type = 'svg'::unit_image_media_type"
    " AND width IS NULL"
    " AND height IS NULL"
    " AND thumbnail_path IS NULL"
    ") OR ("
    "media_type <> 'svg'::unit_image_media_type"
    " AND width > 0"
    " AND height > 0"
    ")"
)
RESOURCE_FILE_MAX_BYTES: int = 2 * 1024 * 1024
RESOURCE_FILE_PROVENANCE_CHECK_SQL: str = "btrim(provenance) <> ''"
RESOURCE_FILE_FILENAME_CHECK_SQL: str = (
    "btrim(original_filename) <> ''"
    " AND strpos(original_filename, '/') = 0"
    " AND strpos(original_filename, chr(92)) = 0"
)
RESOURCE_FILE_BYTE_SIZE_CHECK_SQL: str = (
    f"byte_size > 0 AND byte_size <= {RESOURCE_FILE_MAX_BYTES}"
)
RESOURCE_FILE_PATH_CHECK_SQL: str = (
    "("
    "media_type = 'markdown'::resource_file_media_type"
    " AND relative_path = ('resources/' || source_id::text || '/body.md')"
    ") OR ("
    "media_type = 'plain'::resource_file_media_type"
    " AND relative_path = ('resources/' || source_id::text || '/body.txt')"
    ")"
)
UNIT_IMAGE_PATH_CHECK_SQL: str = (
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


class ContentSource(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``sources``. Every source requires one theme."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_sources_slug"),
        CheckConstraint(CONTENT_SOURCE_NAME_CHECK_SQL, name="ck_sources_name"),
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)

    units: Mapped[list["Unit"]] = relationship(
        "Unit",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Unit.position",
    )


class Unit(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One piece of content inside a source. The id stays; the name is set."""

    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "position",
            name="uq_units_source_id_position",
        ),
        CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_units_position"),
        CheckConstraint(UNIT_NAME_CHECK_SQL, name="ck_units_name"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )

    source: Mapped[ContentSource] = relationship("ContentSource", back_populates="units")
    fields: Mapped[list["UnitField"]] = relationship(
        "UnitField",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="UnitField.position",
    )
    images: Mapped[list["UnitImage"]] = relationship(
        "UnitImage",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="UnitImage.position",
    )


class UnitField(Base, UuidPrimaryKeyMixin):
    """One labeled value on a unit, such as name or price."""

    __tablename__ = "unit_fields"
    __table_args__ = (
        UniqueConstraint(
            "unit_id",
            "position",
            name="uq_unit_fields_unit_id_position",
        ),
        CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_unit_fields_position"),
        CheckConstraint(UNIT_FIELD_TEXT_CHECK_SQL, name="ck_unit_fields_text"),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    unit: Mapped[Unit] = relationship("Unit", back_populates="fields")


class UnitImage(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One image file that belongs to a unit, with license and source."""

    __tablename__ = "unit_images"
    __table_args__ = (
        UniqueConstraint("relative_path", name="uq_unit_images_relative_path"),
        UniqueConstraint("unit_id", name="uq_unit_images_unit_id"),
        UniqueConstraint(
            "unit_id",
            "position",
            name="uq_unit_images_unit_id_position",
        ),
        CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_unit_images_position"),
        CheckConstraint(UNIT_IMAGE_SOURCE_CHECK_SQL, name="ck_unit_images_source"),
        CheckConstraint(UNIT_IMAGE_BYTE_SIZE_CHECK_SQL, name="ck_unit_images_byte_size"),
        CheckConstraint(
            UNIT_IMAGE_LICENSE_NOTE_CHECK_SQL,
            name="ck_unit_images_license_note",
        ),
        CheckConstraint(
            UNIT_IMAGE_DIMENSIONS_CHECK_SQL,
            name="ck_unit_images_dimensions",
        ),
        CheckConstraint(UNIT_IMAGE_PATH_CHECK_SQL, name="ck_unit_images_relative_path"),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[UnitImageMediaType] = mapped_column(
        UNIT_IMAGE_MEDIA_TYPE_ENUM,
        nullable=False,
    )
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[UnitImageLicense] = mapped_column(
        UNIT_IMAGE_LICENSE_ENUM,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    license_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    intake: Mapped[UnitImageIntake] = mapped_column(
        UNIT_IMAGE_INTAKE_ENUM,
        nullable=False,
    )
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    unit: Mapped[Unit] = relationship("Unit", back_populates="images")
