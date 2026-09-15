"""Persist 1.7 metrics, median, and steer against Postgres when reachable."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.artifacts import create_artifact
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster, get_cluster_by_id
from app.api.v1.metrics import (
    create_post_job_metric_snapshot,
    create_stub_post_job_metric_snapshot,
)
from app.api.v1.post_jobs import create_post_job, get_post_job_by_id
from app.api.v1.schemas import (
    AccountCreateRequest,
    ArtifactCreateRequest,
    BrandCreateRequest,
    ClusterAgentSummaryResponse,
    ClusterCreateRequest,
    ClusterSteerRequest,
    PostJobCreateRequest,
    PostJobMetricsCreateRequest,
    PostJobReadResponse,
)
from app.api.v1.steer import (
    create_cluster_steer_action,
    get_cluster_agent_summary,
    get_cluster_metrics_summary,
)
from app.models.enums import (
    ArtifactStatus,
    Platform,
    PostJobStatus,
    SteerActionType,
)


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)

FIRST_CAPTURED_AT: datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
SECOND_CAPTURED_AT: datetime = FIRST_CAPTURED_AT + timedelta(hours=1)


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


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for 1.7 persist tests")
class MeasureSteerPersistTests(unittest.TestCase):
    """1.7: metrics append, median latest-wins, pause/resume, agent-summary."""

    def setUp(self) -> None:
        """Open a session and seed a brand / cluster / account / artifact."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for 1.7 persist tests")

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
                slug=f"measure-{self.run_suffix}",
                name="Measure Brand",
            ),
            self.our_database_session,
        )
        self.created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=self.created_brand.id,
                slug=f"measure-lane-{self.run_suffix}",
                name="Measure lane",
            ),
            self.our_database_session,
        )
        self.created_account = create_account(
            AccountCreateRequest(
                cluster_id=self.created_cluster.id,
                platform=Platform.INSTAGRAM,
                handle=f"measure_{self.run_suffix}",
            ),
            self.our_database_session,
        )
        self.created_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.created_brand.id,
                cluster_id=self.created_cluster.id,
                status=ArtifactStatus.APPROVED,
            ),
            self.our_database_session,
        )

    def tearDown(self) -> None:
        """Close the session."""

        if getattr(self, "our_database_session", None) is not None:
            self.our_database_session.close()

    def test_empty_cluster_median_is_null(self) -> None:
        """No snapshots → median_views is None, counts are zero."""

        summary = get_cluster_metrics_summary(
            self.created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(summary.post_job_count, 0)
        self.assertEqual(summary.snapshot_job_count, 0)
        self.assertEqual(summary.views_job_count, 0)
        self.assertIsNone(summary.median_views)

    def test_metrics_latest_wins_median_and_measured_status(self) -> None:
        """Three jobs, latest views 10/20/30 → median 20; published → measured."""

        first_post_job = self._create_published_post_job()
        second_post_job = self._create_published_post_job()
        third_post_job = self._create_published_post_job()
        create_post_job_metric_snapshot(
            first_post_job.id,
            PostJobMetricsCreateRequest(views=5, captured_at=FIRST_CAPTURED_AT),
            self.our_database_session,
        )
        create_post_job_metric_snapshot(
            first_post_job.id,
            PostJobMetricsCreateRequest(views=10, captured_at=SECOND_CAPTURED_AT),
            self.our_database_session,
        )
        create_post_job_metric_snapshot(
            second_post_job.id,
            PostJobMetricsCreateRequest(views=20, captured_at=SECOND_CAPTURED_AT),
            self.our_database_session,
        )
        create_post_job_metric_snapshot(
            third_post_job.id,
            PostJobMetricsCreateRequest(views=30, captured_at=SECOND_CAPTURED_AT),
            self.our_database_session,
        )
        summary = get_cluster_metrics_summary(
            self.created_cluster.id,
            self.our_database_session,
        )
        first_after: PostJobReadResponse = get_post_job_by_id(
            first_post_job.id,
            self.our_database_session,
        )

        self.assertEqual(summary.post_job_count, 3)
        self.assertEqual(summary.snapshot_job_count, 3)
        self.assertEqual(summary.views_job_count, 3)
        self.assertEqual(summary.median_views, 20.0)
        self.assertEqual(first_after.status, PostJobStatus.MEASURED)

    def test_pause_resume_and_double_down_side_effects(self) -> None:
        """Pause/kill deactivate; resume reactivates; double_down leaves the flag."""

        pause_action = create_cluster_steer_action(
            self.created_cluster.id,
            ClusterSteerRequest(action=SteerActionType.PAUSE, reason="low median"),
            self.our_database_session,
        )
        paused_cluster = get_cluster_by_id(
            self.created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(pause_action.action, SteerActionType.PAUSE)
        self.assertFalse(paused_cluster.is_active)

        double_down_while_paused = create_cluster_steer_action(
            self.created_cluster.id,
            ClusterSteerRequest(action=SteerActionType.DOUBLE_DOWN),
            self.our_database_session,
        )
        still_paused = get_cluster_by_id(
            self.created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(double_down_while_paused.action, SteerActionType.DOUBLE_DOWN)
        self.assertFalse(still_paused.is_active)

        resume_action = create_cluster_steer_action(
            self.created_cluster.id,
            ClusterSteerRequest(action=SteerActionType.RESUME, reason="retry"),
            self.our_database_session,
        )
        resumed_cluster = get_cluster_by_id(
            self.created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(resume_action.action, SteerActionType.RESUME)
        self.assertTrue(resumed_cluster.is_active)

        kill_action = create_cluster_steer_action(
            self.created_cluster.id,
            ClusterSteerRequest(action=SteerActionType.KILL),
            self.our_database_session,
        )
        killed_cluster = get_cluster_by_id(
            self.created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(kill_action.action, SteerActionType.KILL)
        self.assertFalse(killed_cluster.is_active)

    def test_stub_metrics_for_mock_id_and_agent_summary_formats(self) -> None:
        """Stub writes 100 views; JSON + markdown summaries include the cluster."""

        mock_post_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=self.created_artifact.id,
                account_id=self.created_account.id,
                status=PostJobStatus.PUBLISHED,
                platform_post_id=f"mock-instagram-{uuid.uuid4()}",
            ),
            self.our_database_session,
        )
        stub_snapshot = create_stub_post_job_metric_snapshot(
            mock_post_job.id,
            self.our_database_session,
        )
        json_summary = get_cluster_agent_summary(
            self.created_cluster.id,
            "json",
            self.our_database_session,
        )
        markdown_summary = get_cluster_agent_summary(
            self.created_cluster.id,
            "markdown",
            self.our_database_session,
        )

        self.assertEqual(stub_snapshot.views, 100)
        self.assertIsInstance(json_summary, ClusterAgentSummaryResponse)
        self.assertEqual(json_summary.metrics.median_views, 100.0)
        self.assertEqual(json_summary.is_active, True)
        self.assertEqual(len(json_summary.recent_post_jobs), 1)
        self.assertEqual(json_summary.recent_post_jobs[0].latest_views, 100)
        self.assertIsInstance(markdown_summary, FastAPIResponse)
        markdown_body: str = markdown_summary.body.decode("utf-8")
        self.assertIn("median views: 100.0", markdown_body)
        self.assertIn(self.created_cluster.slug, markdown_body)

        live_post_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=self.created_artifact.id,
                account_id=self.created_account.id,
                status=PostJobStatus.PUBLISHED,
                platform_post_id="not-a-mock-id",
            ),
            self.our_database_session,
        )

        with self.assertRaises(HTTPException) as raised_stub:
            create_stub_post_job_metric_snapshot(
                live_post_job.id,
                self.our_database_session,
            )

        self.assertEqual(raised_stub.exception.status_code, 409)

    def _create_published_post_job(self) -> PostJobReadResponse:
        """Persist a published PostJob on the smoke account."""

        created_post_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=self.created_artifact.id,
                account_id=self.created_account.id,
                status=PostJobStatus.PUBLISHED,
            ),
            self.our_database_session,
        )

        return created_post_job


if __name__ == "__main__":
    unittest.main()
