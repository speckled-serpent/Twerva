"""Move slide images onto reusable albums.

Revision ID: albums_from_slides
Revises: skeletons_carousels_slides
Create Date: 2026-10-17

Each carousel that has slide images gets one album named after the
carousel. The image rows move onto that album. Paths and ids stay, so
the bytes are not copied. A slide that had an image points at that
album image. The Default carousel's packaged photos become the album
named Default, at a stable id. A carousel with no images gets no album.
Skeleton paths are not rewritten.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade puts every slide pointer back on ``slide_images`` with the
same id and path. An album image that no slide points at has nowhere
to live on the old table, so downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.carousels.default_carousel import default_library_album_id
from app.models.album import (
    ALBUM_IMAGE_BYTE_SIZE_CHECK_SQL,
    ALBUM_IMAGE_DIMENSIONS_CHECK_SQL,
    ALBUM_IMAGE_LICENSE_NOTE_CHECK_SQL,
    ALBUM_IMAGE_PATH_CHECK_SQL,
    ALBUM_IMAGE_POSITION_CHECK_SQL,
    ALBUM_IMAGE_SOURCE_CHECK_SQL,
    ALBUM_NAME_CHECK_SQL,
)


revision: str = "albums_from_slides"
down_revision: str | None = "skeletons_carousels_slides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)
MEDIA_TYPE_ENUM = ENUM(
    "svg",
    "png",
    "jpeg",
    name="slide_image_media_type",
    create_type=False,
)
LICENSE_ENUM = ENUM(
    "cc0",
    "public_domain",
    "owned",
    "licensed",
    name="slide_image_license",
    create_type=False,
)
INTAKE_ENUM = ENUM(
    "upload",
    "url",
    name="slide_image_intake",
    create_type=False,
)


def upgrade() -> None:
    """Add albums, move image rows, then drop ``slide_images``."""

    _create_album_tables()
    _add_pointers()
    _move_image_rows()
    op.drop_table("slide_images")


def downgrade() -> None:
    """Restore ``slide_images`` from the slide pointers, then drop albums."""

    _recreate_slide_images()
    _restore_slide_image_rows()
    op.drop_constraint(
        "fk_slides_album_image_id_album_images",
        "slides",
        type_="foreignkey",
    )
    op.drop_index("ix_slides_album_image_id", table_name="slides")
    op.drop_column("slides", "album_image_id")
    op.drop_constraint("fk_carousels_album_id_albums", "carousels", type_="foreignkey")
    op.drop_index("ix_carousels_album_id", table_name="carousels")
    op.drop_column("carousels", "album_id")
    op.drop_table("album_images")
    op.drop_table("albums")


def _create_album_tables() -> None:
    """Create ``albums`` and ``album_images`` with short check names."""

    op.create_table(
        "albums",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_albums_slug"),
    )
    op.create_check_constraint("name", "albums", ALBUM_NAME_CHECK_SQL)
    op.create_table(
        "album_images",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("album_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("license", LICENSE_ENUM, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "license_note",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("intake", INTAKE_ENUM, nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["album_id"],
            ["albums.id"],
            name="fk_album_images_album_id_albums",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("relative_path", name="uq_album_images_relative_path"),
        sa.UniqueConstraint(
            "album_id",
            "position",
            name="uq_album_images_album_id_position",
        ),
    )
    op.create_index("ix_album_images_album_id", "album_images", ["album_id"])
    op.create_check_constraint("position", "album_images", ALBUM_IMAGE_POSITION_CHECK_SQL)
    op.create_check_constraint("source", "album_images", ALBUM_IMAGE_SOURCE_CHECK_SQL)
    op.create_check_constraint("byte_size", "album_images", ALBUM_IMAGE_BYTE_SIZE_CHECK_SQL)
    op.create_check_constraint(
        "license_note",
        "album_images",
        ALBUM_IMAGE_LICENSE_NOTE_CHECK_SQL,
    )
    op.create_check_constraint(
        "dimensions",
        "album_images",
        ALBUM_IMAGE_DIMENSIONS_CHECK_SQL,
    )
    op.create_check_constraint(
        "relative_path",
        "album_images",
        ALBUM_IMAGE_PATH_CHECK_SQL,
    )


def _add_pointers() -> None:
    """Add nullable album pointers before the rows move."""

    op.add_column("carousels", sa.Column("album_id", UUID_COLUMN, nullable=True))
    op.add_column("slides", sa.Column("album_image_id", UUID_COLUMN, nullable=True))
    op.create_index("ix_carousels_album_id", "carousels", ["album_id"])
    op.create_index("ix_slides_album_image_id", "slides", ["album_image_id"])
    op.create_foreign_key(
        "fk_carousels_album_id_albums",
        "carousels",
        "albums",
        ["album_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_slides_album_image_id_album_images",
        "slides",
        "album_images",
        ["album_image_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _move_image_rows() -> None:
    """Create one album per carousel that has images and move the rows."""

    default_album_id: str = str(default_library_album_id())
    op.execute(
        sa.text(
            """
            INSERT INTO albums (id, name, slug, created_at, updated_at)
            SELECT
                CASE
                    WHEN carousels.slug = 'default'
                        THEN CAST(:default_album_id AS uuid)
                    ELSE gen_random_uuid()
                END,
                carousels.name,
                carousels.slug,
                now(),
                now()
            FROM carousels
            WHERE EXISTS (
                SELECT 1
                FROM slides
                JOIN slide_images ON slide_images.slide_id = slides.id
                WHERE slides.carousel_id = carousels.id
            )
            """
        ).bindparams(default_album_id=default_album_id),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO album_images (
                id,
                album_id,
                position,
                relative_path,
                media_type,
                byte_size,
                width,
                height,
                alt_text,
                license,
                source,
                license_note,
                intake,
                thumbnail_path,
                created_at,
                updated_at
            )
            SELECT
                slide_images.id,
                albums.id,
                (
                    ROW_NUMBER() OVER (
                        PARTITION BY slides.carousel_id
                        ORDER BY slides.position, slide_images.position, slide_images.id
                    ) - 1
                )::integer,
                slide_images.relative_path,
                slide_images.media_type,
                slide_images.byte_size,
                slide_images.width,
                slide_images.height,
                slide_images.alt_text,
                slide_images.license,
                slide_images.source,
                slide_images.license_note,
                slide_images.intake,
                slide_images.thumbnail_path,
                slide_images.created_at,
                slide_images.updated_at
            FROM slide_images
            JOIN slides ON slides.id = slide_images.slide_id
            JOIN carousels ON carousels.id = slides.carousel_id
            JOIN albums ON albums.slug = carousels.slug
            """
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE slides
            SET album_image_id = slide_images.id
            FROM slide_images
            WHERE slide_images.slide_id = slides.id
            """
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE carousels
            SET album_id = albums.id
            FROM albums
            WHERE albums.slug = carousels.slug
            """
        ),
    )


def _recreate_slide_images() -> None:
    """Recreate the pre-album image table. Rows are inserted next."""

    op.create_table(
        "slide_images",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slide_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("license", LICENSE_ENUM, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "license_note",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("intake", INTAKE_ENUM, nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["slide_id"],
            ["slides.id"],
            name="fk_slide_images_slide_id_slides",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("relative_path", name="uq_slide_images_relative_path"),
        sa.UniqueConstraint("slide_id", name="uq_slide_images_slide_id"),
        sa.UniqueConstraint(
            "slide_id",
            "position",
            name="uq_slide_images_slide_id_position",
        ),
    )
    op.create_index("ix_slide_images_slide_id", "slide_images", ["slide_id"])
    op.create_check_constraint("position", "slide_images", ALBUM_IMAGE_POSITION_CHECK_SQL)
    op.create_check_constraint("source", "slide_images", ALBUM_IMAGE_SOURCE_CHECK_SQL)
    op.create_check_constraint("byte_size", "slide_images", ALBUM_IMAGE_BYTE_SIZE_CHECK_SQL)
    op.create_check_constraint(
        "license_note",
        "slide_images",
        ALBUM_IMAGE_LICENSE_NOTE_CHECK_SQL,
    )
    op.create_check_constraint(
        "dimensions",
        "slide_images",
        ALBUM_IMAGE_DIMENSIONS_CHECK_SQL,
    )
    op.create_check_constraint(
        "relative_path",
        "slide_images",
        ALBUM_IMAGE_PATH_CHECK_SQL,
    )


def _restore_slide_image_rows() -> None:
    """Copy each slide pointer back onto ``slide_images``. Position is 0."""

    op.execute(
        sa.text(
            """
            INSERT INTO slide_images (
                id,
                slide_id,
                position,
                relative_path,
                media_type,
                byte_size,
                width,
                height,
                alt_text,
                license,
                source,
                license_note,
                intake,
                thumbnail_path,
                created_at,
                updated_at
            )
            SELECT
                album_images.id,
                slides.id,
                0,
                album_images.relative_path,
                album_images.media_type,
                album_images.byte_size,
                album_images.width,
                album_images.height,
                album_images.alt_text,
                album_images.license,
                album_images.source,
                album_images.license_note,
                album_images.intake,
                album_images.thumbnail_path,
                album_images.created_at,
                album_images.updated_at
            FROM slides
            JOIN album_images ON album_images.id = slides.album_image_id
            """
        ),
    )
