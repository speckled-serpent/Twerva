"""Persist 1.5 approve / cadence / schedule against Postgres when reachable."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.artifacts import (
    approve_artifact_by_id,
    create_artifact,
    list_artifacts,
    patch_artifact_by_id,
    reject_artifact_by_id,
)
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster
from app.api.v1.post_jobs import create_post_job
from app.api.v1.schedule import schedule_post_job
from app.api.v1.schemas import (
    AccountCreateRequest,
    ArtifactApproveRequest,
    ArtifactCreateRequest,
    ArtifactPatchRequest,
    BrandCreateRequest,
    ClusterCreateRequest,
    PostJobCreateRequest,
    SchedulePostJobRequest,
    SourceItemCreateRequest,
)
from app.api.v1.source_items import create_source_item
from app.models.enums import ArtifactStatus, Platform, PostJobStatus


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)

SCHEDULED_FOR: datetime = datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc)


def _connect_test_engine() -> Engine | None:
    """Return an engine for the first reachable candidate URL, if any."""

    for candidate_database_url in CANDIDATE_DATABASE_URLS:

        if candidate_database_url == "":
            continue

        normalized_database_url: str = candidate_database_url

        if normalized_database_url.startswith("postgresql://"):
            remainder: str = normalized_database_url[len("postgresql://"):]
            normalized_database_url = f"postgresql+psycopg://{remainder}"

        candidate_engine: Engine | None = None

        try:
            candidate_engine = create_engine(normalized_database_url)
            with candidate_engine.connect() as our_database_connection:
                our_database_connection.execute(text("SELECT 1"))
        except OperationalError:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        except Exception:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        else:

            return candidate_engine

    return None


TEST_ENGINE: Engine | None = _connect_test_engine()


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for 1.5 persist tests")
class ApproveSchedulePersistTests(unittest.TestCase):
    """1.5a–1.5c: review queue, cadence 409, schedule from approved."""

    def setUp(self) -> None:
        """Open a session on the reachable test engine."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for 1.5 persist tests")

        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()
        self.run_suffix: str = uuid.uuid4().hex[:8]
        self.created_brand = create_brand(
            BrandCreateRequest(
                slug=f"approve-{self.run_suffix}",
                name="Approve Brand",
            ),
            self.our_database_session,
        )
        self.created_source_item = create_source_item(
            SourceItemCreateRequest(
                brand_id=self.created_brand.id,
                title="Approve carousel",
                interest_heading="Approve heading",
                overview_bullets=["a", "b", "c"],
                canonical_url="https://spotmu.com/interest/example",
                external_key=f"approve-{self.run_suffix}",
            ),
            self.our_database_session,
        )
        self.created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=self.created_brand.id,
                slug=f"approve-lane-{self.run_suffix}",
                name="Approve lane",
            ),
            self.our_database_session,
        )
        self.created_account = create_account(
            AccountCreateRequest(
                cluster_id=self.created_cluster.id,
                platform=Platform.INSTAGRAM,
                handle=f"approve_{self.run_suffix}",
                cadence_cap_per_day=1,
            ),
            self.our_database_session,
        )

    def tearDown(self) -> None:
        """Close the request-scoped test session."""

        if getattr(self, "our_database_session", None) is not None:
            self.our_database_session.close()

    def test_review_queue_approve_reject_patch_and_list_drafts(self) -> None:
        """Draft list, PATCH caption, approve, reject cannot re-approve."""

        created_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
                caption="original",
            ),
            self.our_database_session,
        )
        listed_drafts = list_artifacts(
            artifact_status=ArtifactStatus.DRAFT,
            our_database_session=self.our_database_session,
        )
        listed_draft_ids: set[uuid.UUID] = {
            artifact_response.id for artifact_response in listed_drafts
        }

        self.assertIn(created_artifact.id, listed_draft_ids)

        patched_artifact = patch_artifact_by_id(
            created_artifact.id,
            ArtifactPatchRequest(caption="patched caption"),
            self.our_database_session,
        )

        self.assertEqual(patched_artifact.caption, "patched caption")
        self.assertEqual(patched_artifact.status, ArtifactStatus.DRAFT)

        approved_artifact = approve_artifact_by_id(
            created_artifact.id,
            ArtifactApproveRequest(caption="approved caption"),
            self.our_database_session,
        )

        self.assertEqual(approved_artifact.status, ArtifactStatus.APPROVED)
        self.assertEqual(approved_artifact.caption, "approved caption")
        self.assertIsNotNone(approved_artifact.approved_at)

        listed_drafts_after_approve = list_artifacts(
            artifact_status=ArtifactStatus.DRAFT,
            our_database_session=self.our_database_session,
        )
        draft_ids_after_approve: set[uuid.UUID] = {
            artifact_response.id for artifact_response in listed_drafts_after_approve
        }

        self.assertNotIn(created_artifact.id, draft_ids_after_approve)

        rejected_artifact = reject_artifact_by_id(
            created_artifact.id,
            None,
            self.our_database_session,
        )

        self.assertEqual(rejected_artifact.status, ArtifactStatus.REJECTED)

        with self.assertRaises(HTTPException) as raised_reapprove:
            approve_artifact_by_id(
                created_artifact.id,
                None,
                self.our_database_session,
            )

        self.assertEqual(raised_reapprove.exception.status_code, 409)

        with self.assertRaises(HTTPException) as raised_patch:
            patch_artifact_by_id(
                created_artifact.id,
                ArtifactPatchRequest(caption="too late"),
                self.our_database_session,
            )

        self.assertEqual(raised_patch.exception.status_code, 409)

    def test_schedule_approved_then_cadence_cap_returns_409(self) -> None:
        """First schedule at cap=1 succeeds; second same UTC day is 409."""

        first_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        approve_artifact_by_id(first_artifact.id, None, self.our_database_session)
        first_post_job = schedule_post_job(
            SchedulePostJobRequest(
                artifact_id=first_artifact.id,
                account_id=self.created_account.id,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.our_database_session,
        )

        self.assertEqual(first_post_job.status, PostJobStatus.SCHEDULED)
        self.assertEqual(first_post_job.account_id, self.created_account.id)

        second_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        approve_artifact_by_id(second_artifact.id, None, self.our_database_session)

        with self.assertRaises(HTTPException) as raised_cap:
            schedule_post_job(
                SchedulePostJobRequest(
                    artifact_id=second_artifact.id,
                    account_id=self.created_account.id,
                    scheduled_for=SCHEDULED_FOR,
                ),
                self.our_database_session,
            )

        self.assertEqual(raised_cap.exception.status_code, 409)
        self.assertIn("Cadence cap exceeded", str(raised_cap.exception.detail))

    def test_failed_job_does_not_consume_cadence_slot(self) -> None:
        """A failed post_job on the same UTC day leaves the cap open."""

        failed_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        create_post_job(
            PostJobCreateRequest(
                artifact_id=failed_artifact.id,
                account_id=self.created_account.id,
                status=PostJobStatus.FAILED,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.our_database_session,
        )
        approved_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        approve_artifact_by_id(
            approved_artifact.id,
            None,
            self.our_database_session,
        )
        created_post_job = schedule_post_job(
            SchedulePostJobRequest(
                artifact_id=approved_artifact.id,
                account_id=self.created_account.id,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.our_database_session,
        )

        self.assertEqual(created_post_job.status, PostJobStatus.SCHEDULED)

    def test_schedule_draft_returns_409(self) -> None:
        """Draft artifacts cannot be scheduled."""

        draft_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )

        with self.assertRaises(HTTPException) as raised_draft:
            schedule_post_job(
                SchedulePostJobRequest(
                    artifact_id=draft_artifact.id,
                    account_id=self.created_account.id,
                    scheduled_for=SCHEDULED_FOR,
                ),
                self.our_database_session,
            )

        self.assertEqual(raised_draft.exception.status_code, 409)

    def test_schedule_cluster_mismatch_returns_400(self) -> None:
        """Artifact with cluster_id cannot schedule to a different cluster."""

        other_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=self.created_brand.id,
                slug=f"other-lane-{self.run_suffix}",
                name="Other lane",
            ),
            self.our_database_session,
        )
        other_account = create_account(
            AccountCreateRequest(
                cluster_id=other_cluster.id,
                platform=Platform.TIKTOK,
                handle=f"approve_other_{self.run_suffix}",
            ),
            self.our_database_session,
        )
        clustered_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                source_item_id=self.created_source_item.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        approve_artifact_by_id(
            clustered_artifact.id,
            None,
            self.our_database_session,
        )

        with self.assertRaises(HTTPException) as raised_cluster:
            schedule_post_job(
                SchedulePostJobRequest(
                    artifact_id=clustered_artifact.id,
                    account_id=other_account.id,
                    scheduled_for=SCHEDULED_FOR,
                ),
                self.our_database_session,
            )

        self.assertEqual(raised_cluster.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
