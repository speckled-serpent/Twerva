"""Add campaign_type value ``spotmu_test``.

Revision ID: campaign_type_spotmu_test
Revises: campaign_status_lifecycle
Create Date: 2026-09-21

Throwaway Spotmu campaigns may omit linked social accounts. Existing
``spotmu`` / ``other`` values are unchanged.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text


revision: str = "campaign_type_spotmu_test"
down_revision: str | None = "campaign_status_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.execute(text("ALTER TYPE campaign_type ADD VALUE 'spotmu_test'"))


def downgrade() -> None:

    op.execute(
        text(
            "ALTER TABLE campaigns ALTER COLUMN campaign_type "
            "TYPE text USING campaign_type::text"
        ),
    )
    op.execute(
        text(
            "UPDATE campaigns SET campaign_type = 'spotmu' "
            "WHERE campaign_type = 'spotmu_test'"
        ),
    )
    op.execute(text("DROP TYPE campaign_type"))
    op.execute(text("CREATE TYPE campaign_type AS ENUM ('spotmu', 'other')"))
    op.execute(
        text(
            "ALTER TABLE campaigns ALTER COLUMN campaign_type "
            "TYPE campaign_type USING campaign_type::campaign_type"
        ),
    )
