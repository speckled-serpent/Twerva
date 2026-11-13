"""Add generation snapshots and hang Final assemblies on them.

Revision ID: carousel_generations
Revises: carousel_final_assembly
Create Date: 2026-11-13

``carousel_generations`` is the snapshot for one carousel and
generation number. Child rows copy the instruction bodies, the
album's image ids, the research title and body, and the slides.
``carousel_assemblies.generation_id`` points at that snapshot.
Upgrade does not change ``generation_number``, working slides,
instruction rows, research links, album files, ``artifacts``, or
``campaign_carousels``. It does not copy PNG files.

Downgrade drops ``generation_id`` first, then the snapshot tables
from child to parent. Assemblies, frames, and the carousel's
``generation_number`` stay. The number is not set back to 1.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

The revision id is 20 characters, inside ``varchar(64)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.models.carousel import (
    CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
    CAROUSEL_GENERATION_EXCLUSION_NOT_SELF_CHECK_SQL,
    CAROUSEL_GENERATION_POSITION_CHECK_SQL,
    CAROUSEL_GENERATION_SLIDE_NAME_CHECK_SQL,
    CAROUSEL_INSTRUCTION_BODY_CHECK_SQL,
)
from app.models.research_item import RESEARCH_BODY_CHECK_SQL


revision: str = "carousel_generations"
down_revision: str | None = "carousel_final_assembly"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)
SLIDE_TEXT_STATUS_COLUMN = ENUM(name="slide_text_status", create_type=False)


def upgrade() -> None:
    """Create the snapshot tables and attach each existing assembly."""

    _create_generation_table()
    _create_instruction_table()
    _create_research_table()
    _create_image_table()
    _create_slide_table()
    _create_slide_text_table()
    _create_exclusion_table()
    _backfill_generations()
    _attach_assemblies()


def downgrade() -> None:
    """Drop the assembly link, then the snapshot tables.

    Assemblies, frames, slides, and ``carousels.generation_number``
    stay. PNG files on disk stay.
    """

    op.drop_constraint(
        "fk_carousel_assemblies_generation_id_carousel_generations",
        "carousel_assemblies",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_carousel_assemblies_generation_id",
        "carousel_assemblies",
        type_="unique",
    )
    op.drop_column("carousel_assemblies", "generation_id")
    op.drop_table("carousel_generation_slide_exclusions")
    op.drop_table("carousel_generation_slide_texts")
    op.drop_table("carousel_generation_slides")
    op.drop_table("carousel_generation_images")
    op.drop_table("carousel_generation_research")
    op.drop_table("carousel_generation_instructions")
    op.drop_table("carousel_generations")


def _create_generation_table() -> None:
    """One snapshot header per carousel and generation number."""

    op.create_table(
        "carousel_generations",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("generation_number", sa.Integer(), nullable=False),
        sa.Column("album_id", UUID_COLUMN, nullable=True),
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
            name="fk_carousel_generations_carousel_id_carousels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["album_id"],
            ["albums.id"],
            name="fk_carousel_generations_album_id_albums",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "generation_number",
            name="uq_carousel_generations_carousel_id_generation_number",
        ),
    )
    op.create_index(
        "ix_carousel_generations_carousel_id",
        "carousel_generations",
        ["carousel_id"],
    )
    op.create_index(
        "ix_carousel_generations_album_id",
        "carousel_generations",
        ["album_id"],
    )
    op.create_check_constraint(
        "generation_number",
        "carousel_generations",
        CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
    )


def _create_instruction_table() -> None:
    """Copied instruction bodies. An empty body is kept."""

    op.create_table(
        "carousel_generation_instructions",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
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
            ["generation_id"],
            ["carousel_generations.id"],
            name="fk_cgen_instructions_generation_id_cgen",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_instructions_generation_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_generation_instructions_generation_id",
        "carousel_generation_instructions",
        ["generation_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_generation_instructions",
        CAROUSEL_GENERATION_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "body",
        "carousel_generation_instructions",
        CAROUSEL_INSTRUCTION_BODY_CHECK_SQL,
    )


def _create_research_table() -> None:
    """Copied research title and body. The library id may clear later."""

    op.create_table(
        "carousel_generation_research",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("research_item_id", UUID_COLUMN, nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["carousel_generations.id"],
            name="fk_cgen_research_generation_id_cgen",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["research_item_id"],
            ["research_items.id"],
            name="fk_cgen_research_research_item_id_research_items",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_research_generation_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_generation_research_generation_id",
        "carousel_generation_research",
        ["generation_id"],
    )
    op.create_index(
        "ix_carousel_generation_research_research_item_id",
        "carousel_generation_research",
        ["research_item_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_generation_research",
        CAROUSEL_GENERATION_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "body",
        "carousel_generation_research",
        RESEARCH_BODY_CHECK_SQL,
    )


def _create_image_table() -> None:
    """Ordered album image ids. Deleting an image clears the id."""

    op.create_table(
        "carousel_generation_images",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("album_image_id", UUID_COLUMN, nullable=True),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["carousel_generations.id"],
            name="fk_cgen_images_generation_id_cgen",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["album_image_id"],
            ["album_images.id"],
            name="fk_cgen_images_album_image_id_album_images",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_images_generation_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_generation_images_generation_id",
        "carousel_generation_images",
        ["generation_id"],
    )
    op.create_index(
        "ix_carousel_generation_images_album_image_id",
        "carousel_generation_images",
        ["album_image_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_generation_images",
        CAROUSEL_GENERATION_POSITION_CHECK_SQL,
    )


def _create_slide_table() -> None:
    """Copied slides. ``source_slide_id`` points at the working slide."""

    op.create_table(
        "carousel_generation_slides",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("text_status", SLIDE_TEXT_STATUS_COLUMN, nullable=False),
        sa.Column("album_image_id", UUID_COLUMN, nullable=True),
        sa.Column("source_slide_id", UUID_COLUMN, nullable=True),
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
            ["generation_id"],
            ["carousel_generations.id"],
            name="fk_cgen_slides_generation_id_cgen",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["album_image_id"],
            ["album_images.id"],
            name="fk_cgen_slides_album_image_id_album_images",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_slide_id"],
            ["slides.id"],
            name="fk_cgen_slides_source_slide_id_slides",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_slides_generation_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_generation_slides_generation_id",
        "carousel_generation_slides",
        ["generation_id"],
    )
    op.create_index(
        "ix_carousel_generation_slides_album_image_id",
        "carousel_generation_slides",
        ["album_image_id"],
    )
    op.create_index(
        "ix_carousel_generation_slides_source_slide_id",
        "carousel_generation_slides",
        ["source_slide_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_generation_slides",
        CAROUSEL_GENERATION_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "name",
        "carousel_generation_slides",
        CAROUSEL_GENERATION_SLIDE_NAME_CHECK_SQL,
    )


def _create_slide_text_table() -> None:
    """Copied element text. The element id has no foreign key."""

    op.create_table(
        "carousel_generation_slide_texts",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_slide_id", UUID_COLUMN, nullable=False),
        sa.Column("skeleton_element_id", UUID_COLUMN, nullable=False),
        sa.Column(
            "value",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("draft_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["generation_slide_id"],
            ["carousel_generation_slides.id"],
            name="fk_cgen_slide_texts_generation_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "generation_slide_id",
            "skeleton_element_id",
            name="uq_cgen_slide_texts_slide_id_element_id",
        ),
    )
    op.create_index(
        "ix_cgen_slide_texts_generation_slide_id",
        "carousel_generation_slide_texts",
        ["generation_slide_id"],
    )


def _create_exclusion_table() -> None:
    """Copied exclusion pairs, stored in both directions."""

    op.create_table(
        "carousel_generation_slide_exclusions",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("generation_slide_id", UUID_COLUMN, nullable=False),
        sa.Column("excluded_generation_slide_id", UUID_COLUMN, nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_slide_id"],
            ["carousel_generation_slides.id"],
            name="fk_cgen_slide_exclusions_generation_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["excluded_generation_slide_id"],
            ["carousel_generation_slides.id"],
            name="fk_cgen_slide_exclusions_excluded_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "generation_slide_id",
            "excluded_generation_slide_id",
            name="uq_cgen_slide_exclusions_pair",
        ),
    )
    op.create_index(
        "ix_cgen_slide_exclusions_generation_slide_id",
        "carousel_generation_slide_exclusions",
        ["generation_slide_id"],
    )
    op.create_index(
        "ix_cgen_slide_exclusions_excluded_slide_id",
        "carousel_generation_slide_exclusions",
        ["excluded_generation_slide_id"],
    )
    op.create_check_constraint(
        "not_self",
        "carousel_generation_slide_exclusions",
        CAROUSEL_GENERATION_EXCLUSION_NOT_SELF_CHECK_SQL,
    )


def _backfill_generations() -> None:
    """Copy generation 1, or whatever number the carousel already stores.

    Each carousel gets one header. Children follow the working rows in
    position order. A null album stores no image rows.
    """

    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generations (
                carousel_id, generation_number, album_id
            )
            SELECT id, generation_number, album_id
            FROM carousels
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_instructions (
                generation_id, position, body
            )
            SELECT generation.id, instruction.position, instruction.body
            FROM carousel_instructions AS instruction
            JOIN carousel_generations AS generation
              ON generation.carousel_id = instruction.carousel_id
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_research (
                generation_id, position, research_item_id, title, body
            )
            SELECT
                generation.id,
                link.position,
                link.research_item_id,
                item.title,
                item.body
            FROM carousel_research_items AS link
            JOIN research_items AS item ON item.id = link.research_item_id
            JOIN carousel_generations AS generation
              ON generation.carousel_id = link.carousel_id
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_images (
                generation_id, position, album_image_id
            )
            SELECT generation.id, image.position, image.id
            FROM carousel_generations AS generation
            JOIN carousels AS carousel ON carousel.id = generation.carousel_id
            JOIN album_images AS image ON image.album_id = carousel.album_id
            WHERE carousel.album_id IS NOT NULL
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_slides (
                generation_id,
                position,
                name,
                text_status,
                album_image_id,
                source_slide_id
            )
            SELECT
                generation.id,
                slide.position,
                slide.name,
                slide.text_status,
                slide.album_image_id,
                slide.id
            FROM slides AS slide
            JOIN carousel_generations AS generation
              ON generation.carousel_id = slide.carousel_id
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_slide_texts (
                generation_slide_id, skeleton_element_id, value, draft_value
            )
            SELECT
                generation_slide.id,
                element_text.skeleton_element_id,
                element_text.value,
                element_text.draft_value
            FROM slide_element_texts AS element_text
            JOIN carousel_generation_slides AS generation_slide
              ON generation_slide.source_slide_id = element_text.slide_id
            """
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO carousel_generation_slide_exclusions (
                generation_slide_id, excluded_generation_slide_id
            )
            SELECT source_slide.id, excluded_slide.id
            FROM slide_exclusions AS exclusion
            JOIN carousel_generation_slides AS source_slide
              ON source_slide.source_slide_id = exclusion.slide_id
            JOIN carousel_generation_slides AS excluded_slide
              ON excluded_slide.source_slide_id = exclusion.excluded_slide_id
             AND excluded_slide.generation_id = source_slide.generation_id
            """
        ),
    )


def _attach_assemblies() -> None:
    """Point each assembly at the snapshot with the same generation number.

    The column is added nullable, filled, then required. Frames and
    ``asset_ref`` are not rewritten.
    """

    op.add_column(
        "carousel_assemblies",
        sa.Column("generation_id", UUID_COLUMN, nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE carousel_assemblies AS assembly
            SET generation_id = generation.id
            FROM carousel_generations AS generation
            WHERE generation.carousel_id = assembly.carousel_id
              AND generation.generation_number = assembly.generation_number
            """
        ),
    )
    op.alter_column("carousel_assemblies", "generation_id", nullable=False)
    op.create_foreign_key(
        "fk_carousel_assemblies_generation_id_carousel_generations",
        "carousel_assemblies",
        "carousel_generations",
        ["generation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_carousel_assemblies_generation_id",
        "carousel_assemblies",
        ["generation_id"],
    )
