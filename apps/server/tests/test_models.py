"""Domain models register on metadata with the 1.2 indexes and enums."""

import unittest

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.sql.schema import Column, Table

from app.models import (
    ARTIFACT_STATUS_TRANSITIONS,
    CAMPAIGN_STATUS_TRANSITIONS,
    POST_JOB_STATUS_TRANSITIONS,
    Account,
    AdvertisementType,
    Artifact,
    ArtifactStatus,
    Base,
    Brand,
    Campaign,
    CampaignAccount,
    CampaignInterest,
    CampaignStatus,
    CampaignType,
    Cluster,
    MetricSnapshot,
    OpsUser,
    OpsUserRole,
    Platform,
    PostJob,
    PostJobStatus,
    SourceItem,
    SourceType,
    SteerAction,
    SteerActionType,
    Skeleton,
    SkeletonElement,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SkeletonStatus,
    ResearchItem,
    BackgroundKind,
    cluster_source_items,
)
from app.models.skeleton_element import (
    SKELETON_ELEMENT_CONTENT_CHECK_SQL,
    SKELETON_ELEMENT_NAME_CHECK_SQL,
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
        "ops_users",
        "campaigns",
        "campaign_accounts",
        "campaign_interests",
        "skeletons",
        "skeleton_elements",
        "research_items",
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
        self.assertEqual(OpsUser.__tablename__, "ops_users")
        self.assertEqual(Campaign.__tablename__, "campaigns")
        self.assertEqual(CampaignAccount.__tablename__, "campaign_accounts")
        self.assertEqual(CampaignInterest.__tablename__, "campaign_interests")
        self.assertEqual(Skeleton.__tablename__, "skeletons")
        self.assertEqual(SkeletonElement.__tablename__, "skeleton_elements")
        self.assertEqual(ResearchItem.__tablename__, "research_items")
        self.assertIs(Account, AccountModel)
        self.assertIn("template_id", set(Artifact.__table__.columns.keys()))

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

    def test_ops_user_role_values(self) -> None:
        """Ops operator roles are admin (full) and reader (GET-only)."""

        self.assertEqual(
            {member.value for member in OpsUserRole},
            {"admin", "reader"},
        )
        self.assertIn("role", set(OpsUser.__table__.columns.keys()))

    def test_campaign_closed_vocabularies(self) -> None:
        """Campaign type/format/status match the lifecycle slice."""

        self.assertEqual(
            {member.value for member in CampaignType},
            {"spotmu", "spotmu_test", "other"},
        )
        self.assertEqual(
            {member.value for member in AdvertisementType},
            {"carousel"},
        )
        self.assertEqual(
            {member.value for member in CampaignStatus},
            {"ready", "running", "paused", "finished"},
        )
        self.assertIn("slug", set(Campaign.__table__.columns.keys()))
        self.assertIn("hashtag", set(Campaign.__table__.columns.keys()))
        self.assertIn("platforms", set(Campaign.__table__.columns.keys()))
        self.assertEqual(
            CAMPAIGN_STATUS_TRANSITIONS[CampaignStatus.READY],
            frozenset({CampaignStatus.RUNNING}),
        )
        self.assertEqual(
            CAMPAIGN_STATUS_TRANSITIONS[CampaignStatus.FINISHED],
            frozenset(),
        )

    def test_skeleton_status_values(self) -> None:
        """Skeleton status is draft or live, and the column defaults to draft."""

        self.assertEqual(
            {member.value for member in SkeletonStatus},
            {"draft", "live"},
        )
        self.assertIn("status", set(Skeleton.__table__.columns.keys()))
        status_column: Column[object] = Skeleton.__table__.columns["status"]
        self.assertFalse(status_column.nullable)
        self.assertIsNotNone(status_column.server_default)
        self.assertEqual(str(status_column.server_default.arg), SkeletonStatus.DRAFT.value)

    def test_skeleton_spacing_defaults(self) -> None:
        """Spacing columns are non-null integers defaulting to 96 / 0 / 0."""

        page_margin_column: Column[object] = Skeleton.__table__.columns["page_margin"]
        element_gap_column: Column[object] = Skeleton.__table__.columns["element_gap"]
        element_margin_column: Column[object] = Skeleton.__table__.columns["element_margin"]

        self.assertFalse(page_margin_column.nullable)
        self.assertFalse(element_gap_column.nullable)
        self.assertFalse(element_margin_column.nullable)
        self.assertEqual(str(page_margin_column.server_default.arg), "96")
        self.assertEqual(str(element_gap_column.server_default.arg), "0")
        self.assertEqual(str(element_margin_column.server_default.arg), "0")

    def test_skeleton_background_defaults(self) -> None:
        """Background kind defaults to color and paper; payloads may be null."""

        self.assertEqual(
            {member.value for member in BackgroundKind},
            {"picture", "color", "gradient"},
        )
        kind_column: Column[object] = Skeleton.__table__.columns["background_kind"]
        color_column: Column[object] = Skeleton.__table__.columns["background_color"]
        gradient_column: Column[object] = Skeleton.__table__.columns["background_gradient"]
        asset_column: Column[object] = Skeleton.__table__.columns["background_asset_ref"]

        self.assertFalse(kind_column.nullable)
        self.assertTrue(color_column.nullable)
        self.assertTrue(gradient_column.nullable)
        self.assertTrue(asset_column.nullable)
        self.assertEqual(str(kind_column.server_default.arg), "color")
        self.assertEqual(str(color_column.server_default.arg), "#F6F1E8")
        self.assertIsNone(gradient_column.server_default)
        self.assertIsNone(asset_column.server_default)

    def test_skeleton_element_maps_columns_and_content_check(self) -> None:
        """skeleton_elements maps the locked columns and rejects placement fields."""

        column_names: set[str] = set(SkeletonElement.__table__.columns.keys())
        expected_column_names: set[str] = {
            "id",
            "skeleton_id",
            "band",
            "sort_order",
            "content_kind",
            "name",
            "rectangle_color",
            "rectangle_opacity",
            "rectangle_radius",
            "text_source",
            "font_family",
            "font_size",
            "font_color",
            "bold",
            "italic",
            "underline",
            "strikethrough",
            "font_weight",
            "alignment",
            "image_asset_ref",
            "created_at",
            "updated_at",
        }

        self.assertEqual(column_names, expected_column_names)
        self.assertTrue({"x", "y", "width"}.isdisjoint(column_names))
        self.assertEqual(
            {member.value for member in SkeletonElementBand},
            {"top", "middle", "bottom"},
        )
        self.assertEqual(
            {member.value for member in SkeletonElementContentKind},
            {"text", "image"},
        )
        self.assertEqual(
            {member.value for member in SkeletonElementTextSource},
            {"title", "interest_heading", "overview_bullets", "canonical_url"},
        )
        self.assertEqual(
            {member.value for member in SkeletonElementAlignment},
            {"left", "center", "right"},
        )
        self.assertIn(
            ("skeleton_id", "band", "sort_order"),
            _unique_column_tuples(SkeletonElement.__table__),
        )

        skeleton_id_column: Column[object] = SkeletonElement.__table__.columns["skeleton_id"]
        skeleton_foreign_key: ForeignKey = next(iter(skeleton_id_column.foreign_keys))

        self.assertEqual(skeleton_foreign_key.column.table.name, "skeletons")
        self.assertEqual(skeleton_foreign_key.ondelete, "CASCADE")
        self.assertFalse(SkeletonElement.__table__.columns["sort_order"].nullable)
        self.assertFalse(SkeletonElement.__table__.columns["name"].nullable)
        self.assertTrue(SkeletonElement.__table__.columns["rectangle_color"].nullable)
        opacity_column: Column[object] = SkeletonElement.__table__.columns["rectangle_opacity"]
        radius_column: Column[object] = SkeletonElement.__table__.columns["rectangle_radius"]

        self.assertFalse(opacity_column.nullable)
        self.assertFalse(radius_column.nullable)
        self.assertEqual(str(opacity_column.server_default.arg), "100")
        self.assertEqual(str(radius_column.server_default.arg), "0")
        self.assertTrue(SkeletonElement.__table__.columns["text_source"].nullable)
        self.assertTrue(SkeletonElement.__table__.columns["font_weight"].nullable)
        self.assertTrue(SkeletonElement.__table__.columns["image_asset_ref"].nullable)
        self.assertTrue(SkeletonElement.__table__.columns["alignment"].nullable)

        for style_column_name in ("bold", "italic", "underline", "strikethrough"):
            style_column: Column[object] = SkeletonElement.__table__.columns[
                style_column_name
            ]

            self.assertFalse(style_column.nullable)
            self.assertIsNotNone(style_column.server_default)
            self.assertEqual(str(style_column.server_default.arg), "false")

        content_checks: list[CheckConstraint] = [
            table_constraint
            for table_constraint in SkeletonElement.__table__.constraints
            if isinstance(table_constraint, CheckConstraint)
        ]

        checks_by_name: dict[str, CheckConstraint] = {
            table_constraint.name: table_constraint
            for table_constraint in content_checks
            if table_constraint.name is not None
        }

        self.assertEqual(
            set(checks_by_name),
            {
                "ck_skeleton_elements_content",
                "ck_skeleton_elements_rectangle_style",
                "ck_skeleton_elements_name",
            },
        )
        self.assertEqual(
            str(checks_by_name["ck_skeleton_elements_content"].sqltext),
            SKELETON_ELEMENT_CONTENT_CHECK_SQL,
        )
        self.assertIn(
            "rectangle_opacity >= 0 AND rectangle_opacity <= 100",
            str(checks_by_name["ck_skeleton_elements_rectangle_style"].sqltext),
        )
        self.assertIn(
            "rectangle_radius >= 0 AND rectangle_radius <= 10000",
            str(checks_by_name["ck_skeleton_elements_rectangle_style"].sqltext),
        )
        self.assertIn(
            "content_kind = 'text'::skeleton_element_content_kind",
            SKELETON_ELEMENT_CONTENT_CHECK_SQL,
        )
        self.assertIn("text_source IS NULL", SKELETON_ELEMENT_CONTENT_CHECK_SQL)
        self.assertIn("font_size > 0", SKELETON_ELEMENT_CONTENT_CHECK_SQL)
        self.assertIn(
            "font_weight >= 1 AND font_weight <= 1000",
            SKELETON_ELEMENT_CONTENT_CHECK_SQL,
        )
        self.assertIn(
            "strpos(image_asset_ref, '..') = 0",
            SKELETON_ELEMENT_CONTENT_CHECK_SQL,
        )
        self.assertIn(".jpeg", SKELETON_ELEMENT_CONTENT_CHECK_SQL)
        self.assertEqual(
            str(checks_by_name["ck_skeleton_elements_name"].sqltext),
            SKELETON_ELEMENT_NAME_CHECK_SQL,
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
