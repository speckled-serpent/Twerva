"""Let a metric snapshot belong to a campaign post.

Revision ID: campaign_post_metrics
Revises: campaign_posts
Create Date: 2026-11-13

``metric_snapshots.post_job_id`` becomes nullable. ``campaign_post_id``
points at ``campaign_posts`` and cascades on delete. Exactly one of the
two ids is set. Upgrade inserts no rows and does not change existing
``post_job_id`` values.

Downgrade deletes snapshots that belong to a campaign post, drops the
new column, and sets ``post_job_id`` not null again. Post-job snapshots
stay.

The revision id is 21 characters, inside ``varchar(64)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.metric_snapshot import METRIC_SNAPSHOT_OWNER_CHECK_SQL


revision: str = "campaign_post_metrics"
down_revision: str | None = "campaign_posts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_COLUMN = UUID(as_uuid=True)
OWNER_CHECK_NAME: str = "owner"


def upgrade() -> None:
    """Add the campaign post pointer. Existing snapshots stay on their jobs."""

    op.add_column(
        "metric_snapshots",
        sa.Column("campaign_post_id", UUID_COLUMN, nullable=True),
    )
    op.create_foreign_key(
        "fk_metric_snapshots_campaign_post_id_campaign_posts",
        "metric_snapshots",
        "campaign_posts",
        ["campaign_post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_metric_snapshots_campaign_post_id",
        "metric_snapshots",
        ["campaign_post_id"],
    )
    op.alter_column(
        "metric_snapshots",
        "post_job_id",
        existing_type=UUID_COLUMN,
        nullable=True,
    )
    op.create_check_constraint(
        "owner",
        "metric_snapshots",
        METRIC_SNAPSHOT_OWNER_CHECK_SQL,
    )


def downgrade() -> None:
    """Remove campaign-post snapshots and restore the post-job-only column."""

    op.drop_constraint(OWNER_CHECK_NAME, "metric_snapshots", type_="check")
    op.execute(
        sa.text(
            "DELETE FROM metric_snapshots WHERE campaign_post_id IS NOT NULL",
        ),
    )
    op.drop_index(
        "ix_metric_snapshots_campaign_post_id",
        table_name="metric_snapshots",
    )
    op.drop_constraint(
        "fk_metric_snapshots_campaign_post_id_campaign_posts",
        "metric_snapshots",
        type_="foreignkey",
    )
    op.drop_column("metric_snapshots", "campaign_post_id")
    op.alter_column(
        "metric_snapshots",
        "post_job_id",
        existing_type=UUID_COLUMN,
        nullable=False,
    )
