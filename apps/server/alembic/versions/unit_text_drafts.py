"""Store source inspiration and draft text that is not live yet.

Revision ID: unit_text_drafts
Revises: unit_exclusions
Create Date: 2026-10-15

Inspiration and rules live on the source. A unit's text is ``live``
until a generate call marks it ``draft``. The draft string sits beside
the live value. Existing units stay ``live``. Downgrade drops the
columns and does not restore drafts.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "unit_text_drafts"
down_revision: str | None = "unit_exclusions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIT_TEXT_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "live",
    "draft",
    name="unit_text_status",
    create_type=False,
)


def upgrade() -> None:

    op.add_column(
        "sources",
        sa.Column("inspiration", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "sources",
        sa.Column("rules", sa.Text(), nullable=False, server_default=""),
    )
    op.execute(text("CREATE TYPE unit_text_status AS ENUM ('live', 'draft')"))
    op.add_column(
        "units",
        sa.Column(
            "text_status",
            UNIT_TEXT_STATUS_ENUM,
            nullable=False,
            server_default=sa.text("'live'::unit_text_status"),
        ),
    )
    op.add_column(
        "unit_element_texts",
        sa.Column("draft_value", sa.Text(), nullable=True),
    )


def downgrade() -> None:

    op.drop_column("unit_element_texts", "draft_value")
    op.drop_column("units", "text_status")
    op.execute(text("DROP TYPE unit_text_status"))
    op.drop_column("sources", "rules")
    op.drop_column("sources", "inspiration")
