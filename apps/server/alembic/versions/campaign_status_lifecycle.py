"""Rename campaign_status ``not_started`` → ``ready`` and add lifecycle values.

Revision ID: campaign_status_lifecycle
Revises: campaigns_create_ui
Create Date: 2026-09-21

Existing ``not_started`` rows become ``ready`` via enum value rename.
Adds ``running``, ``paused``, and ``finished``. Column default becomes
``ready``. Start / pause / resume / finish are application-layer only.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "campaign_status_lifecycle"
down_revision: str | None = "campaigns_create_ui"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAMPAIGN_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "ready",
    "running",
    "paused",
    "finished",
    name="campaign_status",
    create_type=False,
)


def upgrade() -> None:

    op.execute(text("ALTER TYPE campaign_status RENAME VALUE 'not_started' TO 'ready'"))
    op.execute(text("ALTER TYPE campaign_status ADD VALUE 'running'"))
    op.execute(text("ALTER TYPE campaign_status ADD VALUE 'paused'"))
    op.execute(text("ALTER TYPE campaign_status ADD VALUE 'finished'"))
    op.alter_column(
        "campaigns",
        "status",
        existing_type=CAMPAIGN_STATUS_ENUM,
        server_default=sa.text("'ready'::campaign_status"),
        existing_nullable=False,
    )


def downgrade() -> None:

    op.alter_column(
        "campaigns",
        "status",
        existing_type=CAMPAIGN_STATUS_ENUM,
        server_default=None,
        existing_nullable=False,
    )
    op.execute(text("ALTER TABLE campaigns ALTER COLUMN status TYPE text USING status::text"))
    op.execute(
        text(
            "UPDATE campaigns SET status = 'not_started' "
            "WHERE status IN ('ready', 'running', 'paused', 'finished')"
        ),
    )
    op.execute(text("DROP TYPE campaign_status"))
    op.execute(text("CREATE TYPE campaign_status AS ENUM ('not_started')"))
    op.execute(
        text(
            "ALTER TABLE campaigns ALTER COLUMN status "
            "TYPE campaign_status USING status::campaign_status"
        ),
    )
    op.execute(
        text(
            "ALTER TABLE campaigns ALTER COLUMN status "
            "SET DEFAULT 'not_started'::campaign_status"
        ),
    )
