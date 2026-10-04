"""Add one background per theme. Default color is paper #F6F1E8.

Revision ID: themes_background
Revises: themes_spacing
Create Date: 2026-10-04

``background_kind`` is picture, color, gradient, or texture. Color,
gradient, and asset ref stay nullable so a Draft may leave the payload
empty. Existing rows, including Spotmu Paper v1 and Spotmu Bold v1,
become kind ``color`` with ``#F6F1E8``. Does not render or upload.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "themes_background"
down_revision: str | None = "themes_spacing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKGROUND_KIND_ENUM: postgresql.ENUM = postgresql.ENUM(
    "picture",
    "color",
    "gradient",
    "texture",
    name="background_kind",
    create_type=False,
)

DEFAULT_BACKGROUND_COLOR: str = "#F6F1E8"
SEEDED_PAPER_THEME_NAME: str = "Spotmu Paper v1"
SEEDED_BOLD_THEME_NAME: str = "Spotmu Bold v1"


def upgrade() -> None:

    _create_background_kind_type()
    _add_nullable_background_columns()
    _backfill_existing_theme_backgrounds()
    _lock_background_kind_not_null()
    _default_background_color()


def downgrade() -> None:

    op.drop_column("themes", "background_asset_ref")
    op.drop_column("themes", "background_gradient")
    op.drop_column("themes", "background_color")
    op.drop_column("themes", "background_kind")
    op.execute(text("DROP TYPE background_kind"))


def _create_background_kind_type() -> None:
    """Create the native Postgres enum used by `themes.background_kind`."""

    op.execute(
        text(
            "CREATE TYPE background_kind AS ENUM "
            "('picture', 'color', 'gradient', 'texture')"
        ),
    )


def _add_nullable_background_columns() -> None:
    """Add nullable background columns so existing rows can be backfilled."""

    op.add_column(
        "themes",
        sa.Column("background_kind", BACKGROUND_KIND_ENUM, nullable=True),
    )
    op.add_column(
        "themes",
        sa.Column("background_color", sa.Text(), nullable=True),
    )
    op.add_column(
        "themes",
        sa.Column(
            "background_gradient",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "themes",
        sa.Column("background_asset_ref", sa.Text(), nullable=True),
    )


def _backfill_existing_theme_backgrounds() -> None:
    """Set every existing theme, including the two Spotmu seeds, to paper."""

    op.execute(
        text(
            f"""
            UPDATE themes
            SET background_kind = 'color'::background_kind,
                background_color = '{DEFAULT_BACKGROUND_COLOR}',
                background_gradient = NULL,
                background_asset_ref = NULL
            WHERE background_kind IS NULL
               OR name IN (
                   '{SEEDED_PAPER_THEME_NAME}',
                   '{SEEDED_BOLD_THEME_NAME}'
               )
            """
        ),
    )


def _lock_background_kind_not_null() -> None:
    """Require a kind and default new inserts to color."""

    op.alter_column(
        "themes",
        "background_kind",
        existing_type=BACKGROUND_KIND_ENUM,
        nullable=False,
        server_default=sa.text("'color'::background_kind"),
    )


def _default_background_color() -> None:
    """Default omitted color inserts to paper. Draft may still store null."""

    op.alter_column(
        "themes",
        "background_color",
        existing_type=sa.Text(),
        nullable=True,
        server_default=sa.text(f"'{DEFAULT_BACKGROUND_COLOR}'"),
    )
