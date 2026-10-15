"""Store the other unit ids a unit cannot be shown with.

Revision ID: unit_exclusions
Revises: unit_element_texts
Create Date: 2026-10-15

Each row is one direction of a pair. The application writes both
directions. Deleting a unit removes every row that names it.
Downgrade drops the table and does not restore pairs.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "unit_exclusions"
down_revision: str | None = "unit_element_texts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:

    op.create_table(
        "unit_exclusions",
        sa.Column("id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("excluded_unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_unit_exclusions_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["excluded_unit_id"],
            ["units.id"],
            name="fk_unit_exclusions_excluded_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unit_exclusions"),
        sa.UniqueConstraint(
            "unit_id",
            "excluded_unit_id",
            name="uq_unit_exclusions_unit_id_excluded_unit_id",
        ),
        sa.CheckConstraint(
            "unit_id <> excluded_unit_id",
            name="ck_unit_exclusions_not_self",
        ),
    )
    op.create_index("ix_unit_exclusions_unit_id", "unit_exclusions", ["unit_id"])
    op.create_index(
        "ix_unit_exclusions_excluded_unit_id",
        "unit_exclusions",
        ["excluded_unit_id"],
    )


def downgrade() -> None:

    op.drop_index("ix_unit_exclusions_excluded_unit_id", table_name="unit_exclusions")
    op.drop_index("ix_unit_exclusions_unit_id", table_name="unit_exclusions")
    op.drop_table("unit_exclusions")
