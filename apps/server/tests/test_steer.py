"""Steer side effects on cluster `is_active` (1.7c-ii) — no Postgres."""

import unittest
import uuid

from app.metrics.errors import StubMetricsNotAvailableError
from app.metrics.service import append_metric_snapshot, append_stub_metric_snapshot
from app.metrics.stub import (
    STUB_MOCK_COMMENTS,
    STUB_MOCK_LIKES,
    STUB_MOCK_SHARES,
    STUB_MOCK_VIEWS,
)
from app.models import Cluster, MetricSnapshot, PostJob, SteerAction
from app.models.enums import PostJobStatus, SteerActionType
from app.steer.service import apply_steer_action_to_cluster


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_POST_JOB_ID: uuid.UUID = uuid.UUID("66666666-6666-6666-6666-666666666666")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")


class SteerSideEffectTests(unittest.TestCase):
    """1.7c-ii: pause/kill deactivate; resume reactivates; double_down logs only."""

    def test_pause_sets_cluster_inactive(self) -> None:
        """Pause writes a steer row and sets is_active false."""

        cluster: Cluster = _active_cluster()
        steer_action: SteerAction = apply_steer_action_to_cluster(
            cluster,
            SteerActionType.PAUSE,
            reason="median below floor",
            created_by="human",
        )

        self.assertFalse(cluster.is_active)
        self.assertEqual(steer_action.action, SteerActionType.PAUSE)
        self.assertEqual(steer_action.cluster_id, FIXED_CLUSTER_ID)
        self.assertEqual(steer_action.reason, "median below floor")
        self.assertEqual(steer_action.created_by, "human")

    def test_kill_sets_cluster_inactive(self) -> None:
        """Kill uses the same cluster flag as pause; action string differs."""

        cluster: Cluster = _active_cluster()
        steer_action: SteerAction = apply_steer_action_to_cluster(
            cluster,
            SteerActionType.KILL,
            reason="lane dead",
        )

        self.assertFalse(cluster.is_active)
        self.assertEqual(steer_action.action, SteerActionType.KILL)

    def test_resume_sets_cluster_active(self) -> None:
        """Resume turns a paused cluster back on."""

        cluster: Cluster = _active_cluster()
        cluster.is_active = False
        steer_action: SteerAction = apply_steer_action_to_cluster(
            cluster,
            SteerActionType.RESUME,
            reason="try again",
        )

        self.assertTrue(cluster.is_active)
        self.assertEqual(steer_action.action, SteerActionType.RESUME)

    def test_double_down_does_not_change_is_active(self) -> None:
        """MVP double_down is log-only (no cadence bump)."""

        active_cluster: Cluster = _active_cluster()
        active_steer_action: SteerAction = apply_steer_action_to_cluster(
            active_cluster,
            SteerActionType.DOUBLE_DOWN,
            reason="above floor",
        )
        paused_cluster: Cluster = _active_cluster()
        paused_cluster.is_active = False
        paused_steer_action: SteerAction = apply_steer_action_to_cluster(
            paused_cluster,
            SteerActionType.DOUBLE_DOWN,
            reason="still paused",
        )

        self.assertTrue(active_cluster.is_active)
        self.assertFalse(paused_cluster.is_active)
        self.assertEqual(active_steer_action.action, SteerActionType.DOUBLE_DOWN)
        self.assertEqual(paused_steer_action.action, SteerActionType.DOUBLE_DOWN)

    def test_resume_of_already_active_cluster_stays_active(self) -> None:
        """Resume is idempotent on the flag."""

        cluster: Cluster = _active_cluster()
        apply_steer_action_to_cluster(cluster, SteerActionType.RESUME)

        self.assertTrue(cluster.is_active)


class MetricMeasuredTransitionTests(unittest.TestCase):
    """Appending metrics promotes published/failed jobs to measured."""

    def test_published_job_becomes_measured(self) -> None:
        """Happy-path measure mark after a snapshot."""

        post_job: PostJob = _post_job(PostJobStatus.PUBLISHED)
        append_metric_snapshot(post_job, views=10, likes=1, comments=0, shares=0)

        self.assertEqual(post_job.status, PostJobStatus.MEASURED)

    def test_failed_job_becomes_measured(self) -> None:
        """Failed → measured is an allowed close-out."""

        post_job: PostJob = _post_job(PostJobStatus.FAILED)
        append_metric_snapshot(post_job, views=0, likes=None, comments=None, shares=None)

        self.assertEqual(post_job.status, PostJobStatus.MEASURED)

    def test_scheduled_job_keeps_status(self) -> None:
        """Snapshots may be stored without a scheduled → measured jump."""

        post_job: PostJob = _post_job(PostJobStatus.SCHEDULED)
        append_metric_snapshot(post_job, views=3, likes=None, comments=None, shares=None)

        self.assertEqual(post_job.status, PostJobStatus.SCHEDULED)

    def test_already_measured_job_stays_measured(self) -> None:
        """A second snapshot does not fight the terminal status."""

        post_job: PostJob = _post_job(PostJobStatus.MEASURED)
        append_metric_snapshot(post_job, views=99, likes=None, comments=None, shares=None)

        self.assertEqual(post_job.status, PostJobStatus.MEASURED)


class StubMetricsUnitTests(unittest.TestCase):
    """1.7a-ii: stub only copies views for mock-published jobs."""

    def test_stub_writes_documented_counts_for_mock_id(self) -> None:
        """Mock platform_post_id gets views=100 / likes=10 / comments=2 / shares=1."""

        post_job: PostJob = _post_job(PostJobStatus.PUBLISHED)
        post_job.platform_post_id = f"mock-instagram-{FIXED_POST_JOB_ID}"
        metric_snapshot: MetricSnapshot = append_stub_metric_snapshot(post_job)

        self.assertEqual(metric_snapshot.views, STUB_MOCK_VIEWS)
        self.assertEqual(metric_snapshot.likes, STUB_MOCK_LIKES)
        self.assertEqual(metric_snapshot.comments, STUB_MOCK_COMMENTS)
        self.assertEqual(metric_snapshot.shares, STUB_MOCK_SHARES)
        self.assertEqual(post_job.status, PostJobStatus.MEASURED)

    def test_stub_rejects_non_mock_platform_post_id(self) -> None:
        """Live vendor ids are not invented by the stub."""

        post_job: PostJob = _post_job(PostJobStatus.PUBLISHED)
        post_job.platform_post_id = "ayrshare-not-real"

        with self.assertRaises(StubMetricsNotAvailableError):
            append_stub_metric_snapshot(post_job)


def _active_cluster() -> Cluster:
    """In-memory Cluster used for steer flag tests."""

    cluster: Cluster = Cluster(
        id=FIXED_CLUSTER_ID,
        brand_id=FIXED_BRAND_ID,
        slug="steer-lane",
        name="Steer lane",
        is_active=True,
    )

    return cluster


def _post_job(status: PostJobStatus) -> PostJob:
    """In-memory PostJob for measure-transition tests."""

    post_job: PostJob = PostJob(
        id=FIXED_POST_JOB_ID,
        artifact_id=FIXED_ARTIFACT_ID,
        account_id=FIXED_ACCOUNT_ID,
        status=status,
    )

    return post_job


if __name__ == "__main__":
    unittest.main()
