"""Add themes for carousel visual styling.

Revision ID: themes_create
Revises: campaign_type_spotmu_test
Create Date: 2026-09-27

Stores a named theme (slug from name, carousel advertisement type,
optional generator ``template_key``). Seeds the two existing Spotmu
carousel templates so the Themes list is not empty after upgrade.
Does not bind campaigns or render slides.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "themes_create"
down_revision: str | None = "campaign_type_spotmu_test"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)

ADVERTISEMENT_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "carousel",
    name="advertisement_type",
    create_type=False,
)

SEEDED_PAPER_THEME_ID: str = "e8700eea-c086-5ce2-859d-b3d689af5c25"
SEEDED_BOLD_THEME_ID: str = "ea248e2b-0222-50ce-82ce-ca7c562afa7b"


def upgrade() -> None:

    _create_themes_table()
    _seed_carousel_template_themes()


def downgrade() -> None:

    op.drop_index("ix_themes_created_at", table_name="themes")
    op.drop_index("ix_themes_created_by", table_name="themes")
    op.drop_table("themes")


def _uuid_primary_key_column() -> sa.Column[object]:
    """Return the shared UUID PK column (server default gen_random_uuid)."""

    uuid_primary_key_column: sa.Column[object] = sa.Column(
        "id",
        UUID_PRIMARY_KEY,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )

    return uuid_primary_key_column


def _created_at_column() -> sa.Column[object]:
    """Return a timezone-aware created_at column."""

    created_at_column: sa.Column[object] = sa.Column(
        "created_at",
        TIMESTAMPTZ,
        server_default=sa.text("now()"),
        nullable=False,
    )

    return created_at_column


def _updated_at_column() -> sa.Column[object]:
    """Return a timezone-aware updated_at column."""

    updated_at_column: sa.Column[object] = sa.Column(
        "updated_at",
        TIMESTAMPTZ,
        server_default=sa.text("now()"),
        nullable=False,
    )

    return updated_at_column


def _create_themes_table() -> None:
    """Create `themes` with unique slug and optional template key."""

    op.create_table(
        "themes",
        _uuid_primary_key_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "advertisement_type",
            ADVERTISEMENT_TYPE_ENUM,
            nullable=False,
        ),
        sa.Column("template_key", sa.Text(), nullable=True),
        sa.Column("created_by", UUID_PRIMARY_KEY, nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["ops_users.id"],
            name="fk_themes_created_by_ops_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_themes"),
        sa.UniqueConstraint("slug", name="uq_themes_slug"),
        sa.UniqueConstraint("template_key", name="uq_themes_template_key"),
    )
    op.create_index("ix_themes_created_by", "themes", ["created_by"])
    op.create_index("ix_themes_created_at", "themes", ["created_at"])


def _seed_carousel_template_themes() -> None:
    """Register the two existing Spotmu carousel generators as themes."""

    op.execute(
        sa.text(
            f"""
            INSERT INTO themes (
                id,
                name,
                slug,
                advertisement_type,
                template_key
            )
            VALUES
                (
                    '{SEEDED_PAPER_THEME_ID}'::uuid,
                    'Spotmu Paper v1',
                    'spotmu-paper-v1',
                    'carousel',
                    'spotmu_paper_v1'
                ),
                (
                    '{SEEDED_BOLD_THEME_ID}'::uuid,
                    'Spotmu Bold v1',
                    'spotmu-bold-v1',
                    'carousel',
                    'spotmu_bold_v1'
                )
            ON CONFLICT (slug) DO NOTHING
            """
        ),
    )
