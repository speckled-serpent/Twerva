"""Add content sources, units, and unit images. Seed Default.

Revision ID: sources_default_album
Revises: themes_element_rectangle
Create Date: 2026-10-14

Tables ``sources``, ``units``, ``unit_fields``, and ``unit_images``.
Seeds one album, slug ``default``, with six image-only units. Each
``relative_path`` stays ``theme-defaults/<filename>``. License and
source URL come from the packaged ``LICENSES.md``. Bytes stay in the
package. Does not update ``themes`` or ``theme_elements``.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

import sqlalchemy as sa

from app.models.content_source import (
    CONTENT_SOURCE_NAME_CHECK_SQL,
    UNIT_FIELD_TEXT_CHECK_SQL,
    UNIT_IMAGE_BYTE_SIZE_CHECK_SQL,
    UNIT_IMAGE_DIMENSIONS_CHECK_SQL,
    UNIT_IMAGE_LICENSE_NOTE_CHECK_SQL,
    UNIT_IMAGE_PATH_CHECK_SQL,
    UNIT_IMAGE_SOURCE_CHECK_SQL,
    UNIT_POSITION_CHECK_SQL,
)


revision: str = "sources_default_album"
down_revision: str | None = "themes_element_rectangle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)

CONTENT_SOURCE_KIND_ENUM: postgresql.ENUM = postgresql.ENUM(
    "album",
    "resource",
    name="content_source_kind",
    create_type=False,
)
UNIT_IMAGE_MEDIA_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "svg",
    "png",
    "jpeg",
    name="unit_image_media_type",
    create_type=False,
)
UNIT_IMAGE_LICENSE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "cc0",
    "public_domain",
    "owned",
    "licensed",
    name="unit_image_license",
    create_type=False,
)
UNIT_IMAGE_INTAKE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "upload",
    "url",
    name="unit_image_intake",
    create_type=False,
)


def upgrade() -> None:

    _create_content_source_enum_types()
    _create_sources_table()
    _create_units_table()
    _create_unit_fields_table()
    _create_unit_images_table()
    _seed_default_album()


def downgrade() -> None:

    op.drop_table("unit_images")
    op.drop_table("unit_fields")
    op.drop_table("units")
    op.drop_table("sources")
    op.execute(sa.text("DROP TYPE unit_image_intake"))
    op.execute(sa.text("DROP TYPE unit_image_license"))
    op.execute(sa.text("DROP TYPE unit_image_media_type"))
    op.execute(sa.text("DROP TYPE content_source_kind"))


def _create_content_source_enum_types() -> None:
    """Create the native Postgres enums used by content sources."""

    op.execute(
        sa.text(
            "CREATE TYPE content_source_kind AS ENUM ('album', 'resource')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE unit_image_media_type AS ENUM ('svg', 'png', 'jpeg')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE unit_image_license AS ENUM "
            "('cc0', 'public_domain', 'owned', 'licensed')"
        ),
    )
    op.execute(
        sa.text("CREATE TYPE unit_image_intake AS ENUM ('upload', 'url')"),
    )


def _uuid_primary_key_column() -> sa.Column[object]:
    """Return the shared UUID PK column (server default gen_random_uuid)."""

    uuid_primary_key_column: sa.Column[object] = sa.Column(
        "id",
        UUID_PRIMARY_KEY,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )

    return uuid_primary_key_column


def _created_at_column() -> sa.Column[object]:
    """Return a timezone-aware created_at column."""

    created_at_column: sa.Column[object] = sa.Column(
        "created_at",
        TIMESTAMPTZ,
        server_default=sa.text("now()"),
        nullable=False,
    )

    return created_at_column


def _updated_at_column() -> sa.Column[object]:
    """Return a timezone-aware updated_at column."""

    updated_at_column: sa.Column[object] = sa.Column(
        "updated_at",
        TIMESTAMPTZ,
        server_default=sa.text("now()"),
        nullable=False,
    )

    return updated_at_column


def _create_sources_table() -> None:
    """Create ``sources`` with a unique slug."""

    op.create_table(
        "sources",
        _uuid_primary_key_column(),
        sa.Column("kind", CONTENT_SOURCE_KIND_ENUM, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        _created_at_column(),
        _updated_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("slug", name="uq_sources_slug"),
        sa.CheckConstraint(CONTENT_SOURCE_NAME_CHECK_SQL, name="ck_sources_name"),
    )


def _create_units_table() -> None:
    """Create ``units``. Tags are a text array. Free text is optional."""

    op.create_table(
        "units",
        _uuid_primary_key_column(),
        sa.Column("source_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_units_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_units"),
        sa.UniqueConstraint(
            "source_id",
            "position",
            name="uq_units_source_id_position",
        ),
        sa.CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_units_position"),
    )
    op.create_index("ix_units_source_id", "units", ["source_id"])


def _create_unit_fields_table() -> None:
    """Create ``unit_fields``. Phase 1 seeds no rows."""

    op.create_table(
        "unit_fields",
        _uuid_primary_key_column(),
        sa.Column("unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_unit_fields_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unit_fields"),
        sa.UniqueConstraint(
            "unit_id",
            "position",
            name="uq_unit_fields_unit_id_position",
        ),
        sa.CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_unit_fields_position"),
        sa.CheckConstraint(UNIT_FIELD_TEXT_CHECK_SQL, name="ck_unit_fields_text"),
    )
    op.create_index("ix_unit_fields_unit_id", "unit_fields", ["unit_id"])


def _create_unit_images_table() -> None:
    """Create ``unit_images`` with license, source, and path checks."""

    op.create_table(
        "unit_images",
        _uuid_primary_key_column(),
        sa.Column("unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", UNIT_IMAGE_MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("license", UNIT_IMAGE_LICENSE_ENUM, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "license_note",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("intake", UNIT_IMAGE_INTAKE_ENUM, nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_unit_images_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unit_images"),
        sa.UniqueConstraint("relative_path", name="uq_unit_images_relative_path"),
        sa.UniqueConstraint(
            "unit_id",
            "position",
            name="uq_unit_images_unit_id_position",
        ),
        sa.CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_unit_images_position"),
        sa.CheckConstraint(UNIT_IMAGE_SOURCE_CHECK_SQL, name="ck_unit_images_source"),
        sa.CheckConstraint(
            UNIT_IMAGE_BYTE_SIZE_CHECK_SQL,
            name="ck_unit_images_byte_size",
        ),
        sa.CheckConstraint(
            UNIT_IMAGE_LICENSE_NOTE_CHECK_SQL,
            name="ck_unit_images_license_note",
        ),
        sa.CheckConstraint(
            UNIT_IMAGE_DIMENSIONS_CHECK_SQL,
            name="ck_unit_images_dimensions",
        ),
        sa.CheckConstraint(UNIT_IMAGE_PATH_CHECK_SQL, name="ck_unit_images_relative_path"),
    )
    op.create_index("ix_unit_images_unit_id", "unit_images", ["unit_id"])


def _seed_default_album() -> None:
    """Insert Default and six image-only units. Leave theme rows alone."""

    from app.sources.default_album import (
        DEFAULT_ALBUM_SLUG,
        DefaultUnitSeed,
        default_album_source_id,
        default_unit_seeds,
    )
    from app.themes.default_images import DEFAULT_ALBUM_NAME

    database_connection: Connection = op.get_bind()
    source_id: str = str(default_album_source_id())
    database_connection.execute(
        sa.text(
            """
            INSERT INTO sources (id, kind, name, slug)
            VALUES (
                CAST(:source_id AS uuid),
                CAST(:kind AS content_source_kind),
                :name,
                :slug
            )
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {
            "source_id": source_id,
            "kind": "album",
            "name": DEFAULT_ALBUM_NAME,
            "slug": DEFAULT_ALBUM_SLUG,
        },
    )

    for seed in default_unit_seeds():
        unit_seed: DefaultUnitSeed = seed
        database_connection.execute(
            sa.text(
                """
                INSERT INTO units (id, source_id, position, free_text, tags)
                VALUES (
                    CAST(:unit_id AS uuid),
                    CAST(:source_id AS uuid),
                    :position,
                    NULL,
                    '{}'::text[]
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "unit_id": str(unit_seed.unit_id),
                "source_id": source_id,
                "position": unit_seed.position,
            },
        )
        database_connection.execute(
            sa.text(
                """
                INSERT INTO unit_images (
                    id,
                    unit_id,
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
                    thumbnail_path
                )
                VALUES (
                    CAST(:image_id AS uuid),
                    CAST(:unit_id AS uuid),
                    :position,
                    :relative_path,
                    CAST(:media_type AS unit_image_media_type),
                    :byte_size,
                    :width,
                    :height,
                    NULL,
                    CAST(:image_license AS unit_image_license),
                    :source_url,
                    '',
                    CAST(:intake AS unit_image_intake),
                    NULL
                )
                ON CONFLICT (relative_path) DO NOTHING
                """
            ),
            {
                "image_id": str(unit_seed.image_id),
                "unit_id": str(unit_seed.unit_id),
                "position": unit_seed.position,
                "relative_path": unit_seed.relative_path,
                "media_type": "jpeg",
                "byte_size": unit_seed.byte_size,
                "width": unit_seed.width,
                "height": unit_seed.height,
                "image_license": unit_seed.image_license.value,
                "source_url": unit_seed.source_url,
                "intake": "upload",
            },
        )
