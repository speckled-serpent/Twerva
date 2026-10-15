"""Store the theme and source a campaign runs, and the carousels it built.

Revision ID: campaign_theme_source
Revises: unit_text_drafts
Create Date: 2026-10-15

Campaigns saved before this revision have no theme and no source. The
new columns stay null on those rows. Nothing is deleted and nothing is
assigned a theme the operator did not pick. Run refuses them until
both are set. New campaigns require a theme and a source bound to it.

``campaign_carousels`` and ``campaign_carousel_slides`` hold the latest
run: live units placed on that theme, split where an exclusion pair
would share a carousel. Downgrade drops the tables and the columns.
It does not restore a run.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "campaign_theme_source"
down_revision: str | None = "unit_text_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN: postgresql.UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:

    op.add_column("campaigns", sa.Column("theme_id", UUID_COLUMN, nullable=True))
    op.add_column("campaigns", sa.Column("source_id", UUID_COLUMN, nullable=True))
    op.create_foreign_key(
        "fk_campaigns_theme_id_themes",
        "campaigns",
        "themes",
        ["theme_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_campaigns_source_id_sources",
        "campaigns",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_campaigns_theme_id", "campaigns", ["theme_id"])
    op.create_index("ix_campaigns_source_id", "campaigns", ["source_id"])
    op.create_table(
        "campaign_carousels",
        sa.Column("id", UUID_COLUMN, nullable=False),
        sa.Column("campaign_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_campaign_carousels_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_carousels"),
        sa.UniqueConstraint(
            "campaign_id",
            "position",
            name="uq_campaign_carousels_campaign_id_position",
        ),
    )
    op.create_index(
        "ix_campaign_carousels_campaign_id",
        "campaign_carousels",
        ["campaign_id"],
    )
    op.create_table(
        "campaign_carousel_slides",
        sa.Column("id", UUID_COLUMN, nullable=False),
        sa.Column("carousel_id", UUID_COLUMN, nullable=False),
        sa.Column("unit_id", UUID_COLUMN, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["carousel_id"],
            ["campaign_carousels.id"],
            name="fk_campaign_carousel_slides_carousel_id_campaign_carousels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_campaign_carousel_slides_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_carousel_slides"),
        sa.UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_campaign_carousel_slides_carousel_id_position",
        ),
        sa.UniqueConstraint(
            "carousel_id",
            "unit_id",
            name="uq_campaign_carousel_slides_carousel_id_unit_id",
        ),
    )
    op.create_index(
        "ix_campaign_carousel_slides_carousel_id",
        "campaign_carousel_slides",
        ["carousel_id"],
    )
    op.create_index(
        "ix_campaign_carousel_slides_unit_id",
        "campaign_carousel_slides",
        ["unit_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_campaign_carousel_slides_unit_id",
        table_name="campaign_carousel_slides",
    )
    op.drop_index(
        "ix_campaign_carousel_slides_carousel_id",
        table_name="campaign_carousel_slides",
    )
    op.drop_table("campaign_carousel_slides")
    op.drop_index(
        "ix_campaign_carousels_campaign_id",
        table_name="campaign_carousels",
    )
    op.drop_table("campaign_carousels")
    op.drop_index("ix_campaigns_source_id", table_name="campaigns")
    op.drop_index("ix_campaigns_theme_id", table_name="campaigns")
    op.drop_constraint(
        "fk_campaigns_source_id_sources",
        "campaigns",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_campaigns_theme_id_themes",
        "campaigns",
        type_="foreignkey",
    )
    op.drop_column("campaigns", "source_id")
    op.drop_column("campaigns", "theme_id")
