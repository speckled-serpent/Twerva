"""Append metric snapshots and roll up latest-wins views (1.7a–1.7b)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.metrics.errors import StubMetricsNotAvailableError
from app.metrics.median import calculate_median_of_numbers
from app.metrics.stub import (
    STUB_MOCK_COMMENTS,
    STUB_MOCK_LIKES,
    STUB_MOCK_SHARES,
    STUB_MOCK_VIEWS,
    post_job_is_mock_published,
)
from app.models import Account, MetricSnapshot, PostJob
from app.models.enums import POST_JOB_STATUS_TRANSITIONS, PostJobStatus


MEASUREABLE_POST_JOB_STATUSES: frozenset[PostJobStatus] = frozenset(
    {PostJobStatus.PUBLISHED, PostJobStatus.FAILED},
)


def append_metric_snapshot(
    post_job: PostJob,
    views: int | None,
    likes: int | None,
    comments: int | None,
    shares: int | None,
    captured_at: datetime | None = None,
    raw: dict[str, object] | list[object] | None = None,
) -> MetricSnapshot:
    """Build an uncommitted `MetricSnapshot` and maybe mark the job measured.

    Multiple rows per job are allowed (latest-wins). `published` and
    `failed` jobs move to `measured`. Other statuses keep their status
    so a snapshot can still be recorded on a scheduled row.

    Args:
        post_job: Job the snapshot belongs to (mutated when measured).
        views: View count, or None.
        likes: Like count, or None.
        comments: Comment count, or None.
        shares: Share count, or None.
        captured_at: Override for tests; default is UTC now.
        raw: Optional vendor payload passthrough.

    Returns:
        The new MetricSnapshot instance (not yet added to a session).
    """

    resolved_captured_at: datetime = _resolve_captured_at(captured_at)
    metric_snapshot: MetricSnapshot = MetricSnapshot(
        post_job_id=post_job.id,
        captured_at=resolved_captured_at,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        raw=raw,
    )
    maybe_mark_post_job_measured(post_job)

    return metric_snapshot


def append_stub_metric_snapshot(post_job: PostJob) -> MetricSnapshot:
    """Copy documented mock views onto a mock-published job.

    Args:
        post_job: Must have `platform_post_id` starting with `mock-`.

    Returns:
        Uncommitted snapshot with stub counts.

    Raises:
        StubMetricsNotAvailableError: Job is not mock-published.
    """

    is_mock_published: bool = post_job_is_mock_published(post_job)

    if not is_mock_published:
        raise StubMetricsNotAvailableError(
            post_job.id,
            post_job.platform_post_id,
            post_job.status,
        )

    stub_snapshot: MetricSnapshot = append_metric_snapshot(
        post_job,
        views=STUB_MOCK_VIEWS,
        likes=STUB_MOCK_LIKES,
        comments=STUB_MOCK_COMMENTS,
        shares=STUB_MOCK_SHARES,
        captured_at=None,
        raw={"source": "mock_stub"},
    )

    return stub_snapshot


def maybe_mark_post_job_measured(post_job: PostJob) -> None:
    """Move `published` / `failed` to terminal `measured` when allowed."""

    current_status: PostJobStatus = post_job.status

    if current_status not in MEASUREABLE_POST_JOB_STATUSES:
        return

    allowed_targets: frozenset[PostJobStatus] = POST_JOB_STATUS_TRANSITIONS.get(
        current_status,
        frozenset(),
    )

    if PostJobStatus.MEASURED not in allowed_targets:
        return

    post_job.status = PostJobStatus.MEASURED


def collect_latest_view_counts_for_cluster(
    cluster_id: uuid.UUID,
    our_database_session: Session,
) -> tuple[int, int, int, list[int]]:
    """Latest-wins view counts for post jobs under a cluster's accounts.

    Jobs with no snapshot, or whose latest snapshot has `views` null,
    are omitted from the views list (they still count in job totals).

    Args:
        cluster_id: Cluster whose accounts own the post jobs.
        our_database_session: Open SQLAlchemy session.

    Returns:
        `(post_job_count, snapshot_job_count, views_job_count, view_counts)`.
    """

    account_selection: Select[tuple[Account]] = select(Account).where(
        Account.cluster_id == cluster_id,
    )
    account_scalars = our_database_session.scalars(account_selection)
    accounts: list[Account] = list(account_scalars.all())
    account_ids: list[uuid.UUID] = [account.id for account in accounts]

    if len(account_ids) == 0:
        empty_view_counts: list[int] = []

        return (0, 0, 0, empty_view_counts)

    post_job_selection: Select[tuple[PostJob]] = select(PostJob).where(
        PostJob.account_id.in_(account_ids),
    )
    post_job_scalars = our_database_session.scalars(post_job_selection)
    post_jobs: list[PostJob] = list(post_job_scalars.all())
    post_job_count: int = len(post_jobs)
    post_job_ids: list[uuid.UUID] = [post_job.id for post_job in post_jobs]

    if post_job_count == 0:
        empty_job_view_counts: list[int] = []

        return (0, 0, 0, empty_job_view_counts)

    latest_snapshot_by_post_job_id: dict[uuid.UUID, MetricSnapshot] = (
        fetch_latest_snapshots_by_post_job_ids(
            post_job_ids,
            our_database_session,
        )
    )
    snapshot_job_count: int = len(latest_snapshot_by_post_job_id)
    view_counts: list[int] = []

    for latest_snapshot in latest_snapshot_by_post_job_id.values():
        latest_views: int | None = latest_snapshot.views

        if latest_views is None:
            continue

        view_counts.append(int(latest_views))

    views_job_count: int = len(view_counts)

    return (post_job_count, snapshot_job_count, views_job_count, view_counts)


def fetch_latest_snapshots_by_post_job_ids(
    post_job_ids: list[uuid.UUID],
    our_database_session: Session,
) -> dict[uuid.UUID, MetricSnapshot]:
    """Latest-wins snapshot per post job id.

    Args:
        post_job_ids: Jobs to look up. Empty list returns {}.
        our_database_session: Open SQLAlchemy session.

    Returns:
        Map of post_job_id to the newest MetricSnapshot.
    """

    latest_snapshot_by_post_job_id: dict[uuid.UUID, MetricSnapshot] = {}

    if len(post_job_ids) == 0:
        return latest_snapshot_by_post_job_id

    snapshot_selection: Select[tuple[MetricSnapshot]] = select(MetricSnapshot).where(
        MetricSnapshot.post_job_id.in_(post_job_ids),
    )
    ordered_snapshot_selection: Select[tuple[MetricSnapshot]] = snapshot_selection.order_by(
        MetricSnapshot.captured_at.desc(),
        MetricSnapshot.id.desc(),
    )
    snapshot_scalars = our_database_session.scalars(ordered_snapshot_selection)
    metric_snapshots: list[MetricSnapshot] = list(snapshot_scalars.all())

    for metric_snapshot in metric_snapshots:
        already_seen: bool = metric_snapshot.post_job_id in latest_snapshot_by_post_job_id

        if already_seen:
            continue

        latest_snapshot_by_post_job_id[metric_snapshot.post_job_id] = metric_snapshot

    return latest_snapshot_by_post_job_id


def calculate_cluster_median_views(
    cluster_id: uuid.UUID,
    our_database_session: Session,
) -> tuple[int, int, int, float | None]:
    """Median of latest-wins views across jobs that have a views snapshot.

    Empty cluster or no views → `median_views` is None (not zero).

    Args:
        cluster_id: Cluster to roll up.
        our_database_session: Open SQLAlchemy session.

    Returns:
        `(post_job_count, snapshot_job_count, views_job_count, median_views)`.
    """

    post_job_count: int
    snapshot_job_count: int
    views_job_count: int
    view_counts: list[int]
    post_job_count, snapshot_job_count, views_job_count, view_counts = (
        collect_latest_view_counts_for_cluster(
            cluster_id,
            our_database_session,
        )
    )
    median_views: float | None = calculate_median_of_numbers(view_counts)

    return (post_job_count, snapshot_job_count, views_job_count, median_views)


def _resolve_captured_at(captured_at: datetime | None) -> datetime:
    """Use UTC now, or treat a naive override as UTC."""

    if captured_at is None:
        current_captured_at: datetime = datetime.now(timezone.utc)

        return current_captured_at

    if captured_at.tzinfo is None:
        utc_captured_at: datetime = captured_at.replace(tzinfo=timezone.utc)

        return utc_captured_at

    return captured_at
