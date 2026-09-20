"""Add nullable `artifacts.template_id` for Spotmu carousel variants.

Revision ID: artifact_template_id
Revises: ops_users_role_rbac
Create Date: 2026-09-20

Stores the restricted template used to render slides (`spotmu_paper_v1`,
`spotmu_bold_v1`, …). Existing rows stay NULL (treated as paper v1).
"""

from collections.abc import Sequence

from alembic import op

import sqlalchemy as sa


revision: str = "artifact_template_id"
down_revision: str | None = "ops_users_role_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.add_column(
        "artifacts",
        sa.Column("template_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:

    op.drop_column("artifacts", "template_id")
