"""Allow carousels to store the Instructions step.

Revision ID: carousel_editor_step_instructions
Revises: carousel_instructions
Create Date: 2026-11-12

``editor_step`` may be 0 Basic, 1 Instructions, 2 Content, or 3 Slides.
Existing rows stay on 0, 2, or 3. Downgrade sets any stored 1 back to 0,
then restores ``editor_step IN (0, 2, 3)``.

The revision id is 33 characters. ``alembic_version.version_num`` is
``varchar(32)`` until this upgrade widens it, so the new id can be
stamped. Downgrade leaves the wider column: the row still holds this
id until Alembic updates it after ``downgrade()`` returns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.carousel import CAROUSEL_EDITOR_STEP_CHECK_SQL


revision: str = "carousel_editor_step_instructions"
down_revision: str | None = "carousel_instructions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREVIOUS_EDITOR_STEP_CHECK_SQL: str = "editor_step IN (0, 2, 3)"
EDITOR_STEP_CHECK_NAME: str = "ck_carousels_editor_step"
EDITOR_STEP_BASIC: int = 0
EDITOR_STEP_INSTRUCTIONS: int = 1


def upgrade() -> None:
    """Allow step 1. Leave every stored step where it is."""

    _widen_version_num()
    _replace_editor_step_check(CAROUSEL_EDITOR_STEP_CHECK_SQL)


def downgrade() -> None:
    """Put stored Instructions back on Basic, then restore the old check."""

    op.execute(
        sa.text(
            """
            UPDATE carousels
            SET editor_step = :basic_step
            WHERE editor_step = :instructions_step
            """
        ).bindparams(
            basic_step=EDITOR_STEP_BASIC,
            instructions_step=EDITOR_STEP_INSTRUCTIONS,
        ),
    )
    _replace_editor_step_check(PREVIOUS_EDITOR_STEP_CHECK_SQL)


def _widen_version_num() -> None:
    """Let ``alembic_version`` hold this 33-character revision id."""

    op.execute(
        sa.text(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(64)"
        ),
    )


def _replace_editor_step_check(check_sql: str) -> None:
    """Drop ``ck_carousels_editor_step`` and create it with ``check_sql``."""

    op.execute(
        sa.text(
            "ALTER TABLE carousels "
            f"DROP CONSTRAINT IF EXISTS {EDITOR_STEP_CHECK_NAME}"
        ),
    )
    op.create_check_constraint(
        "editor_step",
        "carousels",
        check_sql,
    )
