"""Pydantic create/read schemas for the 1.2l persist-proof API."""

import unittest
import uuid
from datetime import datetime, timezone

from app.api.v1.schemas import (
    AccountCreateRequest,
    AccountReadResponse,
    ArtifactCreateRequest,
    ArtifactReadResponse,
    ArtifactSlideSchema,
    BrandCreateRequest,
    BrandReadResponse,
    ClusterCreateRequest,
    ClusterReadResponse,
    MetricSnapshotCreateRequest,
    MetricSnapshotReadResponse,
    PostJobCreateRequest,
    PostJobReadResponse,
    SourceItemCreateRequest,
    SourceItemReadResponse,
)
from app.models.enums import (
    AccountStatus,
    ArtifactStatus,
    Platform,
    PostJobStatus,
    SourceType,
)


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FIXED_SOURCE_ITEM_ID: uuid.UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_POST_JOB_ID: uuid.UUID = uuid.UUID("66666666-6666-6666-6666-666666666666")
FIXED_SNAPSHOT_ID: uuid.UUID = uuid.UUID("77777777-7777-7777-7777-777777777777")
FIXED_TIMESTAMP: datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


class ApiSchemaTests(unittest.TestCase):
    """1.2l-i: create/read models accept the Phase 1 field sets."""

    def test_brand_create_and_read_round_trip_fields(self) -> None:
        """Brand schemas cover slug, name, and optional notes."""

        brand_create_request: BrandCreateRequest = BrandCreateRequest(
            slug="spotmu",
            name="Spotmu",
            notes="customer zero",
        )
        brand_read_response: BrandReadResponse = BrandReadResponse(
            id=FIXED_BRAND_ID,
            slug=brand_create_request.slug,
            name=brand_create_request.name,
            notes=brand_create_request.notes,
            voice_notes=None,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(brand_create_request.slug, "spotmu")
        self.assertEqual(brand_read_response.name, "Spotmu")
        self.assertIsNone(brand_read_response.voice_notes)

    def test_source_item_defaults_to_spotmu_interest(self) -> None:
        """SourceItem create defaults match the Phase 1 hose."""

        source_item_create_request: SourceItemCreateRequest = SourceItemCreateRequest(
            brand_id=FIXED_BRAND_ID,
            title="Example Spotmu interest",
            interest_heading="What this example lane is about",
            overview_bullets=["one", "two", "three"],
            canonical_url="https://spotmu.com/interest/example",
        )

        self.assertEqual(
            source_item_create_request.source_type,
            SourceType.SPOTMU_INTEREST,
        )
        self.assertEqual(len(source_item_create_request.overview_bullets), 3)

        source_item_read_response: SourceItemReadResponse = SourceItemReadResponse(
            id=FIXED_SOURCE_ITEM_ID,
            brand_id=FIXED_BRAND_ID,
            source_type=SourceType.SPOTMU_INTEREST,
            external_key="example",
            title=source_item_create_request.title,
            interest_heading=source_item_create_request.interest_heading,
            overview_bullets=source_item_create_request.overview_bullets,
            canonical_url=source_item_create_request.canonical_url,
            brand_kit_refs=None,
            raw_payload=None,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(
            source_item_read_response.canonical_url,
            "https://spotmu.com/interest/example",
        )

    def test_cluster_and_account_create_defaults(self) -> None:
        """Cluster is active; Account is active and carries platform/handle."""

        cluster_create_request: ClusterCreateRequest = ClusterCreateRequest(
            brand_id=FIXED_BRAND_ID,
            slug="example-lane",
            name="Example lane",
        )
        account_create_request: AccountCreateRequest = AccountCreateRequest(
            cluster_id=FIXED_CLUSTER_ID,
            platform=Platform.INSTAGRAM,
            handle="spotmu_example",
        )

        self.assertTrue(cluster_create_request.is_active)
        self.assertEqual(account_create_request.status, AccountStatus.ACTIVE)

        cluster_read_response: ClusterReadResponse = ClusterReadResponse(
            id=FIXED_CLUSTER_ID,
            brand_id=FIXED_BRAND_ID,
            slug="example-lane",
            name="Example lane",
            description=None,
            is_active=True,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )
        account_read_response: AccountReadResponse = AccountReadResponse(
            id=FIXED_ACCOUNT_ID,
            cluster_id=FIXED_CLUSTER_ID,
            platform=Platform.INSTAGRAM,
            handle="spotmu_example",
            external_account_id=None,
            status=AccountStatus.ACTIVE,
            cadence_cap_per_day=None,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )

        self.assertTrue(cluster_read_response.is_active)
        self.assertEqual(account_read_response.platform, Platform.INSTAGRAM)

    def test_artifact_and_post_job_include_status(self) -> None:
        """1.2l-iii: Artifact and PostJob schemas expose status."""

        artifact_create_request: ArtifactCreateRequest = ArtifactCreateRequest(
            brand_id=FIXED_BRAND_ID,
            source_item_id=FIXED_SOURCE_ITEM_ID,
            cluster_id=FIXED_CLUSTER_ID,
            slides=[ArtifactSlideSchema(role="cover", text="Hello")],
        )
        post_job_create_request: PostJobCreateRequest = PostJobCreateRequest(
            artifact_id=FIXED_ARTIFACT_ID,
            account_id=FIXED_ACCOUNT_ID,
        )

        self.assertEqual(artifact_create_request.status, ArtifactStatus.DRAFT)
        self.assertEqual(post_job_create_request.status, PostJobStatus.SCHEDULED)

        artifact_read_response: ArtifactReadResponse = ArtifactReadResponse(
            id=FIXED_ARTIFACT_ID,
            brand_id=FIXED_BRAND_ID,
            source_item_id=FIXED_SOURCE_ITEM_ID,
            cluster_id=FIXED_CLUSTER_ID,
            status=ArtifactStatus.DRAFT,
            format="carousel",
            caption=None,
            cta_url=None,
            slides=[{"role": "cover", "text": "Hello"}],
            approved_at=None,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )
        post_job_read_response: PostJobReadResponse = PostJobReadResponse(
            id=FIXED_POST_JOB_ID,
            artifact_id=FIXED_ARTIFACT_ID,
            account_id=FIXED_ACCOUNT_ID,
            status=PostJobStatus.SCHEDULED,
            scheduled_for=None,
            published_at=None,
            platform_post_id=None,
            platform_post_url=None,
            last_error=None,
            created_at=FIXED_TIMESTAMP,
            updated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(artifact_read_response.status, ArtifactStatus.DRAFT)
        self.assertEqual(post_job_read_response.status, PostJobStatus.SCHEDULED)

    def test_metric_snapshot_create_schema_is_available(self) -> None:
        """1.2l-i: MetricSnapshot create/read schemas exist (routes optional)."""

        snapshot_create_request: MetricSnapshotCreateRequest = (
            MetricSnapshotCreateRequest(
                post_job_id=FIXED_POST_JOB_ID,
                captured_at=FIXED_TIMESTAMP,
                views=100,
            )
        )
        snapshot_read_response: MetricSnapshotReadResponse = (
            MetricSnapshotReadResponse(
                id=FIXED_SNAPSHOT_ID,
                post_job_id=FIXED_POST_JOB_ID,
                captured_at=FIXED_TIMESTAMP,
                views=100,
                likes=None,
                comments=None,
                shares=None,
                raw=None,
            )
        )

        self.assertEqual(snapshot_create_request.views, 100)
        self.assertEqual(snapshot_read_response.post_job_id, FIXED_POST_JOB_ID)


if __name__ == "__main__":
    unittest.main()
