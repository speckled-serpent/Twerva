"""Build agent-readable cluster summaries (JSON payload + markdown)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models import Account, Artifact, Cluster, PostJob, SteerAction
from app.models.enums import ArtifactStatus, PostJobStatus, SteerActionType


RECENT_SUMMARY_LIMIT: int = 10


def fetch_recent_cluster_artifacts(
    cluster_id: uuid.UUID,
    our_database_session: Session,
    limit: int = RECENT_SUMMARY_LIMIT,
) -> list[Artifact]:
    """Newest artifacts linked to the cluster, capped.

    Args:
        cluster_id: Cluster primary key.
        our_database_session: Open SQLAlchemy session.
        limit: Maximum rows.

    Returns:
        Artifact rows, newest first.
    """

    artifact_selection: Select[tuple[Artifact]] = select(Artifact).where(
        Artifact.cluster_id == cluster_id,
    )
    ordered_artifact_selection: Select[tuple[Artifact]] = artifact_selection.order_by(
        Artifact.created_at.desc(),
    )
    limited_artifact_selection: Select[tuple[Artifact]] = ordered_artifact_selection.limit(
        limit,
    )
    artifact_scalars = our_database_session.scalars(limited_artifact_selection)
    artifacts: list[Artifact] = list(artifact_scalars.all())

    return artifacts


def fetch_recent_cluster_post_jobs(
    cluster_id: uuid.UUID,
    our_database_session: Session,
    limit: int = RECENT_SUMMARY_LIMIT,
) -> list[PostJob]:
    """Newest post jobs on accounts in the cluster, capped.

    Args:
        cluster_id: Cluster primary key.
        our_database_session: Open SQLAlchemy session.
        limit: Maximum rows.

    Returns:
        PostJob rows, newest first.
    """

    post_job_selection: Select[tuple[PostJob]] = select(PostJob)
    joined_post_job_selection: Select[tuple[PostJob]] = post_job_selection.join(
        Account,
        PostJob.account_id == Account.id,
    )
    cluster_post_job_selection: Select[tuple[PostJob]] = joined_post_job_selection.where(
        Account.cluster_id == cluster_id,
    )
    ordered_post_job_selection: Select[tuple[PostJob]] = cluster_post_job_selection.order_by(
        PostJob.created_at.desc(),
    )
    limited_post_job_selection: Select[tuple[PostJob]] = ordered_post_job_selection.limit(
        limit,
    )
    post_job_scalars = our_database_session.scalars(limited_post_job_selection)
    post_jobs: list[PostJob] = list(post_job_scalars.all())

    return post_jobs


def fetch_recent_cluster_steer_actions(
    cluster_id: uuid.UUID,
    our_database_session: Session,
    limit: int = RECENT_SUMMARY_LIMIT,
) -> list[SteerAction]:
    """Newest steer_actions for the cluster, capped.

    Args:
        cluster_id: Cluster primary key.
        our_database_session: Open SQLAlchemy session.
        limit: Maximum rows.

    Returns:
        SteerAction rows, newest first.
    """

    steer_selection: Select[tuple[SteerAction]] = select(SteerAction).where(
        SteerAction.cluster_id == cluster_id,
    )
    ordered_steer_selection: Select[tuple[SteerAction]] = steer_selection.order_by(
        SteerAction.created_at.desc(),
    )
    limited_steer_selection: Select[tuple[SteerAction]] = ordered_steer_selection.limit(
        limit,
    )
    steer_scalars = our_database_session.scalars(limited_steer_selection)
    steer_actions: list[SteerAction] = list(steer_scalars.all())

    return steer_actions


def render_cluster_agent_summary_markdown(
    cluster: Cluster,
    post_job_count: int,
    snapshot_job_count: int,
    views_job_count: int,
    median_views: float | None,
    artifacts: list[Artifact],
    post_jobs: list[PostJob],
    steer_actions: list[SteerAction],
) -> str:
    """Render a plaintext markdown brief for agents.

    Args:
        cluster: Cluster row.
        post_job_count: Jobs under the cluster's accounts.
        snapshot_job_count: Jobs with at least one snapshot.
        views_job_count: Jobs whose latest snapshot has views.
        median_views: Median of those views, or None.
        artifacts: Recent artifacts (already ordered).
        post_jobs: Recent post jobs (already ordered).
        steer_actions: Recent steer rows (already ordered).

    Returns:
        Markdown string.
    """

    active_label: str

    if cluster.is_active:
        active_label = "yes"
    else:
        active_label = "no"

    median_label: str

    if median_views is None:
        median_label = "null (no jobs with views snapshots)"
    else:
        median_label = str(median_views)

    markdown_lines: list[str] = [
        f"# Cluster {cluster.name} (`{cluster.slug}`)",
        "",
        f"- id: `{cluster.id}`",
        f"- active: {active_label}",
        "",
        "## Metrics",
        "",
        f"- median views: {median_label}",
        f"- post jobs: {post_job_count}",
        f"- jobs with snapshots: {snapshot_job_count}",
        f"- jobs with views: {views_job_count}",
        "",
        "## Recent artifacts",
        "",
    ]
    _append_artifact_markdown_lines(markdown_lines, artifacts)
    markdown_lines.extend(["", "## Recent post jobs", ""])
    _append_post_job_markdown_lines(markdown_lines, post_jobs)
    markdown_lines.extend(["", "## Recent steer actions", ""])
    _append_steer_markdown_lines(markdown_lines, steer_actions)
    markdown_body: str = "\n".join(markdown_lines) + "\n"

    return markdown_body


def _append_artifact_markdown_lines(
    markdown_lines: list[str],
    artifacts: list[Artifact],
) -> None:
    """Append artifact bullets, or an empty-state line."""

    if len(artifacts) == 0:
        markdown_lines.append("- (none)")

        return

    for artifact in artifacts:
        artifact_status: ArtifactStatus = artifact.status
        caption_excerpt: str = _caption_excerpt(artifact.caption)
        created_at_label: str = _format_timestamp(artifact.created_at)
        markdown_lines.append(
            (
                f"- `{artifact.id}` status={artifact_status.value} "
                f"created={created_at_label} caption={caption_excerpt}"
            ),
        )


def _append_post_job_markdown_lines(
    markdown_lines: list[str],
    post_jobs: list[PostJob],
) -> None:
    """Append post-job bullets, or an empty-state line."""

    if len(post_jobs) == 0:
        markdown_lines.append("- (none)")

        return

    for post_job in post_jobs:
        post_job_status: PostJobStatus = post_job.status
        platform_post_id: str = post_job.platform_post_id or "null"
        published_at_label: str = _format_timestamp(post_job.published_at)
        markdown_lines.append(
            (
                f"- `{post_job.id}` status={post_job_status.value} "
                f"platform_post_id={platform_post_id} "
                f"published_at={published_at_label}"
            ),
        )


def _append_steer_markdown_lines(
    markdown_lines: list[str],
    steer_actions: list[SteerAction],
) -> None:
    """Append steer bullets, or an empty-state line."""

    if len(steer_actions) == 0:
        markdown_lines.append("- (none)")

        return

    for steer_action in steer_actions:
        action_type: SteerActionType = steer_action.action
        reason_label: str = steer_action.reason or "null"
        created_by_label: str = steer_action.created_by or "null"
        created_at_label: str = _format_timestamp(steer_action.created_at)
        markdown_lines.append(
            (
                f"- {action_type.value} by {created_by_label} "
                f"at {created_at_label} reason={reason_label}"
            ),
        )


def _caption_excerpt(caption: str | None) -> str:
    """Short single-line caption for markdown bullets."""

    if caption is None or caption == "":
        return "null"

    collapsed_caption: str = " ".join(caption.split())
    excerpt_limit: int = 80

    if len(collapsed_caption) <= excerpt_limit:
        return collapsed_caption

    truncated_caption: str = collapsed_caption[:excerpt_limit] + "…"

    return truncated_caption


def _format_timestamp(timestamp: datetime | None) -> str:
    """ISO-8601 or `null`."""

    if timestamp is None:
        return "null"

    iso_timestamp: str = timestamp.isoformat()

    return iso_timestamp
