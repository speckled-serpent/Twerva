"""Create `ops_users` for operator login (public ops console).

Revision ID: ops_users_web_auth
Revises: 12bk_domain_schema
Create Date: 2026-09-20

Sessions are **not** stored in Postgres. The API issues a signed
httpOnly cookie (`itsdangerous` + `SESSION_SECRET`). See
`app.auth.sessions` and `docs/reports/task_ops_web_auth_report.md`.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "ops_users_web_auth"
down_revision: str | None = "12bk_domain_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)


def upgrade() -> None:

    _create_ops_users_table()


def downgrade() -> None:

    op.drop_table("ops_users")


def _create_ops_users_table() -> None:
    """Create `ops_users` (operator accounts, not social `accounts`)."""

    op.create_table(
        "ops_users",
        sa.Column(
            "id",
            UUID_PRIMARY_KEY,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ,
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ops_users"),
        sa.UniqueConstraint("username", name="uq_ops_users_username"),
    )
