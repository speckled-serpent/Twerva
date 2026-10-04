"""Add theme_elements. Full-width rows in a band. No coordinates.

Revision ID: theme_elements
Revises: themes_background
Create Date: 2026-10-04

One row is text or an image. Text requires a Spotmu source, family,
positive size, color, and alignment. Image requires a relative asset
ref and forbids text_source. The content check is named ``content``;
the metadata naming convention stores it as
``ck_theme_elements_content``. Does not add HTTP, layout, or upload.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa

from app.models.theme_element import THEME_ELEMENT_CONTENT_CHECK_SQL


revision: str = "theme_elements"
down_revision: str | None = "themes_background"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)

THEME_ELEMENT_BAND_ENUM: postgresql.ENUM = postgresql.ENUM(
    "top",
    "middle",
    "bottom",
    name="theme_element_band",
    create_type=False,
)
THEME_ELEMENT_CONTENT_KIND_ENUM: postgresql.ENUM = postgresql.ENUM(
    "text",
    "image",
    name="theme_element_content_kind",
    create_type=False,
)
THEME_ELEMENT_TEXT_SOURCE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "title",
    "interest_heading",
    "overview_bullets",
    "canonical_url",
    name="theme_element_text_source",
    create_type=False,
)
THEME_ELEMENT_ALIGNMENT_ENUM: postgresql.ENUM = postgresql.ENUM(
    "left",
    "center",
    "right",
    name="theme_element_alignment",
    create_type=False,
)


def upgrade() -> None:

    _create_theme_element_enum_types()
    _create_theme_elements_table()


def downgrade() -> None:

    op.drop_table("theme_elements")
    op.execute(sa.text("DROP TYPE theme_element_alignment"))
    op.execute(sa.text("DROP TYPE theme_element_text_source"))
    op.execute(sa.text("DROP TYPE theme_element_content_kind"))
    op.execute(sa.text("DROP TYPE theme_element_band"))


def _create_theme_element_enum_types() -> None:
    """Create the native Postgres enums used by theme_elements."""

    op.execute(
        sa.text(
            "CREATE TYPE theme_element_band AS ENUM "
            "('top', 'middle', 'bottom')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE theme_element_content_kind AS ENUM "
            "('text', 'image')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE theme_element_text_source AS ENUM "
            "('title', 'interest_heading', 'overview_bullets', 'canonical_url')"
        ),
    )
    op.execute(
        sa.text(
            "CREATE TYPE theme_element_alignment AS ENUM "
            "('left', 'center', 'right')"
        ),
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


def _boolean_style_column(column_name: str) -> sa.Column[object]:
    """Return a style flag that defaults to false."""

    style_column: sa.Column[object] = sa.Column(
        column_name,
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

    return style_column


def _create_theme_elements_table() -> None:
    """Create theme_elements with the content check and band order unique."""

    op.create_table(
        "theme_elements",
        _uuid_primary_key_column(),
        sa.Column("theme_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("band", THEME_ELEMENT_BAND_ENUM, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("content_kind", THEME_ELEMENT_CONTENT_KIND_ENUM, nullable=False),
        sa.Column("rectangle_color", sa.Text(), nullable=True),
        sa.Column("text_source", THEME_ELEMENT_TEXT_SOURCE_ENUM, nullable=True),
        sa.Column("font_family", sa.Text(), nullable=True),
        sa.Column("font_size", sa.Integer(), nullable=True),
        sa.Column("font_color", sa.Text(), nullable=True),
        _boolean_style_column("bold"),
        _boolean_style_column("italic"),
        _boolean_style_column("underline"),
        _boolean_style_column("strikethrough"),
        sa.Column("font_weight", sa.Integer(), nullable=True),
        sa.Column("alignment", THEME_ELEMENT_ALIGNMENT_ENUM, nullable=True),
        sa.Column("image_asset_ref", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            name="fk_theme_elements_theme_id_themes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_theme_elements"),
        sa.UniqueConstraint(
            "theme_id",
            "band",
            "sort_order",
            name="uq_theme_elements_theme_id_band_sort_order",
        ),
        sa.CheckConstraint(
            THEME_ELEMENT_CONTENT_CHECK_SQL,
            name="content",
        ),
    )
