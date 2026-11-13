"""Add the review batch for one press of Generate.

Revision ID: slide_draft_batches
Revises: carousel_instructions_drop_guidance
Create Date: 2026-11-13

``slide_draft_batches`` stores one generated set: ``pending``,
``accepted``, or ``discarded``. One carousel holds one pending row.
``slides.draft_batch_id`` points at that row and is set null when the
batch is deleted, so the slides stay. Upgrade inserts no rows and does
not update ``text_status``, ``draft_value``, ``album_image_id``, or
``generation_number``.

This table is the review state for one press of Generate. It is not
the phase 8 snapshot, and it is not ``campaign_carousels``.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops ``draft_batch_id`` and then the table. Albums,
research, instructions, and slides stay.

The revision id is 19 characters, inside ``varchar(64)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.carousel import (
    SLIDE_DRAFT_BATCH_SLIDE_COUNT_CHECK_SQL,
    SLIDE_DRAFT_BATCH_STATUS_CHECK_SQL,
)


revision: str = "slide_draft_batches"
down_revision: str | None = "carousel_instructions_drop_guidance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)


def upgrade() -> None:
    """Create the batch table and the nullable slide pointer.

    Existing slides stay as they are. No batch row is inserted.
    """

    _create_batch_table()
    _add_slide_pointer()


def downgrade() -> None:
    """Drop the slide pointer, then the batch table.

    Albums, research, instructions, and slides stay.
    """

    op.drop_constraint(
        "fk_slides_draft_batch_id_slide_draft_batches",
        "slides",
        type_="foreignkey",
    )
    op.drop_index("ix_slides_draft_batch_id", table_name="slides")
    op.drop_column("slides", "draft_batch_id")
    op.drop_table("slide_draft_batches")


def _create_batch_table() -> None:
    """Create the review rows. One pending row per carousel."""

    op.create_table(
        "slide_draft_batches",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("slide_count", sa.Integer(), nullable=False),
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
            ["carousel_id"],
            ["carousels.id"],
            name="fk_slide_draft_batches_carousel_id_carousels",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_slide_draft_batches_carousel_id",
        "slide_draft_batches",
        ["carousel_id"],
    )
    op.create_index(
        "uq_slide_draft_batches_one_pending_carousel",
        "slide_draft_batches",
        ["carousel_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_check_constraint(
        "status",
        "slide_draft_batches",
        SLIDE_DRAFT_BATCH_STATUS_CHECK_SQL,
    )
    op.create_check_constraint(
        "slide_count",
        "slide_draft_batches",
        SLIDE_DRAFT_BATCH_SLIDE_COUNT_CHECK_SQL,
    )


def _add_slide_pointer() -> None:
    """Point a slide at its batch. Deleting the batch leaves the slide."""

    op.add_column("slides", sa.Column("draft_batch_id", UUID_COLUMN, nullable=True))
    op.create_index("ix_slides_draft_batch_id", "slides", ["draft_batch_id"])
    op.create_foreign_key(
        "fk_slides_draft_batch_id_slide_draft_batches",
        "slides",
        "slide_draft_batches",
        ["draft_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
