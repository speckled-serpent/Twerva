"""Domain models register on metadata with the 1.2 indexes and enums."""

import unittest

from sqlalchemy import UniqueConstraint
from sqlalchemy.sql.schema import Table

from app.models import (
    ARTIFACT_STATUS_TRANSITIONS,
    POST_JOB_STATUS_TRANSITIONS,
    Account,
    Artifact,
    ArtifactStatus,
    Base,
    Brand,
    Cluster,
    MetricSnapshot,
    Platform,
    PostJob,
    PostJobStatus,
    SourceItem,
    SourceType,
    SteerAction,
    SteerActionType,
    cluster_source_items,
)
from app.models.account import Account as AccountModel


EXPECTED_TABLE_NAMES: frozenset[str] = frozenset(
    {
        "brands",
        "source_items",
        "clusters",
        "cluster_source_items",
        "accounts",
        "artifacts",
        "post_jobs",
        "metric_snapshots",
        "steer_actions",
    },
)


class DomainModelMetadataTests(unittest.TestCase):
    """1.2b–j: tables, relationships, and locked constraints exist in metadata."""

    def test_all_domain_tables_are_registered(self) -> None:
        """Importing app.models attaches every 1.2c–1.2j table."""

        registered_table_names: set[str] = set(Base.metadata.tables.keys())

        self.assertTrue(EXPECTED_TABLE_NAMES.issubset(registered_table_names))

    def test_model_tablenames_match_the_task_sheet(self) -> None:
        """SQLAlchemy classes use the locked table names."""

        self.assertEqual(Brand.__tablename__, "brands")
        self.assertEqual(SourceItem.__tablename__, "source_items")
        self.assertEqual(Cluster.__tablename__, "clusters")
        self.assertEqual(cluster_source_items.name, "cluster_source_items")
        self.assertEqual(Account.__tablename__, "accounts")
        self.assertEqual(Artifact.__tablename__, "artifacts")
        self.assertEqual(PostJob.__tablename__, "post_jobs")
        self.assertEqual(MetricSnapshot.__tablename__, "metric_snapshots")
        self.assertEqual(SteerAction.__tablename__, "steer_actions")
        self.assertIs(Account, AccountModel)

    def test_account_has_no_oauth_token_columns(self) -> None:
        """1.2f: do not store OAuth tokens on accounts."""

        account_column_names: set[str] = set(Account.__table__.columns.keys())
        forbidden_column_names: set[str] = {
            "access_token",
            "refresh_token",
            "oauth_token",
            "token",
            "token_secret",
        }
        overlapping_column_names: set[str] = (
            account_column_names.intersection(forbidden_column_names)
        )

        self.assertEqual(overlapping_column_names, set())

    def test_account_uniqueness_is_platform_and_handle(self) -> None:
        """1.2f-ii: unique (platform, handle)."""

        unique_column_pairs: list[tuple[str, ...]] = _unique_column_tuples(
            Account.__table__,
        )

        self.assertIn(("platform", "handle"), unique_column_pairs)

    def test_metric_snapshots_allow_multiple_rows_per_post_job(self) -> None:
        """1.2i-i: no unique constraint that collapses snapshot history."""

        unique_column_pairs: list[tuple[str, ...]] = _unique_column_tuples(
            MetricSnapshot.__table__,
        )
        unique_includes_post_job_id: bool = any(
            "post_job_id" in column_tuple and "id" not in column_tuple
            for column_tuple in unique_column_pairs
        )

        self.assertFalse(unique_includes_post_job_id)

    def test_required_query_indexes_exist(self) -> None:
        """1.2k-ii named indexes are present on metadata."""

        index_names: set[str] = {
            index.name
            for table in Base.metadata.tables.values()
            for index in table.indexes
            if index.name is not None
        }

        self.assertIn("ix_clusters_brand_id_slug", index_names)
        self.assertIn("ix_source_items_brand_id_source_type", index_names)
        self.assertIn("ix_post_jobs_status_scheduled_for", index_names)
        self.assertIn("ix_artifacts_status", index_names)
        self.assertIn("uq_source_items_brand_type_external_key", index_names)

        brands_slug_is_unique: bool = any(
            column.name == "slug" and column.unique
            for column in Brand.__table__.columns
        )

        self.assertTrue(brands_slug_is_unique)

    def test_foreign_key_columns_are_indexed(self) -> None:
        """Every FK column has an index (or is leftmost in a unique/PK)."""

        missing_foreign_key_indexes: list[str] = []

        for table_name, table in Base.metadata.tables.items():
            indexed_column_names: set[str] = _indexed_column_names(table)

            for foreign_key in table.foreign_keys:
                foreign_key_column_name: str = foreign_key.parent.name

                if foreign_key_column_name not in indexed_column_names:
                    missing_foreign_key_indexes.append(
                        f"{table_name}.{foreign_key_column_name}",
                    )

        self.assertEqual(missing_foreign_key_indexes, [])


class DomainEnumTests(unittest.TestCase):
    """1.2b closed vocabularies and documented transitions."""

    def test_artifact_status_values(self) -> None:
        """ArtifactStatus is draft / approved / rejected."""

        self.assertEqual(
            {member.value for member in ArtifactStatus},
            {"draft", "approved", "rejected"},
        )
        self.assertEqual(
            ARTIFACT_STATUS_TRANSITIONS[ArtifactStatus.REJECTED],
            frozenset(),
        )

    def test_post_job_status_retry_edges(self) -> None:
        """failed may return to scheduled or publishing."""

        failed_targets: frozenset[PostJobStatus] = POST_JOB_STATUS_TRANSITIONS[
            PostJobStatus.FAILED
        ]

        self.assertIn(PostJobStatus.SCHEDULED, failed_targets)
        self.assertIn(PostJobStatus.PUBLISHING, failed_targets)
        self.assertEqual(
            {member.value for member in PostJobStatus},
            {"scheduled", "publishing", "published", "failed", "measured"},
        )

    def test_platform_and_source_type_include_phase_one_values(self) -> None:
        """Platform is IG+TikTok; SourceType keeps reserved unused values."""

        self.assertEqual(
            {member.value for member in Platform},
            {"instagram", "tiktok"},
        )
        self.assertEqual(SourceType.SPOTMU_INTEREST.value, "spotmu_interest")
        self.assertEqual(SourceType.BRAND_PRODUCT.value, "brand_product")
        self.assertEqual(SourceType.EDITORIAL_BRIEF.value, "editorial_brief")

    def test_steer_action_values(self) -> None:
        """Steer actions match the 1.2j closed set."""

        self.assertEqual(
            {member.value for member in SteerActionType},
            {"kill", "pause", "double_down", "resume"},
        )


def _unique_column_tuples(table: Table) -> list[tuple[str, ...]]:
    """Return column-name tuples for unique constraints and unique indexes."""

    unique_column_pairs: list[tuple[str, ...]] = []

    for table_constraint in table.constraints:

        if isinstance(table_constraint, UniqueConstraint):
            constraint_column_names: tuple[str, ...] = tuple(
                column.name for column in table_constraint.columns
            )
            unique_column_pairs.append(constraint_column_names)

    for table_index in table.indexes:

        if table_index.unique:
            index_column_names: tuple[str, ...] = tuple(
                column.name for column in table_index.columns
            )
            unique_column_pairs.append(index_column_names)

    return unique_column_pairs


def _indexed_column_names(table: Table) -> set[str]:
    """Column names covered as leftmost key of a PK, unique, or index."""

    indexed_column_names: set[str] = set()

    for primary_key_column in table.primary_key.columns:
        indexed_column_names.add(primary_key_column.name)

        break

    for table_constraint in table.constraints:

        if isinstance(table_constraint, UniqueConstraint):
            first_unique_column: str | None = next(
                (column.name for column in table_constraint.columns),
                None,
            )

            if first_unique_column is not None:
                indexed_column_names.add(first_unique_column)

    for table_index in table.indexes:
        first_index_column: str | None = next(
            (column.name for column in table_index.columns),
            None,
        )

        if first_index_column is not None:
            indexed_column_names.add(first_index_column)

    return indexed_column_names


if __name__ == "__main__":
    unittest.main()
