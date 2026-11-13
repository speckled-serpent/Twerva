"""Add the Final assembly tables.

Revision ID: carousel_final_assembly
Revises: slide_draft_batches
Create Date: 2026-11-13

``carousel_assemblies`` is one assembly for a carousel and generation.
``assembled_carousels`` is one reviewed carousel, status ``draft``.
``assembled_carousel_frames`` is one frozen frame. ``slide_id`` and
``album_image_id`` set null when the source row is deleted, and the
frame stays. Upgrade inserts no rows and does not update ``artifacts``,
``campaign_carousels``, slides, or ``generation_number``.

This row is what phase 8 attaches. It is not a generation snapshot,
and it is not ``campaign_carousels``.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops the frames, then the assembled carousels, then the
assemblies. PNG files on disk stay. ``ck_carousels_editor_step`` stays.

The revision id is 23 characters, inside ``varchar(64)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.carousel import (
    ASSEMBLED_CAROUSEL_STATUS_CHECK_SQL,
    ASSEMBLED_FRAME_BLOCK_REASON_CHECK_SQL,
    ASSEMBLED_POSITION_CHECK_SQL,
    CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
    CAROUSEL_ASSEMBLY_SLIDE_COUNT_CHECK_SQL,
)


revision: str = "carousel_final_assembly"
down_revision: str | None = "slide_draft_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)


def upgrade() -> None:
    """Create the assembly tables. Existing rows stay as they are."""

    _create_assembly_table()
    _create_assembled_carousel_table()
    _create_frame_table()


def downgrade() -> None:
    """Drop the frames, the assembled carousels, then the assemblies.

    Slides, albums, artifacts, and campaign carousels stay. PNG files
    on disk stay.
    """

    op.drop_table("assembled_carousel_frames")
    op.drop_table("assembled_carousels")
    op.drop_table("carousel_assemblies")


def _create_assembly_table() -> None:
    """One assembly per carousel and generation. No rows are inserted."""

    op.create_table(
        "carousel_assemblies",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("generation_number", sa.Integer(), nullable=False),
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
            name="fk_carousel_assemblies_carousel_id_carousels",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "generation_number",
            name="uq_carousel_assemblies_carousel_id_generation_number",
        ),
    )
    op.create_index(
        "ix_carousel_assemblies_carousel_id",
        "carousel_assemblies",
        ["carousel_id"],
    )
    op.create_check_constraint(
        "generation_number",
        "carousel_assemblies",
        CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
    )
    op.create_check_constraint(
        "slide_count",
        "carousel_assemblies",
        CAROUSEL_ASSEMBLY_SLIDE_COUNT_CHECK_SQL,
    )


def _create_assembled_carousel_table() -> None:
    """One draft carousel inside an assembly. No hashtag column."""

    op.create_table(
        "assembled_carousels",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("assembly_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("cta_url", sa.Text(), nullable=True),
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
            ["assembly_id"],
            ["carousel_assemblies.id"],
            name="fk_assembled_carousels_assembly_id_carousel_assemblies",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "assembly_id",
            "position",
            name="uq_assembled_carousels_assembly_id_position",
        ),
    )
    op.create_index(
        "ix_assembled_carousels_assembly_id",
        "assembled_carousels",
        ["assembly_id"],
    )
    op.create_check_constraint(
        "position",
        "assembled_carousels",
        ASSEMBLED_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "status",
        "assembled_carousels",
        ASSEMBLED_CAROUSEL_STATUS_CHECK_SQL,
    )


def _create_frame_table() -> None:
    """One frozen frame. Deleting the slide or the image clears the pointer."""

    op.create_table(
        "assembled_carousel_frames",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("assembled_carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("slide_id", UUID_COLUMN, nullable=True),
        sa.Column("album_image_id", UUID_COLUMN, nullable=True),
        sa.Column("asset_ref", sa.Text(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("block_detail", sa.Text(), nullable=True),
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
            ["assembled_carousel_id"],
            ["assembled_carousels.id"],
            name="fk_frames_assembled_carousel_id_assembled_carousels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["slide_id"],
            ["slides.id"],
            name="fk_assembled_carousel_frames_slide_id_slides",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["album_image_id"],
            ["album_images.id"],
            name="fk_assembled_carousel_frames_album_image_id_album_images",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "assembled_carousel_id",
            "position",
            name="uq_assembled_carousel_frames_assembled_carousel_id_position",
        ),
    )
    op.create_index(
        "ix_assembled_carousel_frames_assembled_carousel_id",
        "assembled_carousel_frames",
        ["assembled_carousel_id"],
    )
    op.create_index(
        "ix_assembled_carousel_frames_slide_id",
        "assembled_carousel_frames",
        ["slide_id"],
    )
    op.create_index(
        "ix_assembled_carousel_frames_album_image_id",
        "assembled_carousel_frames",
        ["album_image_id"],
    )
    op.create_check_constraint(
        "position",
        "assembled_carousel_frames",
        ASSEMBLED_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "block_reason",
        "assembled_carousel_frames",
        ASSEMBLED_FRAME_BLOCK_REASON_CHECK_SQL,
    )
