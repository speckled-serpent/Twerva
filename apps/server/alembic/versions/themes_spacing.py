"""Add theme spacing integers, default 96 / 0 / 0.

Revision ID: themes_spacing
Revises: themes_status
Create Date: 2026-10-04

``page_margin``, ``element_gap``, and ``element_margin`` are one integer
each, applied on every edge. Existing rows, including Spotmu Paper v1
and Spotmu Bold v1, receive 96, 0, and 0. Negatives are rejected by the
API. Does not draw frames or store elements.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

import sqlalchemy as sa


revision: str = "themes_spacing"
down_revision: str | None = "themes_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_PAGE_MARGIN: int = 96
DEFAULT_ELEMENT_GAP: int = 0
DEFAULT_ELEMENT_MARGIN: int = 0

SEEDED_PAPER_THEME_NAME: str = "Spotmu Paper v1"
SEEDED_BOLD_THEME_NAME: str = "Spotmu Bold v1"


def upgrade() -> None:

    _add_nullable_spacing_columns()
    _backfill_existing_theme_spacing()
    _lock_spacing_columns_not_null()


def downgrade() -> None:

    op.drop_column("themes", "element_margin")
    op.drop_column("themes", "element_gap")
    op.drop_column("themes", "page_margin")


def _add_nullable_spacing_columns() -> None:
    """Add nullable spacing columns so existing rows can be backfilled."""

    op.add_column(
        "themes",
        sa.Column("page_margin", sa.Integer(), nullable=True),
    )
    op.add_column(
        "themes",
        sa.Column("element_gap", sa.Integer(), nullable=True),
    )
    op.add_column(
        "themes",
        sa.Column("element_margin", sa.Integer(), nullable=True),
    )


def _backfill_existing_theme_spacing() -> None:
    """Set every existing theme, including the two Spotmu seeds, to defaults."""

    op.execute(
        text(
            f"""
            UPDATE themes
            SET page_margin = {DEFAULT_PAGE_MARGIN},
                element_gap = {DEFAULT_ELEMENT_GAP},
                element_margin = {DEFAULT_ELEMENT_MARGIN}
            WHERE page_margin IS NULL
               OR element_gap IS NULL
               OR element_margin IS NULL
               OR name IN (
                   '{SEEDED_PAPER_THEME_NAME}',
                   '{SEEDED_BOLD_THEME_NAME}'
               )
            """
        ),
    )


def _lock_spacing_columns_not_null() -> None:
    """Require the three spacing columns and default new inserts."""

    _lock_spacing_column("page_margin", DEFAULT_PAGE_MARGIN)
    _lock_spacing_column("element_gap", DEFAULT_ELEMENT_GAP)
    _lock_spacing_column("element_margin", DEFAULT_ELEMENT_MARGIN)


def _lock_spacing_column(column_name: str, default_value: int) -> None:
    """Set one spacing column not null with a constant server default."""

    op.alter_column(
        "themes",
        column_name,
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text(str(default_value)),
    )
