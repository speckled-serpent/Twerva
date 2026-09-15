"""Create a `scheduled` PostJob from an approved Artifact (1.5c).

Cluster / brand coherence (locked for MVP):

- The Account's Cluster `brand_id` must equal the Artifact `brand_id`.
- When the Artifact has `cluster_id` set, the Account must belong to
  that same cluster.
- When Artifact `cluster_id` is null, any Account under the same brand
  is allowed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Account, Artifact, Cluster, PostJob
from app.models.enums import ArtifactStatus, PostJobStatus
from app.schedule.cadence import as_utc_datetime, raise_if_cadence_cap_exceeded
from app.schedule.errors import (
    ArtifactNotApprovedError,
    ScheduleBrandMismatchError,
    ScheduleClusterMismatchError,
)


def schedule_approved_artifact(
    artifact: Artifact,
    account: Account,
    account_cluster: Cluster,
    scheduled_for: datetime,
    our_database_session: Session,
) -> PostJob:
    """Insert a PostJob with status `scheduled` (not committed).

    Args:
        artifact: Must be `approved`.
        account: Target platform account.
        account_cluster: Cluster row for `account.cluster_id` (already loaded).
        scheduled_for: ISO timestamptz; stored as UTC.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The flushed PostJob row (`status=scheduled`).

    Raises:
        ArtifactNotApprovedError: Artifact is not `approved`.
        ScheduleBrandMismatchError: Account cluster brand != artifact brand.
        ScheduleClusterMismatchError: Artifact cluster set and does not match.
        CadenceCapExceededError: UTC-day cap would be exceeded.
    """

    require_artifact_is_approved(artifact)
    require_schedule_brand_and_cluster_coherence(
        artifact,
        account,
        account_cluster,
    )
    raise_if_cadence_cap_exceeded(
        account,
        scheduled_for,
        our_database_session,
    )
    scheduled_for_utc: datetime = as_utc_datetime(scheduled_for)
    created_post_job: PostJob = PostJob(
        artifact_id=artifact.id,
        account_id=account.id,
        status=PostJobStatus.SCHEDULED,
        scheduled_for=scheduled_for_utc,
    )
    our_database_session.add(created_post_job)
    our_database_session.flush()

    return created_post_job


def require_artifact_is_approved(artifact: Artifact) -> None:
    """Raise when the Artifact is not eligible to schedule."""

    if artifact.status != ArtifactStatus.APPROVED:
        raise ArtifactNotApprovedError(artifact.id, artifact.status)


def require_schedule_brand_and_cluster_coherence(
    artifact: Artifact,
    account: Account,
    account_cluster: Cluster,
) -> None:
    """Enforce brand match always, cluster match when the Artifact has a cluster."""

    if account_cluster.brand_id != artifact.brand_id:
        raise ScheduleBrandMismatchError(
            artifact.id,
            account.id,
            artifact.brand_id,
            account_cluster.brand_id,
        )

    if artifact.cluster_id is None:

        return

    if account.cluster_id != artifact.cluster_id:
        raise ScheduleClusterMismatchError(
            artifact.id,
            account.id,
            artifact.cluster_id,
            account.cluster_id,
        )
