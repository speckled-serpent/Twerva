"""Drop carousel inspiration and rules.

Revision ID: carousel_instructions_drop_guidance
Revises: carousel_editor_step_instructions
Create Date: 2026-11-12

The copied documents already live in ``carousel_instructions``. This
revision drops ``carousels.inspiration`` and ``carousels.rules``.
Instruction rows stay. Downgrade adds both columns back as text, not
null, server default ``""``, and leaves them empty. It does not parse
documents back into the columns.

The revision id is 35 characters. ``alembic_version.version_num`` is
already ``varchar(64)`` from ``carousel_editor_step_instructions``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "carousel_instructions_drop_guidance"
down_revision: str | None = "carousel_editor_step_instructions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the two guidance columns. Instruction documents stay."""

    op.drop_column("carousels", "rules")
    op.drop_column("carousels", "inspiration")


def downgrade() -> None:
    """Add empty inspiration and rules. Instruction documents stay."""

    op.add_column(
        "carousels",
        sa.Column("inspiration", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "carousels",
        sa.Column("rules", sa.Text(), nullable=False, server_default=""),
    )
