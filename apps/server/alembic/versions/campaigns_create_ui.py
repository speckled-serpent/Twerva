"""Add campaign definition tables (create-only; no start/generate).

Revision ID: campaigns_create_ui
Revises: artifact_template_id
Create Date: 2026-09-21

Stores a marketing campaign (name + slug/hashtag + type + carousel +
platforms) plus optional account and Spotmu interest joins. Status is
``not_started`` only. Creating a row does not ingest or render.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "campaigns_create_ui"
down_revision: str | None = "artifact_template_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
JSONB_TYPE: postgresql.JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)

CAMPAIGN_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "spotmu",
    "other",
    name="campaign_type",
    create_type=False,
)
ADVERTISEMENT_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "carousel",
    name="advertisement_type",
    create_type=False,
)
CAMPAIGN_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "not_started",
    name="campaign_status",
    create_type=False,
)


def upgrade() -> None:

    _create_campaign_enum_types()
    _create_campaigns_table()
    _create_campaign_accounts_table()
    _create_campaign_interests_table()


def downgrade() -> None:

    op.drop_table("campaign_interests")
    op.drop_table("campaign_accounts")
    op.drop_table("campaigns")
    op.execute(text("DROP TYPE campaign_status"))
    op.execute(text("DROP TYPE advertisement_type"))
    op.execute(text("DROP TYPE campaign_type"))


def _create_campaign_enum_types() -> None:
    """Create native Postgres ENUM types for campaign columns."""

    op.execute(text("CREATE TYPE campaign_type AS ENUM ('spotmu', 'other')"))
    op.execute(text("CREATE TYPE advertisement_type AS ENUM ('carousel')"))
    op.execute(text("CREATE TYPE campaign_status AS ENUM ('not_started')"))


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


def _create_campaigns_table() -> None:
    """Create `campaigns` plus unique slug/hashtag."""

    op.create_table(
        "campaigns",
        _uuid_primary_key_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("hashtag", sa.Text(), nullable=False),
        sa.Column("campaign_type", CAMPAIGN_TYPE_ENUM, nullable=False),
        sa.Column(
            "advertisement_type",
            ADVERTISEMENT_TYPE_ENUM,
            nullable=False,
        ),
        sa.Column(
            "status",
            CAMPAIGN_STATUS_ENUM,
            nullable=False,
            server_default=sa.text("'not_started'::campaign_status"),
        ),
        sa.Column(
            "platforms",
            JSONB_TYPE,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_by", UUID_PRIMARY_KEY, nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["ops_users.id"],
            name="fk_campaigns_created_by_ops_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.UniqueConstraint("slug", name="uq_campaigns_slug"),
        sa.UniqueConstraint("hashtag", name="uq_campaigns_hashtag"),
    )
    op.create_index("ix_campaigns_created_by", "campaigns", ["created_by"])
    op.create_index("ix_campaigns_created_at", "campaigns", ["created_at"])


def _create_campaign_accounts_table() -> None:
    """Create `campaign_accounts` (unique campaign + account pair)."""

    op.create_table(
        "campaign_accounts",
        sa.Column("campaign_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("account_id", UUID_PRIMARY_KEY, nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_campaign_accounts_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_campaign_accounts_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id",
            "account_id",
            name="pk_campaign_accounts",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "account_id",
            name="uq_campaign_accounts_campaign_id_account_id",
        ),
    )
    op.create_index(
        "ix_campaign_accounts_campaign_id",
        "campaign_accounts",
        ["campaign_id"],
    )
    op.create_index(
        "ix_campaign_accounts_account_id",
        "campaign_accounts",
        ["account_id"],
    )


def _create_campaign_interests_table() -> None:
    """Create `campaign_interests` (unique campaign + Spotmu slug)."""

    op.create_table(
        "campaign_interests",
        _uuid_primary_key_column(),
        sa.Column("campaign_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("spotmu_slug", sa.Text(), nullable=False),
        sa.Column("spotmu_interest_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_campaign_interests_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_interests"),
        sa.UniqueConstraint(
            "campaign_id",
            "spotmu_slug",
            name="uq_campaign_interests_campaign_id_spotmu_slug",
        ),
    )
    op.create_index(
        "ix_campaign_interests_campaign_id",
        "campaign_interests",
        ["campaign_id"],
    )
