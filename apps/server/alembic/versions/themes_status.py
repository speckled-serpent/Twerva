"""Add themes.status (draft, live), default draft.

Revision ID: themes_status
Revises: themes_create
Create Date: 2026-10-03

Existing rows, including the seeded Spotmu Paper v1 and Spotmu Bold v1
themes, become ``draft``. Create stores ``draft``; a partial PATCH may
later set ``live``. Does not change spacing, background, or elements.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "themes_status"
down_revision: str | None = "themes_create"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THEME_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "draft",
    "live",
    name="theme_status",
    create_type=False,
)

SEEDED_PAPER_THEME_NAME: str = "Spotmu Paper v1"
SEEDED_BOLD_THEME_NAME: str = "Spotmu Bold v1"


def upgrade() -> None:

    _create_theme_status_type()
    _add_themes_status_column()
    _backfill_existing_themes_as_draft()
    _lock_themes_status_not_null()


def downgrade() -> None:

    op.drop_column("themes", "status")
    op.execute(text("DROP TYPE theme_status"))


def _create_theme_status_type() -> None:
    """Create the native Postgres enum used by `themes.status`."""

    op.execute(text("CREATE TYPE theme_status AS ENUM ('draft', 'live')"))


def _add_themes_status_column() -> None:
    """Add a nullable status column so existing rows can be backfilled."""

    op.add_column(
        "themes",
        sa.Column("status", THEME_STATUS_ENUM, nullable=True),
    )


def _backfill_existing_themes_as_draft() -> None:
    """Set every existing theme, including the two Spotmu seeds, to draft."""

    op.execute(
        text(
            f"""
            UPDATE themes
            SET status = 'draft'::theme_status
            WHERE status IS NULL
               OR name IN (
                   '{SEEDED_PAPER_THEME_NAME}',
                   '{SEEDED_BOLD_THEME_NAME}'
               )
            """
        ),
    )


def _lock_themes_status_not_null() -> None:
    """Require status and default new inserts to draft."""

    op.alter_column(
        "themes",
        "status",
        existing_type=THEME_STATUS_ENUM,
        nullable=False,
        server_default=sa.text("'draft'::theme_status"),
    )
