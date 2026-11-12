"""Add instruction documents and copy inspiration and rules.

Revision ID: carousel_instructions
Revises: carousel_editor_step_content
Create Date: 2026-11-12

``carousel_instructions`` stores the current body and a position. There
is no title and no version. Upgrade inserts one row at position 0 when
``btrim(inspiration) <> ''`` or ``btrim(rules) <> ''``. The body is the
stored strings under two headings, including a field that is blank, and
it ends with a newline:

    ## Inspiration

    {inspiration}

    ## Rules

    {rules}

A carousel whose inspiration and rules both trim to empty gets no row.
That includes Default. This revision does not drop ``inspiration`` or
``rules``, does not change ``ck_carousels_editor_step``, and does not
move ``editor_step``, albums, research, or slides.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops ``carousel_instructions`` and the rows in it. The two
columns stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.carousel import (
    CAROUSEL_INSTRUCTION_BODY_CHECK_SQL,
    CAROUSEL_INSTRUCTION_POSITION_CHECK_SQL,
)


revision: str = "carousel_instructions"
down_revision: str | None = "carousel_editor_step_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)

# The trailing chr(10) is the newline the copied body keeps.
INSTRUCTION_BODY_EXPRESSION: str = (
    "'## Inspiration' || chr(10) || chr(10)"
    " || inspiration || chr(10) || chr(10)"
    " || '## Rules' || chr(10) || chr(10)"
    " || rules || chr(10)"
)


def upgrade() -> None:
    """Create the document table and copy guidance that has text."""

    _create_instruction_table()
    _copy_guidance_into_instructions()


def downgrade() -> None:
    """Drop ``carousel_instructions``. Inspiration and rules stay."""

    op.drop_table("carousel_instructions")


def _create_instruction_table() -> None:
    """Create the ordered documents. Upgrade inserts the copied rows next."""

    op.create_table(
        "carousel_instructions",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["carousel_id"],
            ["carousels.id"],
            name="fk_carousel_instructions_carousel_id_carousels",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_carousel_instructions_carousel_id_position",
        ),
    )
    op.create_index(
        "ix_carousel_instructions_carousel_id",
        "carousel_instructions",
        ["carousel_id"],
    )
    op.create_check_constraint(
        "position",
        "carousel_instructions",
        CAROUSEL_INSTRUCTION_POSITION_CHECK_SQL,
    )
    op.create_check_constraint(
        "body",
        "carousel_instructions",
        CAROUSEL_INSTRUCTION_BODY_CHECK_SQL,
    )


def _copy_guidance_into_instructions() -> None:
    """Insert one document when inspiration or rules has text.

    The body keeps the stored strings, including a blank field. A
    carousel whose fields both trim to empty gets no row.
    """

    op.execute(
        sa.text(
            f"""
            INSERT INTO carousel_instructions (carousel_id, position, body)
            SELECT
                id,
                0,
                {INSTRUCTION_BODY_EXPRESSION}
            FROM carousels
            WHERE btrim(inspiration) <> ''
               OR btrim(rules) <> ''
            """
        ),
    )
