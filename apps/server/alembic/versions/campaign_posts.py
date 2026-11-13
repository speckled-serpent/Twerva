"""Add the campaign timeline table.

Revision ID: campaign_posts
Revises: carousel_generations
Create Date: 2026-11-13

``campaign_posts`` is one assembled carousel placed on a campaign.
Upgrade inserts no rows and does not update ``artifacts``,
``post_jobs``, ``campaign_carousels``, ``assembled_carousels``, or
``metric_snapshots``. A Spotmu interest is optional at create time,
and ``campaigns`` has no interest column to alter.

Check names passed to ``op.create_check_constraint`` are the short
logical names. The metadata convention stores them as
``ck_<table>_<name>``.

Downgrade drops ``campaign_posts``. Assemblies, artifacts, post jobs,
and campaign carousels stay. PNG files on disk stay.

The revision id is 14 characters, inside ``varchar(64)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.campaign import CAMPAIGN_POST_STATUS_CHECK_SQL


revision: str = "campaign_posts"
down_revision: str | None = "carousel_generations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)


def upgrade() -> None:
    """Create ``campaign_posts``. Existing rows stay as they are."""

    op.create_table(
        "campaign_posts",
        sa.Column(
            "id",
            UUID_COLUMN,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("campaign_id", UUID_COLUMN, nullable=False),
        sa.Column("assembled_carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("account_id", UUID_COLUMN, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_post_id", sa.Text(), nullable=True),
        sa.Column("platform_post_url", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_campaign_posts_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assembled_carousel_id"],
            ["assembled_carousels.id"],
            name="fk_campaign_posts_assembled_carousel_id_assembled_carousels",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_campaign_posts_account_id_accounts",
        ),
        sa.UniqueConstraint(
            "assembled_carousel_id",
            "account_id",
            name="uq_campaign_posts_assembled_carousel_id_account_id",
        ),
    )
    op.create_index(
        "ix_campaign_posts_campaign_id",
        "campaign_posts",
        ["campaign_id"],
    )
    op.create_index(
        "ix_campaign_posts_account_id_scheduled_for",
        "campaign_posts",
        ["account_id", "scheduled_for"],
    )
    op.create_check_constraint(
        "status",
        "campaign_posts",
        CAMPAIGN_POST_STATUS_CHECK_SQL,
    )


def downgrade() -> None:
    """Drop ``campaign_posts``. Other post rows and PNG files stay."""

    op.drop_table("campaign_posts")
