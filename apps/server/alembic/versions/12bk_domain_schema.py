"""Create Phase 1.2c–1.2j domain tables, enums, and indexes.

Revision ID: 12bk_domain_schema
Revises:
Create Date: 2026-09-15

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa


revision: str = "12bk_domain_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARTIFACT_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "draft",
    "approved",
    "rejected",
    name="artifact_status",
    create_type=False,
)
POST_JOB_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "scheduled",
    "publishing",
    "published",
    "failed",
    "measured",
    name="post_job_status",
    create_type=False,
)
PLATFORM_ENUM: postgresql.ENUM = postgresql.ENUM(
    "instagram",
    "tiktok",
    name="platform",
    create_type=False,
)
SOURCE_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "spotmu_interest",
    "brand_product",
    "editorial_brief",
    name="source_type",
    create_type=False,
)
ACCOUNT_STATUS_ENUM: postgresql.ENUM = postgresql.ENUM(
    "active",
    "paused",
    "disabled",
    name="account_status",
    create_type=False,
)
STEER_ACTION_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "kill",
    "pause",
    "double_down",
    "resume",
    name="steer_action_type",
    create_type=False,
)

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
JSONB_TYPE: postgresql.JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ: sa.DateTime = sa.DateTime(timezone=True)


def upgrade() -> None:

    _enable_pgcrypto_extension()
    _create_enum_types()
    _create_brands_table()
    _create_source_items_table()
    _create_clusters_table()
    _create_cluster_source_items_table()
    _create_accounts_table()
    _create_artifacts_table()
    _create_post_jobs_table()
    _create_metric_snapshots_table()
    _create_steer_actions_table()
    _create_query_indexes()


def downgrade() -> None:

    op.drop_table("steer_actions")
    op.drop_table("metric_snapshots")
    op.drop_table("post_jobs")
    op.drop_table("artifacts")
    op.drop_table("accounts")
    op.drop_table("cluster_source_items")
    op.drop_table("clusters")
    op.drop_table("source_items")
    op.drop_table("brands")
    _drop_enum_types()


def _enable_pgcrypto_extension() -> None:
    """Install pgcrypto so `gen_random_uuid()` exists on older images."""

    op.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))


def _create_enum_types() -> None:
    """Create native Postgres ENUM types used by 1.2 columns."""

    op.execute(
        text(
            "CREATE TYPE artifact_status AS ENUM "
            "('draft', 'approved', 'rejected')"
        ),
    )
    op.execute(
        text(
            "CREATE TYPE post_job_status AS ENUM "
            "('scheduled', 'publishing', 'published', 'failed', 'measured')"
        ),
    )
    op.execute(text("CREATE TYPE platform AS ENUM ('instagram', 'tiktok')"))
    op.execute(
        text(
            "CREATE TYPE source_type AS ENUM "
            "('spotmu_interest', 'brand_product', 'editorial_brief')"
        ),
    )
    op.execute(
        text(
            "CREATE TYPE account_status AS ENUM "
            "('active', 'paused', 'disabled')"
        ),
    )
    op.execute(
        text(
            "CREATE TYPE steer_action_type AS ENUM "
            "('kill', 'pause', 'double_down', 'resume')"
        ),
    )


def _drop_enum_types() -> None:
    """Drop native Postgres ENUM types after the tables that use them."""

    op.execute(text("DROP TYPE IF EXISTS steer_action_type"))
    op.execute(text("DROP TYPE IF EXISTS account_status"))
    op.execute(text("DROP TYPE IF EXISTS source_type"))
    op.execute(text("DROP TYPE IF EXISTS platform"))
    op.execute(text("DROP TYPE IF EXISTS post_job_status"))
    op.execute(text("DROP TYPE IF EXISTS artifact_status"))


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


def _create_brands_table() -> None:
    """Create `brands` (1.2c)."""

    op.create_table(
        "brands",
        _uuid_primary_key_column(),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("voice_notes", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_brands"),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )


def _create_source_items_table() -> None:
    """Create `source_items` (1.2d) plus the partial unique index."""

    op.create_table(
        "source_items",
        _uuid_primary_key_column(),
        sa.Column("brand_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("source_type", SOURCE_TYPE_ENUM, nullable=False),
        sa.Column("external_key", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("interest_heading", sa.Text(), nullable=True),
        sa.Column(
            "overview_bullets",
            JSONB_TYPE,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("brand_kit_refs", JSONB_TYPE, nullable=True),
        sa.Column("raw_payload", JSONB_TYPE, nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            name="fk_source_items_brand_id_brands",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_items"),
    )
    op.create_index(
        "uq_source_items_brand_type_external_key",
        "source_items",
        ["brand_id", "source_type", "external_key"],
        unique=True,
        postgresql_where=sa.text("external_key IS NOT NULL"),
    )


def _create_clusters_table() -> None:
    """Create `clusters` (1.2e-i)."""

    op.create_table(
        "clusters",
        _uuid_primary_key_column(),
        sa.Column("brand_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            name="fk_clusters_brand_id_brands",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clusters"),
    )


def _create_cluster_source_items_table() -> None:
    """Create `cluster_source_items` join (1.2e-ii). Composite PK = unique pair."""

    op.create_table(
        "cluster_source_items",
        sa.Column("cluster_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("source_item_id", UUID_PRIMARY_KEY, nullable=False),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_cluster_source_items_cluster_id_clusters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"],
            ["source_items.id"],
            name="fk_cluster_source_items_source_item_id_source_items",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "cluster_id",
            "source_item_id",
            name="pk_cluster_source_items",
        ),
    )


def _create_accounts_table() -> None:
    """Create `accounts` (1.2f). Unique on (`platform`, `handle`)."""

    op.create_table(
        "accounts",
        _uuid_primary_key_column(),
        sa.Column("cluster_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("platform", PLATFORM_ENUM, nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("external_account_id", sa.Text(), nullable=True),
        sa.Column("status", ACCOUNT_STATUS_ENUM, nullable=False),
        sa.Column("cadence_cap_per_day", sa.Integer(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_accounts_cluster_id_clusters",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.UniqueConstraint(
            "platform",
            "handle",
            name="uq_accounts_platform_handle",
        ),
    )


def _create_artifacts_table() -> None:
    """Create `artifacts` (1.2g)."""

    op.create_table(
        "artifacts",
        _uuid_primary_key_column(),
        sa.Column("brand_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("source_item_id", UUID_PRIMARY_KEY, nullable=True),
        sa.Column("cluster_id", UUID_PRIMARY_KEY, nullable=True),
        sa.Column("status", ARTIFACT_STATUS_ENUM, nullable=False),
        sa.Column(
            "format",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'carousel'"),
        ),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("cta_url", sa.Text(), nullable=True),
        sa.Column("slides", JSONB_TYPE, nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.Column("approved_at", TIMESTAMPTZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            name="fk_artifacts_brand_id_brands",
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"],
            ["source_items.id"],
            name="fk_artifacts_source_item_id_source_items",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_artifacts_cluster_id_clusters",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )


def _create_post_jobs_table() -> None:
    """Create `post_jobs` (1.2h)."""

    op.create_table(
        "post_jobs",
        _uuid_primary_key_column(),
        sa.Column("artifact_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("account_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("status", POST_JOB_STATUS_ENUM, nullable=False),
        sa.Column("scheduled_for", TIMESTAMPTZ, nullable=True),
        sa.Column("published_at", TIMESTAMPTZ, nullable=True),
        sa.Column("platform_post_id", sa.Text(), nullable=True),
        sa.Column("platform_post_url", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_post_jobs_artifact_id_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_post_jobs_account_id_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_post_jobs"),
    )


def _create_metric_snapshots_table() -> None:
    """Create `metric_snapshots` (1.2i). Multiple rows per post job allowed."""

    op.create_table(
        "metric_snapshots",
        _uuid_primary_key_column(),
        sa.Column("post_job_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("captured_at", TIMESTAMPTZ, nullable=False),
        sa.Column("views", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("raw", JSONB_TYPE, nullable=True),
        sa.ForeignKeyConstraint(
            ["post_job_id"],
            ["post_jobs.id"],
            name="fk_metric_snapshots_post_job_id_post_jobs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metric_snapshots"),
    )


def _create_steer_actions_table() -> None:
    """Create `steer_actions` (1.2j). Append-only stub; no API."""

    op.create_table(
        "steer_actions",
        _uuid_primary_key_column(),
        sa.Column("cluster_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("action", STEER_ACTION_TYPE_ENUM, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at_column(),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_steer_actions_cluster_id_clusters",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_steer_actions"),
    )


def _create_query_indexes() -> None:
    """Create FK indexes plus the 1.2k-ii query indexes."""

    op.create_index("ix_source_items_brand_id", "source_items", ["brand_id"])
    op.create_index(
        "ix_source_items_brand_id_source_type",
        "source_items",
        ["brand_id", "source_type"],
    )
    op.create_index("ix_clusters_brand_id", "clusters", ["brand_id"])
    op.create_index(
        "ix_clusters_brand_id_slug",
        "clusters",
        ["brand_id", "slug"],
        unique=True,
    )
    op.create_index(
        "ix_cluster_source_items_cluster_id",
        "cluster_source_items",
        ["cluster_id"],
    )
    op.create_index(
        "ix_cluster_source_items_source_item_id",
        "cluster_source_items",
        ["source_item_id"],
    )
    op.create_index("ix_accounts_cluster_id", "accounts", ["cluster_id"])
    op.create_index("ix_artifacts_brand_id", "artifacts", ["brand_id"])
    op.create_index(
        "ix_artifacts_source_item_id",
        "artifacts",
        ["source_item_id"],
    )
    op.create_index("ix_artifacts_cluster_id", "artifacts", ["cluster_id"])
    op.create_index("ix_artifacts_status", "artifacts", ["status"])
    op.create_index("ix_post_jobs_artifact_id", "post_jobs", ["artifact_id"])
    op.create_index("ix_post_jobs_account_id", "post_jobs", ["account_id"])
    op.create_index(
        "ix_post_jobs_status_scheduled_for",
        "post_jobs",
        ["status", "scheduled_for"],
    )
    op.create_index(
        "ix_metric_snapshots_post_job_id",
        "metric_snapshots",
        ["post_job_id"],
    )
    op.create_index(
        "ix_steer_actions_cluster_id",
        "steer_actions",
        ["cluster_id"],
    )
