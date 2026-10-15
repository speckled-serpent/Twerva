"""Bind every source to a theme. Drop album versus resource.

Revision ID: sources_theme_bound
Revises: sources_resource_files
Create Date: 2026-10-15

``sources.theme_id`` is required. ``kind`` and ``resource_files`` go
away. Each unit gains a name and keeps its id. A unit holds one image
row. Resource sources are deleted. Other sources without a theme are
deleted once none of their image paths are stored on a theme or an
artifact. A stored path stops the upgrade. The Default album stays and
is bound to Spotmu Paper v1 when that theme exists, otherwise the
oldest theme.
"""

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

import sqlalchemy as sa

from app.models.content_source import (
    RESOURCE_FILE_BYTE_SIZE_CHECK_SQL,
    RESOURCE_FILE_FILENAME_CHECK_SQL,
    RESOURCE_FILE_PATH_CHECK_SQL,
    RESOURCE_FILE_PROVENANCE_CHECK_SQL,
    UNIT_NAME_CHECK_SQL,
)
from app.sources.default_album import (
    DEFAULT_ALBUM_SLUG,
    DEFAULT_ALBUM_THEME_ID,
    default_album_source_id,
    default_unit_display_name,
    default_unit_seeds,
)
from app.sources.editing import collect_used_paths


revision: str = "sources_theme_bound"
down_revision: str | None = "sources_resource_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
CONTENT_SOURCE_KIND_ENUM: postgresql.ENUM = postgresql.ENUM(
    "album",
    "resource",
    name="content_source_kind",
    create_type=False,
)
RESOURCE_FILE_MEDIA_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "markdown",
    "plain",
    name="resource_file_media_type",
    create_type=False,
)
STORED_PATH_REFUSAL: str = (
    "Refusing to delete image paths still stored on a theme or an artifact"
)


def upgrade() -> None:

    op.add_column("sources", sa.Column("theme_id", UUID_PRIMARY_KEY, nullable=True))
    op.add_column("units", sa.Column("name", sa.Text(), nullable=True))
    database_connection: Connection = op.get_bind()
    _remove_sources_that_cannot_fit(database_connection)
    _collapse_units_to_one_image(database_connection)
    _name_remaining_units(database_connection)
    _bind_default_album(database_connection)
    _require_every_source_theme(database_connection)
    op.alter_column("sources", "theme_id", nullable=False)
    op.create_foreign_key(
        "fk_sources_theme_id_themes",
        "sources",
        "themes",
        ["theme_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_sources_theme_id", "sources", ["theme_id"])
    op.alter_column("units", "name", nullable=False)
    op.create_check_constraint("ck_units_name", "units", UNIT_NAME_CHECK_SQL)
    op.create_unique_constraint(
        "uq_unit_images_unit_id",
        "unit_images",
        ["unit_id"],
    )
    op.drop_column("sources", "kind")
    op.drop_table("resource_files")
    op.execute(sa.text("DROP TYPE content_source_kind"))
    op.execute(sa.text("DROP TYPE resource_file_media_type"))


def downgrade() -> None:

    op.execute(
        sa.text(
            "CREATE TYPE resource_file_media_type AS ENUM ('markdown', 'plain')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE content_source_kind AS ENUM ('album', 'resource')"
        ),
    )
    _recreate_resource_files_table()
    op.add_column(
        "sources",
        sa.Column(
            "kind",
            CONTENT_SOURCE_KIND_ENUM,
            nullable=False,
            server_default="album",
        ),
    )
    op.alter_column("sources", "kind", server_default=None)
    op.drop_constraint("uq_unit_images_unit_id", "unit_images", type_="unique")
    op.drop_constraint("ck_units_name", "units", type_="check")
    op.drop_column("units", "name")
    op.drop_index("ix_sources_theme_id", table_name="sources")
    op.drop_constraint("fk_sources_theme_id_themes", "sources", type_="foreignkey")
    op.drop_column("sources", "theme_id")


def _remove_sources_that_cannot_fit(database_connection: Connection) -> None:
    """Delete resource rows and albums that have no theme and no stored path."""

    used_paths: set[str] = _stored_image_paths(database_connection)
    default_source_id: str = str(default_album_source_id())
    source_rows = database_connection.execute(
        sa.text("SELECT id::text, kind, slug FROM sources"),
    ).fetchall()

    for source_row in source_rows:
        source_id: str = str(source_row[0])
        source_slug: str = str(source_row[2])

        if source_id == default_source_id or source_slug == DEFAULT_ALBUM_SLUG:
            continue

        image_paths: set[str] = _image_paths_for_source(database_connection, source_id)
        blocked_paths: set[str] = image_paths.intersection(used_paths)

        if len(blocked_paths) > 0:
            _refuse_stored_paths(blocked_paths)

        database_connection.execute(
            sa.text("DELETE FROM sources WHERE id = CAST(:source_id AS uuid)"),
            {"source_id": source_id},
        )


def _collapse_units_to_one_image(database_connection: Connection) -> None:
    """Keep one image row per unit. A second stored path stops the upgrade."""

    used_paths: set[str] = _stored_image_paths(database_connection)
    image_rows = database_connection.execute(
        sa.text(
            """
            SELECT id::text, unit_id::text, position, relative_path
            FROM unit_images
            ORDER BY unit_id, position, id
            """
        ),
    ).fetchall()
    images_by_unit: dict[str, list[tuple[str, str]]] = {}

    for image_row in image_rows:
        unit_id: str = str(image_row[1])
        image_pair: tuple[str, str] = (str(image_row[0]), str(image_row[3]))
        unit_images: list[tuple[str, str]] = images_by_unit.setdefault(unit_id, [])
        unit_images.append(image_pair)

    for unit_images in images_by_unit.values():

        if len(unit_images) < 2:
            continue

        stored_on_unit: list[tuple[str, str]] = [
            image_pair
            for image_pair in unit_images
            if image_pair[1] in used_paths
        ]

        if len(stored_on_unit) > 1:
            _refuse_stored_paths({image_pair[1] for image_pair in stored_on_unit})

        kept_image_id: str = (
            stored_on_unit[0][0] if len(stored_on_unit) == 1 else unit_images[0][0]
        )

        for image_id, relative_path in unit_images:

            if image_id == kept_image_id:
                continue

            if relative_path in used_paths:
                _refuse_stored_paths({relative_path})

            database_connection.execute(
                sa.text("DELETE FROM unit_images WHERE id = CAST(:image_id AS uuid)"),
                {"image_id": image_id},
            )


def _name_remaining_units(database_connection: Connection) -> None:
    """Fill unit names. Default photos use the packaged filename."""

    names_by_unit_id: dict[str, str] = {
        str(seed.unit_id): default_unit_display_name(seed.filename)
        for seed in default_unit_seeds()
    }
    unit_rows = database_connection.execute(
        sa.text("SELECT id::text, position FROM units"),
    ).fetchall()

    for unit_row in unit_rows:
        unit_id: str = str(unit_row[0])
        position: int = int(unit_row[1])
        unit_name: str = names_by_unit_id.get(unit_id, f"Unit {position + 1}")
        database_connection.execute(
            sa.text(
                """
                UPDATE units
                SET name = :unit_name
                WHERE id = CAST(:unit_id AS uuid)
                """
            ),
            {"unit_id": unit_id, "unit_name": unit_name},
        )


def _bind_default_album(database_connection: Connection) -> None:
    """Point the Default album at Paper v1, or the oldest theme."""

    default_source_id: str = str(default_album_source_id())
    existing_default = database_connection.execute(
        sa.text(
            """
            SELECT id::text
            FROM sources
            WHERE id = CAST(:source_id AS uuid) OR slug = :slug
            """
        ),
        {"source_id": default_source_id, "slug": DEFAULT_ALBUM_SLUG},
    ).fetchone()

    if existing_default is None:

        return

    theme_id: str = _theme_id_for_default_album(database_connection)
    database_connection.execute(
        sa.text(
            """
            UPDATE sources
            SET theme_id = CAST(:theme_id AS uuid)
            WHERE id = CAST(:source_id AS uuid) OR slug = :slug
            """
        ),
        {
            "theme_id": theme_id,
            "source_id": default_source_id,
            "slug": DEFAULT_ALBUM_SLUG,
        },
    )


def _require_every_source_theme(database_connection: Connection) -> None:
    """Stop when a source still has no theme."""

    missing_theme = database_connection.execute(
        sa.text("SELECT slug FROM sources WHERE theme_id IS NULL"),
    ).fetchall()

    if len(missing_theme) == 0:

        return

    missing_slugs: str = ", ".join(str(row[0]) for row in missing_theme)

    raise RuntimeError(f"A source still has no theme: {missing_slugs}")


def _theme_id_for_default_album(database_connection: Connection) -> str:
    """Prefer the seeded Paper theme. Otherwise use the oldest theme."""

    paper_theme = database_connection.execute(
        sa.text("SELECT id::text FROM themes WHERE id = CAST(:theme_id AS uuid)"),
        {"theme_id": str(DEFAULT_ALBUM_THEME_ID)},
    ).fetchone()

    if paper_theme is not None:

        return str(paper_theme[0])

    oldest_theme = database_connection.execute(
        sa.text(
            """
            SELECT id::text
            FROM themes
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ),
    ).fetchone()

    if oldest_theme is None:
        raise RuntimeError(
            "The Default album needs a theme, and no theme exists.",
        )

    return str(oldest_theme[0])


def _stored_image_paths(database_connection: Connection) -> set[str]:
    """Return image paths stored on a theme background, element, or artifact."""

    background_rows = database_connection.execute(
        sa.text(
            """
            SELECT background_asset_ref
            FROM themes
            WHERE background_asset_ref IS NOT NULL
            """
        ),
    ).fetchall()
    element_rows = database_connection.execute(
        sa.text(
            """
            SELECT image_asset_ref
            FROM theme_elements
            WHERE image_asset_ref IS NOT NULL
            """
        ),
    ).fetchall()
    slide_rows = database_connection.execute(
        sa.text("SELECT slides FROM artifacts WHERE slides IS NOT NULL"),
    ).fetchall()
    background_refs: list[str | None] = [row[0] for row in background_rows]
    element_refs: list[str | None] = [row[0] for row in element_rows]
    candidate_paths: set[str] = set()

    for stored_path in background_refs:

        if isinstance(stored_path, str) and stored_path != "":
            candidate_paths.add(stored_path)

    for stored_path in element_refs:

        if isinstance(stored_path, str) and stored_path != "":
            candidate_paths.add(stored_path)

    artifact_slide_rows: list[object] = []

    for slide_row in slide_rows:
        parsed_slides: object = _parse_slides(slide_row[0])
        artifact_slide_rows.append(parsed_slides)
        candidate_paths.update(_asset_refs_in_slides(parsed_slides))

    return collect_used_paths(
        candidate_paths,
        background_refs,
        element_refs,
        artifact_slide_rows,
    )


def _image_paths_for_source(
    database_connection: Connection,
    source_id: str,
) -> set[str]:
    """Return unit image paths that belong to one source."""

    image_rows = database_connection.execute(
        sa.text(
            """
            SELECT unit_images.relative_path
            FROM unit_images
            JOIN units ON units.id = unit_images.unit_id
            WHERE units.source_id = CAST(:source_id AS uuid)
            """
        ),
        {"source_id": source_id},
    ).fetchall()
    image_paths: set[str] = {str(row[0]) for row in image_rows}

    return image_paths


def _refuse_stored_paths(blocked_paths: set[str]) -> None:
    """Abort the upgrade without deleting a stored image path."""

    ordered_paths: str = ", ".join(sorted(blocked_paths))

    raise RuntimeError(f"{STORED_PATH_REFUSAL}: {ordered_paths}")


def _parse_slides(slides_value: object) -> object:
    """Return artifact slides as JSON, or the original value."""

    if not isinstance(slides_value, str):

        return slides_value

    parsed_slides: object = json.loads(slides_value)

    return parsed_slides


def _asset_refs_in_slides(slides_value: object) -> set[str]:
    """Return asset_ref strings found in one slides value."""

    found_paths: set[str] = set()

    if not isinstance(slides_value, list):

        return found_paths

    for slide in slides_value:

        if not isinstance(slide, dict):
            continue

        asset_ref: object = slide.get("asset_ref")

        if isinstance(asset_ref, str) and asset_ref != "":
            found_paths.add(asset_ref)

    return found_paths


def _recreate_resource_files_table() -> None:
    """Restore an empty resource_files table for the previous revision."""

    op.create_table(
        "resource_files",
        sa.Column("source_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", RESOURCE_FILE_MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_resource_files_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", name="pk_resource_files"),
        sa.UniqueConstraint(
            "relative_path",
            name="uq_resource_files_relative_path",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_PROVENANCE_CHECK_SQL,
            name="ck_resource_files_provenance",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_FILENAME_CHECK_SQL,
            name="ck_resource_files_original_filename",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_BYTE_SIZE_CHECK_SQL,
            name="ck_resource_files_byte_size",
        ),
        sa.CheckConstraint(RESOURCE_FILE_PATH_CHECK_SQL, name="ck_resource_files_path"),
    )
