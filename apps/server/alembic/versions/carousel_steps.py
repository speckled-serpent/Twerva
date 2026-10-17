"""Add generation number, editor step, and the research link.

Revision ID: carousel_steps
Revises: research_items
Create Date: 2026-10-17

``generation_number`` starts at 1. ``editor_step`` remembers the last
open step: 0 Basic, 2 Content, or 3 Slides. Existing carousels,
including Default, open on Slides. Research attaches as an ordered
list in ``carousel_research_items``. There is no ``research_id``
column. This revision does not insert research links and does not
change albums, inspiration, rules, or slide image pointers.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops the join table and the two columns. Albums, slides,
and ``research_items`` stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.carousel import (
    CAROUSEL_EDITOR_STEP_CHECK_SQL,
    CAROUSEL_EDITOR_STEP_DEFAULT,
    CAROUSEL_GENERATION_CHECK_SQL,
    CAROUSEL_GENERATION_NUMBER_DEFAULT,
    CAROUSEL_RESEARCH_POSITION_CHECK_SQL,
)


revision: str = "carousel_steps"
down_revision: str | None = "research_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)


def upgrade() -> None:
    """Add the step columns and an empty ordered research link."""

    _add_carousel_step_columns()
    _backfill_existing_carousels()
    op.create_check_constraint(
        "generation_number",
        "carousels",
        CAROUSEL_GENERATION_CHECK_SQL,
    )
    op.create_check_constraint(
        "editor_step",
        "carousels",
        CAROUSEL_EDITOR_STEP_CHECK_SQL,
    )
    _create_research_link_table()


def downgrade() -> None:
    """Drop the research link and the two step columns.

    Rows in ``carousel_research_items`` go with the table. Album
    pointers, slide pointers, and ``research_items`` stay.
    """

    op.drop_table("carousel_research_items")
    op.drop_column("carousels", "editor_step")
    op.drop_column("carousels", "generation_number")


def _add_carousel_step_columns() -> None:
    """Add the two integers. The server default fills existing rows."""

    op.add_column(
        "carousels",
        sa.Column(
            "generation_number",
            sa.Integer(),
            nullable=False,
            server_default=str(CAROUSEL_GENERATION_NUMBER_DEFAULT),
        ),
    )
    op.add_column(
        "carousels",
        sa.Column(
            "editor_step",
            sa.Integer(),
            nullable=False,
            server_default=str(CAROUSEL_EDITOR_STEP_DEFAULT),
        ),
    )


def _backfill_existing_carousels() -> None:
    """Set every carousel, including Default, to generation 1 on Slides."""

    op.execute(
        sa.text(
            """
            UPDATE carousels
            SET generation_number = :generation_number,
                editor_step = :editor_step
            """
        ).bindparams(
            generation_number=CAROUSEL_GENERATION_NUMBER_DEFAULT,
            editor_step=CAROUSEL_EDITOR_STEP_DEFAULT,
        ),
    )


def _create_research_link_table() -> None:
    """Create the ordered join. Upgrade inserts no rows."""

    op.create_table(
        "carousel_research_items",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("research_item_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["carousel_id"],
            ["carousels.id"],
            name="fk_carousel_research_items_carousel_id_carousels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["research_item_id"],
            ["research_items.id"],
            name="fk_carousel_research_items_research_item_id_research_items",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "research_item_id",
            name="uq_carousel_research_items_carousel_id_research_item_id",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_carousel_research_items_carousel_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_research_items_carousel_id",
        "carousel_research_items",
        ["carousel_id"],
    )
    op.create_index(
        "ix_carousel_research_items_research_item_id",
        "carousel_research_items",
        ["research_item_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_research_items",
        CAROUSEL_RESEARCH_POSITION_CHECK_SQL,
    )
