"""Rename themes, sources, and units to skeletons, carousels, and slides.

Revision ID: skeletons_carousels_slides
Revises: theme_element_text_optional
Create Date: 2026-10-17

``themes`` become ``skeletons``, ``sources`` become ``carousels``, and
``units`` become ``slides``. Child tables, columns, enum types, foreign
keys, unique constraints, checks, and standalone indexes move with them.
``campaign_carousels`` stays the run assembly. ``source_items`` and the
image provenance column ``source`` stay.

Checks created by earlier revisions may be stored once
(``ck_sources_name``) or twice (``ck_sources_ck_sources_name``), because
``op.create_check_constraint`` applies
``ck_%(table_name)s_%(constraint_name)s`` on top of a name that is
already prefixed. Upgrade renames whichever spelling is present and
fails when neither is. Downgrade restores the double-prefixed spelling
this chain created, except ``ck_theme_elements_content``, which the
previous revision normalized.

Rows are kept. Each statement is ``ALTER ... RENAME``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "skeletons_carousels_slides"
down_revision: str | None = "theme_element_text_optional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUM_RENAMES: tuple[tuple[str, str], ...] = (
    ("theme_status", "skeleton_status"),
    ("theme_element_alignment", "skeleton_element_alignment"),
    ("theme_element_band", "skeleton_element_band"),
    ("theme_element_content_kind", "skeleton_element_content_kind"),
    ("theme_element_text_source", "skeleton_element_text_source"),
    ("unit_image_intake", "slide_image_intake"),
    ("unit_image_license", "slide_image_license"),
    ("unit_image_media_type", "slide_image_media_type"),
    ("unit_text_status", "slide_text_status"),
)

TABLE_RENAMES: tuple[tuple[str, str], ...] = (
    ("themes", "skeletons"),
    ("theme_elements", "skeleton_elements"),
    ("sources", "carousels"),
    ("units", "slides"),
    ("unit_element_texts", "slide_element_texts"),
    ("unit_exclusions", "slide_exclusions"),
    ("unit_images", "slide_images"),
)

COLUMN_RENAMES: tuple[tuple[str, str, str], ...] = (
    ("campaigns", "theme_id", "skeleton_id"),
    ("campaigns", "source_id", "carousel_id"),
    ("skeleton_elements", "theme_id", "skeleton_id"),
    ("carousels", "theme_id", "skeleton_id"),
    ("slides", "source_id", "carousel_id"),
    ("slide_element_texts", "unit_id", "slide_id"),
    ("slide_element_texts", "theme_element_id", "skeleton_element_id"),
    ("slide_exclusions", "unit_id", "slide_id"),
    ("slide_exclusions", "excluded_unit_id", "excluded_slide_id"),
    ("slide_images", "unit_id", "slide_id"),
    ("campaign_carousel_slides", "unit_id", "slide_id"),
)

# (table, new name, old names). The first old name is what downgrade restores.
CONSTRAINT_RENAMES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("skeletons", "pk_skeletons", ("pk_themes",)),
    ("skeletons", "fk_skeletons_created_by_ops_users", ("fk_themes_created_by_ops_users",)),
    ("skeletons", "uq_skeletons_slug", ("uq_themes_slug",)),
    ("skeletons", "uq_skeletons_template_key", ("uq_themes_template_key",)),
    ("skeleton_elements", "pk_skeleton_elements", ("pk_theme_elements",)),
    (
        "skeleton_elements",
        "fk_skeleton_elements_skeleton_id_skeletons",
        ("fk_theme_elements_theme_id_themes",),
    ),
    (
        "skeleton_elements",
        "uq_skeleton_elements_skeleton_id_band_sort_order",
        ("uq_theme_elements_theme_id_band_sort_order",),
    ),
    (
        "skeleton_elements",
        "ck_skeleton_elements_content",
        ("ck_theme_elements_content",),
    ),
    (
        "skeleton_elements",
        "ck_skeleton_elements_name",
        ("ck_theme_elements_ck_theme_elements_name", "ck_theme_elements_name"),
    ),
    (
        "skeleton_elements",
        "ck_skeleton_elements_rectangle_style",
        (
            "ck_theme_elements_ck_theme_elements_rectangle_style",
            "ck_theme_elements_rectangle_style",
        ),
    ),
    ("carousels", "pk_carousels", ("pk_sources",)),
    ("carousels", "fk_carousels_skeleton_id_skeletons", ("fk_sources_theme_id_themes",)),
    ("carousels", "uq_carousels_slug", ("uq_sources_slug",)),
    (
        "carousels",
        "ck_carousels_name",
        ("ck_sources_ck_sources_name", "ck_sources_name"),
    ),
    ("slides", "pk_slides", ("pk_units",)),
    ("slides", "fk_slides_carousel_id_carousels", ("fk_units_source_id_sources",)),
    ("slides", "uq_slides_carousel_id_position", ("uq_units_source_id_position",)),
    (
        "slides",
        "ck_slides_name",
        ("ck_units_ck_units_name", "ck_units_name"),
    ),
    (
        "slides",
        "ck_slides_position",
        ("ck_units_ck_units_position", "ck_units_position"),
    ),
    ("slide_element_texts", "pk_slide_element_texts", ("pk_unit_element_texts",)),
    (
        "slide_element_texts",
        "fk_slide_element_texts_slide_id_slides",
        ("fk_unit_element_texts_unit_id_units",),
    ),
    (
        "slide_element_texts",
        "fk_slide_element_texts_skeleton_element_id_skeleton_elements",
        ("fk_unit_element_texts_theme_element_id_theme_elements",),
    ),
    (
        "slide_element_texts",
        "uq_slide_element_texts_slide_id_skeleton_element_id",
        ("uq_unit_element_texts_unit_id_theme_element_id",),
    ),
    ("slide_exclusions", "pk_slide_exclusions", ("pk_unit_exclusions",)),
    (
        "slide_exclusions",
        "fk_slide_exclusions_slide_id_slides",
        ("fk_unit_exclusions_unit_id_units",),
    ),
    (
        "slide_exclusions",
        "fk_slide_exclusions_excluded_slide_id_slides",
        ("fk_unit_exclusions_excluded_unit_id_units",),
    ),
    (
        "slide_exclusions",
        "uq_slide_exclusions_slide_id_excluded_slide_id",
        ("uq_unit_exclusions_unit_id_excluded_unit_id",),
    ),
    (
        "slide_exclusions",
        "ck_slide_exclusions_not_self",
        (
            "ck_unit_exclusions_ck_unit_exclusions_not_self",
            "ck_unit_exclusions_not_self",
        ),
    ),
    ("slide_images", "pk_slide_images", ("pk_unit_images",)),
    ("slide_images", "fk_slide_images_slide_id_slides", ("fk_unit_images_unit_id_units",)),
    ("slide_images", "uq_slide_images_relative_path", ("uq_unit_images_relative_path",)),
    ("slide_images", "uq_slide_images_slide_id", ("uq_unit_images_unit_id",)),
    (
        "slide_images",
        "uq_slide_images_slide_id_position",
        ("uq_unit_images_unit_id_position",),
    ),
    (
        "slide_images",
        "ck_slide_images_position",
        ("ck_unit_images_ck_unit_images_position", "ck_unit_images_position"),
    ),
    (
        "slide_images",
        "ck_slide_images_source",
        ("ck_unit_images_ck_unit_images_source", "ck_unit_images_source"),
    ),
    (
        "slide_images",
        "ck_slide_images_byte_size",
        ("ck_unit_images_ck_unit_images_byte_size", "ck_unit_images_byte_size"),
    ),
    (
        "slide_images",
        "ck_slide_images_license_note",
        ("ck_unit_images_ck_unit_images_license_note", "ck_unit_images_license_note"),
    ),
    (
        "slide_images",
        "ck_slide_images_dimensions",
        ("ck_unit_images_ck_unit_images_dimensions", "ck_unit_images_dimensions"),
    ),
    (
        "slide_images",
        "ck_slide_images_relative_path",
        ("ck_unit_images_ck_unit_images_relative_path", "ck_unit_images_relative_path"),
    ),
    (
        "campaigns",
        "fk_campaigns_skeleton_id_skeletons",
        ("fk_campaigns_theme_id_themes",),
    ),
    (
        "campaigns",
        "fk_campaigns_carousel_id_carousels",
        ("fk_campaigns_source_id_sources",),
    ),
    (
        "campaign_carousel_slides",
        "fk_campaign_carousel_slides_slide_id_slides",
        ("fk_campaign_carousel_slides_unit_id_units",),
    ),
    (
        "campaign_carousel_slides",
        "uq_campaign_carousel_slides_carousel_id_slide_id",
        ("uq_campaign_carousel_slides_carousel_id_unit_id",),
    ),
)

# Standalone indexes. Primary-key and unique indexes follow their constraints.
INDEX_RENAMES: tuple[tuple[str, str], ...] = (
    ("ix_themes_created_at", "ix_skeletons_created_at"),
    ("ix_themes_created_by", "ix_skeletons_created_by"),
    ("ix_sources_theme_id", "ix_carousels_skeleton_id"),
    ("ix_units_source_id", "ix_slides_carousel_id"),
    ("ix_unit_element_texts_unit_id", "ix_slide_element_texts_slide_id"),
    (
        "ix_unit_element_texts_theme_element_id",
        "ix_slide_element_texts_skeleton_element_id",
    ),
    ("ix_unit_exclusions_unit_id", "ix_slide_exclusions_slide_id"),
    ("ix_unit_exclusions_excluded_unit_id", "ix_slide_exclusions_excluded_slide_id"),
    ("ix_unit_images_unit_id", "ix_slide_images_slide_id"),
    ("ix_campaigns_theme_id", "ix_campaigns_skeleton_id"),
    ("ix_campaigns_source_id", "ix_campaigns_carousel_id"),
    ("ix_campaign_carousel_slides_unit_id", "ix_campaign_carousel_slides_slide_id"),
)


def upgrade() -> None:
    """Rename enums, tables, columns, constraints, then leftover indexes."""

    _rename_enums(forward=True)
    _rename_tables(forward=True)
    _rename_columns(forward=True)
    _rename_constraints(forward=True)
    _rename_indexes(forward=True)


def downgrade() -> None:
    """Restore the names from ``theme_element_text_optional``."""

    _rename_indexes(forward=False)
    _rename_constraints(forward=False)
    _rename_columns(forward=False)
    _rename_tables(forward=False)
    _rename_enums(forward=False)


def _rename_enums(forward: bool) -> None:
    """Rename Postgres enum types. Checks keep following the type oid."""

    pairs: tuple[tuple[str, str], ...] = ENUM_RENAMES if forward else tuple(
        (new_name, old_name) for old_name, new_name in ENUM_RENAMES
    )

    for old_name, new_name in pairs:
        op.execute(sa.text(f'ALTER TYPE "{old_name}" RENAME TO "{new_name}"'))


def _rename_tables(forward: bool) -> None:
    """Rename the seven content tables. Assembly tables stay."""

    pairs: tuple[tuple[str, str], ...] = TABLE_RENAMES if forward else tuple(
        (new_name, old_name) for old_name, new_name in reversed(TABLE_RENAMES)
    )

    for old_name, new_name in pairs:
        op.rename_table(old_name, new_name)


def _rename_columns(forward: bool) -> None:
    """Rename foreign-key columns. ``text_source`` and image ``source`` stay."""

    triples: tuple[tuple[str, str, str], ...] = COLUMN_RENAMES if forward else tuple(
        (table_name, new_name, old_name)
        for table_name, old_name, new_name in reversed(COLUMN_RENAMES)
    )

    for table_name, old_name, new_name in triples:
        op.alter_column(table_name, old_name, new_column_name=new_name)


def _rename_constraints(forward: bool) -> None:
    """Rename constraints in place. Unique and primary keys rename their indexes."""

    for table_name, new_name, old_names in CONSTRAINT_RENAMES:
        if forward:
            current_name: str = _existing_constraint_name(table_name, old_names)
            _rename_constraint(table_name, current_name, new_name)
            continue

        historical_name: str = old_names[0]
        _rename_constraint(table_name, new_name, historical_name)


def _rename_indexes(forward: bool) -> None:
    """Rename indexes that are not the backing index of a constraint."""

    pairs: tuple[tuple[str, str], ...] = INDEX_RENAMES if forward else tuple(
        (new_name, old_name) for old_name, new_name in INDEX_RENAMES
    )

    for old_name, new_name in pairs:
        if not _index_exists(old_name):
            if _index_exists(new_name):
                continue

            raise RuntimeError(f"Index {old_name} is missing and {new_name} is not present.")

        op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _existing_constraint_name(table_name: str, candidates: tuple[str, ...]) -> str:
    """Return the one candidate present on ``table_name``."""

    found_names: list[str] = []

    for candidate in candidates:
        if _constraint_exists(table_name, candidate):
            found_names.append(candidate)

    if len(found_names) != 1:
        raise RuntimeError(
            f"Expected one of {candidates} on {table_name}, found {found_names}.",
        )

    return found_names[0]


def _rename_constraint(table_name: str, old_name: str, new_name: str) -> None:
    """Rename one constraint. Missing names fail instead of being skipped."""

    if not _constraint_exists(table_name, old_name):
        raise RuntimeError(f"Constraint {old_name} is missing on {table_name}.")

    op.execute(
        sa.text(
            f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"',
        ),
    )


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    """True when ``constraint_name`` is attached to ``table_name``."""

    found = op.get_bind().execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint AS database_constraint
            JOIN pg_class AS database_table
              ON database_table.oid = database_constraint.conrelid
            JOIN pg_namespace AS database_namespace
              ON database_namespace.oid = database_table.relnamespace
            WHERE database_namespace.nspname = 'public'
              AND database_table.relname = :table_name
              AND database_constraint.conname = :constraint_name
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    ).scalar()

    return found is not None


def _index_exists(index_name: str) -> bool:
    """True when a public index has this name."""

    found = op.get_bind().execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class AS database_index
            JOIN pg_namespace AS database_namespace
              ON database_namespace.oid = database_index.relnamespace
            WHERE database_namespace.nspname = 'public'
              AND database_index.relkind = 'i'
              AND database_index.relname = :index_name
            """
        ),
        {"index_name": index_name},
    ).scalar()

    return found is not None
