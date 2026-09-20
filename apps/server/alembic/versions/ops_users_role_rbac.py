"""Add `ops_users.role` for admin / reader RBAC.

Revision ID: ops_users_role_rbac
Revises: ops_users_web_auth
Create Date: 2026-09-20

Existing operator rows become `admin` so the bootstrap account keeps
full access. New rows default to `reader` unless create sets otherwise.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "ops_users_role_rbac"
down_revision: str | None = "ops_users_web_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPS_USER_ROLE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "admin",
    "reader",
    name="ops_user_role",
    create_type=False,
)


def upgrade() -> None:

    _create_ops_user_role_type()
    _add_ops_users_role_column()
    _backfill_existing_ops_users_as_admin()
    _lock_ops_users_role_not_null()


def downgrade() -> None:

    op.drop_column("ops_users", "role")
    op.execute(text("DROP TYPE ops_user_role"))


def _create_ops_user_role_type() -> None:
    """Create the native Postgres enum used by `ops_users.role`."""

    op.execute(text("CREATE TYPE ops_user_role AS ENUM ('admin', 'reader')"))


def _add_ops_users_role_column() -> None:
    """Add a nullable role column so existing rows can be backfilled."""

    op.add_column(
        "ops_users",
        sa.Column("role", OPS_USER_ROLE_ENUM, nullable=True),
    )


def _backfill_existing_ops_users_as_admin() -> None:
    """Promote every existing operator to admin (bootstrap continuity)."""

    op.execute(text("UPDATE ops_users SET role = 'admin' WHERE role IS NULL"))


def _lock_ops_users_role_not_null() -> None:
    """Require role and default new inserts to reader."""

    op.alter_column(
        "ops_users",
        "role",
        existing_type=OPS_USER_ROLE_ENUM,
        nullable=False,
        server_default=sa.text("'reader'::ops_user_role"),
    )
