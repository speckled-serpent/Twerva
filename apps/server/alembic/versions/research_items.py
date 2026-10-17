"""Add the research library.

Revision ID: research_items
Revises: albums_from_slides
Create Date: 2026-10-17

``research_items`` is one text document: a title, a slug, and a body.
``resource_files`` stays gone. This revision does not link a carousel.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops ``research_items`` and the rows in it. Albums and
carousels stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


RESEARCH_TITLE_CHECK_SQL: str = "btrim(title) <> '' AND btrim(slug) <> ''"
RESEARCH_BODY_CHECK_SQL: str = "char_length(body) <= 1000000"


revision: str = "research_items"
down_revision: str | None = "albums_from_slides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)


def upgrade() -> None:
    """Create ``research_items``."""

    op.create_table(
        "research_items",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
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
        sa.UniqueConstraint("slug", name="uq_research_items_slug"),
    )
    op.create_check_constraint("title", "research_items", RESEARCH_TITLE_CHECK_SQL)
    op.create_check_constraint("body", "research_items", RESEARCH_BODY_CHECK_SQL)


def downgrade() -> None:
    """Drop ``research_items``. Rows in that table go with it."""

    op.drop_table("research_items")
